"""Signup, login and session endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.constants import ROLES
from backend.core.deps import get_current_user
from backend.core.security import create_access_token, hash_password, verify_password
from backend.db.session import get_db
from backend.models.entities import User
from backend.schemas.auth import (
    LoginRequest,
    SignupRequest,
    TokenResponse,
    UserPublic,
)
from backend.services import audit
from backend.utils.ids import new_user_id

router = APIRouter(prefix="/auth", tags=["auth"])


def _token_response(user: User) -> dict:
    token, expires_in = create_access_token(
        subject=user.user_id, role=user.role, extra={"name": user.name}
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": expires_in,
        "role": user.role,
        "user": UserPublic.model_validate(user),
    }


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, db: Session = Depends(get_db)):
    """Register a new account.

    Self-service signup is limited to citizen (``USER``) accounts. Authority and
    maintenance accounts are provisioned by an administrator (see
    ``scripts/seed_data.py``) because they carry elevated permissions.
    """
    if payload.role != "USER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Authority and maintenance accounts are provisioned by the "
                "municipal administrator and cannot be self-registered."
            ),
        )

    existing = db.execute(
        select(User).where(User.email == payload.email)
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email address already exists.",
        )

    user = User(
        user_id=new_user_id(db, payload.role),
        name=payload.name.strip(),
        email=payload.email,
        phone=payload.phone,
        password_hash=hash_password(payload.password),
        role=payload.role,
        is_active=True,
    )
    db.add(user)
    db.flush()
    audit.record(
        db,
        user_id=user.user_id,
        role=user.role,
        action="user.signup",
        entity_type="user",
        entity_id=user.user_id,
    )
    db.commit()
    db.refresh(user)
    return _token_response(user)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.execute(select(User).where(User.email == payload.email)).scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        # Identical message for both cases so the endpoint cannot be used to
        # enumerate registered email addresses.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been deactivated.",
        )

    if payload.role:
        requested = payload.role.strip().upper()
        if requested in ROLES and requested != user.role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This account does not have {requested.title()} portal access.",
            )

    audit.record(
        db,
        user_id=user.user_id,
        role=user.role,
        action="user.login",
        entity_type="user",
        entity_id=user.user_id,
    )
    db.commit()
    return _token_response(user)


@router.get("/me", response_model=UserPublic)
def me(current_user: User = Depends(get_current_user)):
    return UserPublic.model_validate(current_user)


@router.post("/refresh", response_model=TokenResponse)
def refresh(current_user: User = Depends(get_current_user)):
    """Exchange a still-valid token for a fresh one."""
    return _token_response(current_user)
