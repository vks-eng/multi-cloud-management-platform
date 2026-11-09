from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import AnonCtx, Ctx, CurrentUser, DbSession
from app.core.config import get_settings
from app.schemas.common import Message
from app.schemas.user import (
    LoginRequest,
    PasswordChange,
    ProfileUpdate,
    TokenResponse,
    UserRead,
    UserRegister,
)
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["Auth"])


def _token_response(user, token: str) -> TokenResponse:  # type: ignore[no-untyped-def]
    return TokenResponse(
        access_token=token,
        expires_in=get_settings().access_token_expire_minutes * 60,
        user=UserRead.model_validate(user),
    )


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(data: UserRegister, db: DbSession, ctx: AnonCtx) -> UserRead:
    """Self-registration. The first user to register becomes the administrator."""
    return UserRead.model_validate(AuthService(db).register(data, ctx))


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db: DbSession, ctx: AnonCtx) -> TokenResponse:
    user, token = AuthService(db).authenticate(data.email, data.password, ctx)
    return _token_response(user, token)


@router.post("/token", response_model=TokenResponse, include_in_schema=True)
def login_form(
    form: Annotated[OAuth2PasswordRequestForm, Depends()], db: DbSession, ctx: AnonCtx
) -> TokenResponse:
    """OAuth2 password flow (used by the Swagger UI 'Authorize' button)."""
    user, token = AuthService(db).authenticate(form.username, form.password, ctx)
    return _token_response(user, token)


@router.get("/me", response_model=UserRead)
def me(user: CurrentUser) -> UserRead:
    return UserRead.model_validate(user)


@router.patch("/me", response_model=UserRead)
def update_me(data: ProfileUpdate, db: DbSession, user: CurrentUser, ctx: Ctx) -> UserRead:
    return UserRead.model_validate(AuthService(db).update_profile(user, data, ctx))


@router.post("/me/password", response_model=Message)
def change_password(data: PasswordChange, db: DbSession, user: CurrentUser, ctx: Ctx) -> Message:
    AuthService(db).change_password(user, data, ctx)
    return Message(message="Password updated")
