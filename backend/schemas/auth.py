"""Authentication and user schemas."""

from __future__ import annotations

import datetime as dt
import re

from pydantic import BaseModel, EmailStr, Field, field_validator

from backend.core.constants import ROLES
from backend.schemas.common import ORMModel

_PHONE_RE = re.compile(r"^\+?[0-9 \-()]{6,20}$")


class SignupRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=160)
    email: str = Field(..., max_length=255)
    phone: str | None = Field(default=None, max_length=32)
    password: str = Field(..., min_length=8, max_length=128)
    role: str = Field(default="USER")

    @field_validator("email")
    @classmethod
    def _email(cls, value: str) -> str:
        value = value.strip().lower()
        if "@" not in value or "." not in value.split("@")[-1]:
            raise ValueError("a valid email address is required")
        return value

    @field_validator("phone")
    @classmethod
    def _phone(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        value = value.strip()
        if not _PHONE_RE.match(value):
            raise ValueError("phone number format is invalid")
        return value

    @field_validator("role")
    @classmethod
    def _role(cls, value: str) -> str:
        value = (value or "USER").strip().upper()
        if value not in ROLES:
            raise ValueError(f"role must be one of {', '.join(ROLES)}")
        return value


class LoginRequest(BaseModel):
    email: str
    password: str
    # Optional: the portal the login form was submitted from.  When present the
    # backend refuses tokens for accounts that do not hold that role.
    role: str | None = None

    @field_validator("email")
    @classmethod
    def _email(cls, value: str) -> str:
        return value.strip().lower()


class UserPublic(ORMModel):
    id: int
    user_id: str
    name: str
    email: str
    phone: str | None = None
    role: str
    organisation: str | None = None
    team: str | None = None
    created_at: dt.datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    role: str
    user: UserPublic


class ProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    phone: str | None = Field(default=None, max_length=32)


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)
