from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends

from app.api.deps import CurrentUser, DbSession, PageParams, require
from app.core.permissions import Permission, has_permission
from app.repositories.repos import AuditRepository, LoginEventRepository
from app.schemas.audit import AuditLogRead, LoginEventRead
from app.schemas.common import Page

router = APIRouter(prefix="/audit", tags=["Audit"])
_audit = Depends(require(Permission.AUDIT_READ))


@router.get("/logs", response_model=Page[AuditLogRead], dependencies=[_audit])
def audit_logs(
    db: DbSession,
    page: PageParams,
    action: str | None = None,
    actor_id: uuid.UUID | None = None,
    target_type: str | None = None,
    status: str | None = None,
) -> Page[AuditLogRead]:
    repo = AuditRepository(db)
    items, total = repo.paginate(
        repo.list_stmt(action, actor_id, target_type, status), page.limit, page.offset
    )
    return Page(
        items=[AuditLogRead.model_validate(i) for i in items],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get("/access-history", response_model=Page[LoginEventRead])
def access_history(
    db: DbSession,
    page: PageParams,
    user: CurrentUser,
    user_id: uuid.UUID | None = None,
    success: bool | None = None,
) -> Page[LoginEventRead]:
    """Login history. Admins may query any user; everyone else sees only their own."""
    if not has_permission(user.role, Permission.AUDIT_READ):
        user_id = user.id
    repo = LoginEventRepository(db)
    items, total = repo.paginate(repo.list_stmt(user_id, success), page.limit, page.offset)
    return Page(
        items=[LoginEventRead.model_validate(i) for i in items],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )
