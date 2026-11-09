from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.permissions import Role
from app.schemas.common import ORMModel


def _check_password_strength(value: str) -> str:
    if len(value) < 10:
        raise ValueError("Password must be at least 10 characters")
    if not any(c.isdigit() for c in value) or not any(c.isalpha() for c in value):
        raise ValueError("Password must contain letters and digits")
    return value


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    full_name: str = Field(min_length=1, max_length=200)

    _pw = field_validator("password")(_check_password_strength)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserRead(ORMModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str
    role: Role
    is_active: bool
    job_title: str | None
    timezone: str
    last_login_at: datetime | None
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserRead


class ProfileUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    job_title: str | None = Field(default=None, max_length=120)
    timezone: str | None = Field(default=None, max_length=64)


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=10, max_length=128)

    _pw = field_validator("new_password")(_check_password_strength)


class UserAdminUpdate(BaseModel):
    role: Role | None = None
    is_active: bool | None = None


class UserCreateByAdmin(UserRegister):
    role: Role = Role.VIEWER


class RolePermissions(BaseModel):
    role: Role
    description: str
    permissions: list[str]
