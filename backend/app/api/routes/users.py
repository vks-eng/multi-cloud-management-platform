from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from app.api.deps import Ctx, CurrentUser, DbSession, PageParams, require
from app.core.permissions import ROLE_DESCRIPTIONS, ROLE_PERMISSIONS, Permission, Role
from app.repositories.repos import UserRepository
from app.schemas.common import Page
from app.schemas.user import RolePermissions, UserAdminUpdate, UserCreateByAdmin, UserRead
from app.services.auth import AuthService

router = APIRouter(prefix="/users", tags=["Users"])
_admin = Depends(require(Permission.USERS_MANAGE))


@router.get("/roles", response_model=list[RolePermissions])
def roles(_: CurrentUser) -> list[RolePermissions]:
    """Role -> permission matrix (visible to every authenticated user)."""
    return [
        RolePermissions(
            role=role,
            description=ROLE_DESCRIPTIONS[role],
            permissions=sorted(p.value for p in ROLE_PERMISSIONS[role]),
        )
        for role in Role
    ]


@router.get("", response_model=Page[UserRead], dependencies=[_admin])
def list_users(db: DbSession, page: PageParams, search: str | None = None) -> Page[UserRead]:
    items, total = UserRepository(db).list(page.limit, page.offset, search)
    return Page(
        items=[UserRead.model_validate(u) for u in items],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.post(
    "", response_model=UserRead, status_code=status.HTTP_201_CREATED, dependencies=[_admin]
)
def create_user(data: UserCreateByAdmin, db: DbSession, ctx: Ctx) -> UserRead:
    return UserRead.model_validate(AuthService(db).create_user(data, ctx))


@router.patch("/{user_id}", response_model=UserRead, dependencies=[_admin])
def update_user(user_id: uuid.UUID, data: UserAdminUpdate, db: DbSession, ctx: Ctx) -> UserRead:
    return UserRead.model_validate(AuthService(db).admin_update(user_id, data, ctx))
