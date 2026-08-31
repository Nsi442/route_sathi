"""FastAPI dependencies: authentication and role-based authorisation.

Frontend route guards are a convenience only - these dependencies are the
security boundary.  Every non-public endpoint depends on one of
``require_user`` / ``require_authority`` / ``require_maintenance``.
"""

from __future__ import annotations

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.constants import ROLE_AUTHORITY, ROLE_MAINTENANCE, ROLE_USER
from backend.core.security import decode_access_token
from backend.db.session import get_db
from backend.models.entities import User

bearer_scheme = HTTPBearer(auto_error=False, description="JWT access token")

CREDENTIALS_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated. Please sign in again.",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or not credentials.credentials:
        raise CREDENTIALS_ERROR
    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your session has expired. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except jwt.PyJWTError as exc:
        raise CREDENTIALS_ERROR from exc

    user_id = payload.get("sub")
    if not user_id:
        raise CREDENTIALS_ERROR

    user = db.execute(select(User).where(User.user_id == user_id)).scalar_one_or_none()
    if user is None or not user.is_active:
        raise CREDENTIALS_ERROR
    # The role is re-read from the database rather than trusted from the token,
    # so a role change takes effect immediately.
    if payload.get("role") != user.role:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your account permissions changed. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def _role_guard(*allowed: str):
    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action.",
            )
        return current_user

    return dependency


require_user = _role_guard(ROLE_USER)
require_authority = _role_guard(ROLE_AUTHORITY)
require_maintenance = _role_guard(ROLE_MAINTENANCE)

# Endpoints that both back-office portals may read (e.g. evidence images).
require_staff = _role_guard(ROLE_AUTHORITY, ROLE_MAINTENANCE)
require_any_role = _role_guard(ROLE_USER, ROLE_AUTHORITY, ROLE_MAINTENANCE)
