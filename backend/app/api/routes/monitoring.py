from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query

from app.api.deps import Ctx, DbSession, PageParams, require
from app.core.permissions import Permission
from app.models.enums import AlertStatus
from app.repositories.repos import AlertRepository
from app.schemas.audit import AlertRead
from app.schemas.common import Page
from app.schemas.dashboard import DashboardOverview
from app.services.alerts import AlertService
from app.services.dashboard import DashboardService

router = APIRouter(tags=["Monitoring"])
_read = Depends(require(Permission.RESOURCES_READ))
_manage = Depends(require(Permission.ALERTS_MANAGE))


@router.get("/dashboard/overview", response_model=DashboardOverview, dependencies=[_read])
def overview(
    db: DbSession, usage_hours: int = Query(default=24, ge=1, le=168)
) -> DashboardOverview:
    """Resource counts, status/provider distribution, usage metrics, alerts and recent activity."""
    return DashboardService(db).overview(usage_hours)


@router.get("/alerts", response_model=Page[AlertRead], dependencies=[_read])
def list_alerts(
    db: DbSession, page: PageParams, status: str | None = None, severity: str | None = None
) -> Page[AlertRead]:
    repo = AlertRepository(db)
    items, total = repo.paginate(repo.list_stmt(status, severity), page.limit, page.offset)
    return Page(
        items=[AlertRead.model_validate(a) for a in items],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.post("/alerts/{alert_id}/acknowledge", response_model=AlertRead, dependencies=[_manage])
def acknowledge(alert_id: uuid.UUID, db: DbSession, ctx: Ctx) -> AlertRead:
    return AlertRead.model_validate(
        AlertService(db).transition(alert_id, AlertStatus.ACKNOWLEDGED, ctx)
    )


@router.post("/alerts/{alert_id}/resolve", response_model=AlertRead, dependencies=[_manage])
def resolve(alert_id: uuid.UUID, db: DbSession, ctx: Ctx) -> AlertRead:
    return AlertRead.model_validate(
        AlertService(db).transition(alert_id, AlertStatus.RESOLVED, ctx)
    )
