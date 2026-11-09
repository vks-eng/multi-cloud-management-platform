from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import Ctx, DbSession, PageParams, require
from app.core.permissions import Permission
from app.repositories.repos import CostAlertRepository
from app.schemas.common import Page
from app.schemas.cost import (
    BudgetCreate,
    BudgetRead,
    BudgetUpdate,
    CostAlertRead,
    CostSummary,
    MonthlyTrendPoint,
    ServiceCost,
)
from app.services.costs import CostService

router = APIRouter(prefix="/costs", tags=["Costs"])
_read = Depends(require(Permission.COSTS_READ))
_write = Depends(require(Permission.BUDGETS_WRITE))


@router.get("/summary", response_model=CostSummary, dependencies=[_read])
def summary(db: DbSession) -> CostSummary:
    return CostService(db).summary()


@router.get("/trends", response_model=list[MonthlyTrendPoint], dependencies=[_read])
def trends(db: DbSession, months: int = Query(default=6, ge=1, le=24)) -> list[MonthlyTrendPoint]:
    return CostService(db).trends(months)


@router.get("/by-service", response_model=list[ServiceCost], dependencies=[_read])
def by_service(db: DbSession, month: date | None = None) -> list[ServiceCost]:
    return CostService(db).by_service(month)


@router.get("/budgets", response_model=list[BudgetRead], dependencies=[_read])
def list_budgets(db: DbSession) -> list[BudgetRead]:
    return CostService(db).list_budgets()


@router.post(
    "/budgets",
    response_model=BudgetRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[_write],
)
def create_budget(data: BudgetCreate, db: DbSession, ctx: Ctx) -> BudgetRead:
    service = CostService(db)
    return service.to_read(service.create_budget(data, ctx))


@router.patch("/budgets/{budget_id}", response_model=BudgetRead, dependencies=[_write])
def update_budget(budget_id: uuid.UUID, data: BudgetUpdate, db: DbSession, ctx: Ctx) -> BudgetRead:
    service = CostService(db)
    return service.to_read(service.update_budget(budget_id, data, ctx))


@router.delete(
    "/budgets/{budget_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[_write]
)
def delete_budget(budget_id: uuid.UUID, db: DbSession, ctx: Ctx) -> Response:
    CostService(db).delete_budget(budget_id, ctx)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/budgets/evaluate", response_model=list[CostAlertRead], dependencies=[_write])
def evaluate(db: DbSession) -> list[CostAlertRead]:
    """Evaluate all active budgets now; returns newly created cost alerts."""
    return [CostAlertRead.model_validate(a) for a in CostService(db).evaluate_budgets()]


@router.get("/alerts", response_model=Page[CostAlertRead], dependencies=[_read])
def cost_alerts(db: DbSession, page: PageParams) -> Page[CostAlertRead]:
    rows, total = CostAlertRepository(db).list_with_budget(page.limit, page.offset)
    items = []
    for alert, name in rows:
        model = CostAlertRead.model_validate(alert)
        model.budget_name = name
        items.append(model)
    return Page(items=items, total=total, limit=page.limit, offset=page.offset)
