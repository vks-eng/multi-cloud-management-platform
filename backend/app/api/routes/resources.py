from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query

from app.api.deps import DbSession, PageParams, require
from app.core.permissions import Permission
from app.models import CloudAccount, Resource
from app.repositories.repos import ResourceRepository
from app.schemas.common import Page
from app.schemas.resource import ResourceChangeRead, ResourceMetricRead, ResourceRead
from app.services.inventory import InventoryService

router = APIRouter(
    prefix="/resources",
    tags=["Resources"],
    dependencies=[Depends(require(Permission.RESOURCES_READ))],
)

_SORTS = {
    "name": Resource.name,
    "-name": Resource.name.desc(),
    "cost": Resource.monthly_cost_estimate,
    "-cost": Resource.monthly_cost_estimate.desc(),
    "last_seen": Resource.last_seen_at,
    "-last_seen": Resource.last_seen_at.desc(),
}


def _names(db: DbSession, ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not ids:
        return {}
    from sqlalchemy import select

    rows = db.execute(select(CloudAccount.id, CloudAccount.name).where(CloudAccount.id.in_(ids)))
    return {r[0]: r[1] for r in rows}


@router.get("", response_model=Page[ResourceRead])
def list_resources(
    db: DbSession,
    page: PageParams,
    provider: str | None = None,
    resource_type: str | None = None,
    status: str | None = None,
    account_id: uuid.UUID | None = None,
    region: str | None = None,
    search: str | None = Query(default=None, max_length=100),
    include_deleted: bool = False,
    sort: str = "name",
) -> Page[ResourceRead]:
    repo = ResourceRepository(db)
    stmt = repo.search_stmt(
        provider=provider,
        resource_type=resource_type,
        status=status,
        account_id=account_id,
        region=region,
        search=search,
        include_deleted=include_deleted,
    )
    stmt = stmt.order_by(_SORTS.get(sort, Resource.name), Resource.id)
    items, total = repo.paginate(stmt, page.limit, page.offset)
    names = _names(db, {r.cloud_account_id for r in items})
    out = []
    for r in items:
        model = ResourceRead.model_validate(r)
        model.account_name = names.get(r.cloud_account_id)
        out.append(model)
    return Page(items=out, total=total, limit=page.limit, offset=page.offset)


@router.get("/changes", response_model=Page[ResourceChangeRead])
def all_changes(db: DbSession, page: PageParams) -> Page[ResourceChangeRead]:
    """Resource change history across the whole estate."""
    rows, total = ResourceRepository(db).changes(None, page.limit, page.offset)
    items = []
    for change, name in rows:
        model = ResourceChangeRead.model_validate(change)
        model.resource_name = name
        items.append(model)
    return Page(items=items, total=total, limit=page.limit, offset=page.offset)


@router.get("/{resource_id}", response_model=ResourceRead)
def get_resource(resource_id: uuid.UUID, db: DbSession) -> ResourceRead:
    res = ResourceRepository(db).get_or_404(resource_id)
    model = ResourceRead.model_validate(res)
    model.account_name = _names(db, {res.cloud_account_id}).get(res.cloud_account_id)
    return model


@router.get("/{resource_id}/changes", response_model=Page[ResourceChangeRead])
def resource_changes(
    resource_id: uuid.UUID, db: DbSession, page: PageParams
) -> Page[ResourceChangeRead]:
    repo = ResourceRepository(db)
    repo.get_or_404(resource_id)
    rows, total = repo.changes(resource_id, page.limit, page.offset)
    items = []
    for change, name in rows:
        model = ResourceChangeRead.model_validate(change)
        model.resource_name = name
        items.append(model)
    return Page(items=items, total=total, limit=page.limit, offset=page.offset)


@router.get("/{resource_id}/metrics", response_model=list[ResourceMetricRead])
def resource_metrics(
    resource_id: uuid.UUID, db: DbSession, hours: int = Query(default=24, ge=1, le=720)
) -> list[ResourceMetricRead]:
    return [
        ResourceMetricRead.model_validate(m)
        for m in InventoryService(db).metrics(resource_id, hours)
    ]
