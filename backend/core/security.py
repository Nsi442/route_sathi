"""Password hashing and JWT issuing/verification."""

from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import os
from typing import Any

import jwt

from backend.core.config import settings

try:  # pragma: no cover - exercised implicitly by the runtime environment
    import bcrypt as _bcrypt
except Exception:  # pragma: no cover
    _bcrypt = None

_PBKDF2_ROUNDS = 260_000
_BCRYPT_MAX_BYTES = 72


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------
def hash_password(password: str) -> str:
    """Hash a plaintext password.

    bcrypt is used when available (it is pinned in ``requirements.txt``); the
    stdlib PBKDF2-HMAC-SHA256 implementation is kept as a fallback so the API
    never degrades to storing anything reversible.
    """
    if not password:
        raise ValueError("password must not be empty")
    if _bcrypt is not None:
        secret = password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
        return _bcrypt.hashpw(secret, _bcrypt.gensalt(rounds=12)).decode("utf-8")

    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ROUNDS)
    return f"pbkdf2_sha256${_PBKDF2_ROUNDS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, password_hash: str | None) -> bool:
    """Constant-time verification of a plaintext password against a stored hash."""
    if not password or not password_hash:
        return False

    if password_hash.startswith("pbkdf2_sha256$"):
        try:
            _, rounds_raw, salt_hex, digest_hex = password_hash.split("$")
            digest = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode("utf-8"),
                bytes.fromhex(salt_hex),
                int(rounds_raw),
            )
        except (ValueError, TypeError):
            return False
        return hmac.compare_digest(digest.hex(), digest_hex)

    if _bcrypt is None:
        return False
    try:
        return _bcrypt.checkpw(
            password.encode("utf-8")[:_BCRYPT_MAX_BYTES],
            password_hash.encode("utf-8"),
        )
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------------------
# JSON Web Tokens
# ---------------------------------------------------------------------------
def create_access_token(
    *,
    subject: str,
    role: str,
    extra: dict[str, Any] | None = None,
    expires_minutes: int | None = None,
) -> tuple[str, int]:
    """Return ``(token, expires_in_seconds)`` for the given subject."""
    minutes = expires_minutes or settings.access_token_expire_minutes
    now = dt.datetime.now(dt.timezone.utc)
    expires_at = now + dt.timedelta(minutes=minutes)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "iss": "routesathi",
    }
    if extra:
        payload.update(extra)
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    if isinstance(token, bytes):  # PyJWT < 2 compatibility
        token = token.decode("utf-8")
    return token, minutes * 60


def create_media_token(*, subject: str, role: str, resource: str, expires_seconds: int = 900) -> tuple[str, int]:
    """Short-lived token granting read access to one media object.

    A browser cannot attach an ``Authorization`` header to an ``<img src>`` or
    a download link, so media URLs carry this instead.  It is scoped to a
    single resource and expires quickly, mirroring how an S3 presigned URL
    behaves when object storage is configured.
    """
    now = dt.datetime.now(dt.timezone.utc)
    payload = {
        "sub": str(subject),
        "role": role,
        "scope": "media",
        "res": resource,
        "iat": int(now.timestamp()),
        "exp": int((now + dt.timedelta(seconds=expires_seconds)).timestamp()),
        "iss": "routesathi",
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    if isinstance(token, bytes):  # PyJWT < 2 compatibility
        token = token.decode("utf-8")
    return token, expires_seconds


def decode_media_token(token: str, resource: str) -> dict[str, Any]:
    """Decode a media token and check it was issued for ``resource``."""
    payload = decode_access_token(token)
    if payload.get("scope") != "media" or payload.get("res") != resource:
        raise jwt.InvalidTokenError("token is not valid for this resource")
    return payload


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a token, raising ``jwt.PyJWTError`` on failure."""
    return jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
        issuer="routesathi",
        options={"require": ["exp", "sub"]},
    )
