"""FastAPI dependencies: DB session, authentication, RBAC and request context."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Annotated

import jwt
from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.errors import AuthenticationError, PermissionDeniedError
from app.core.permissions import Permission, has_permission
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models import User
from app.services.audit import RequestContext

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token", auto_error=False)

DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(db: DbSession, token: Annotated[str | None, Depends(oauth2_scheme)]) -> User:
    if not token:
        raise AuthenticationError("Not authenticated")
    try:
        payload = decode_access_token(token)
        user_id = uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise AuthenticationError("Invalid or expired token") from None
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise AuthenticationError("User not found or inactive")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64]
    return request.client.host if request.client else None


def get_context(request: Request, user: CurrentUser) -> RequestContext:
    return RequestContext(
        user=user, ip_address=client_ip(request), user_agent=request.headers.get("user-agent")
    )


def get_anonymous_context(request: Request) -> RequestContext:
    return RequestContext(
        user=None, ip_address=client_ip(request), user_agent=request.headers.get("user-agent")
    )


Ctx = Annotated[RequestContext, Depends(get_context)]
AnonCtx = Annotated[RequestContext, Depends(get_anonymous_context)]


def require(permission: Permission) -> Callable[[User], User]:
    """Dependency factory enforcing a single RBAC permission."""

    def _checker(user: CurrentUser) -> User:
        if not has_permission(user.role, permission):
            raise PermissionDeniedError(
                f"Your role '{user.role}' lacks the '{permission.value}' permission"
            )
        return user

    return _checker


class Pagination:
    def __init__(self, limit: int = 25, offset: int = 0) -> None:
        self.limit = max(1, min(limit, 200))
        self.offset = max(0, offset)


PageParams = Annotated[Pagination, Depends(Pagination)]
