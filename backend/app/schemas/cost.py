from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from app.models.enums import CloudProvider
from app.schemas.common import ORMModel


class ProviderCost(BaseModel):
    provider: str
    current_month: Decimal
    previous_month: Decimal
    change_percent: float | None


class CostSummary(BaseModel):
    currency: str = "USD"
    current_month: Decimal
    previous_month: Decimal
    change_percent: float | None
    forecast_current_month: Decimal
    by_provider: list[ProviderCost]


class MonthlyTrendPoint(BaseModel):
    month: date
    aws: Decimal = Decimal("0")
    azure: Decimal = Decimal("0")
    gcp: Decimal = Decimal("0")
    total: Decimal = Decimal("0")


class ServiceCost(BaseModel):
    provider: str
    service: str
    amount: Decimal


class BudgetBase(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    provider: CloudProvider | None = None
    cloud_account_id: uuid.UUID | None = None
    monthly_limit: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    alert_threshold_percent: int = Field(default=80, ge=1, le=100)

    @model_validator(mode="after")
    def _single_scope(self) -> BudgetBase:
        if self.provider and self.cloud_account_id:
            raise ValueError("A budget can be scoped to a provider OR an account, not both")
        return self


class BudgetCreate(BudgetBase):
    pass


class BudgetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    monthly_limit: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)
    alert_threshold_percent: int | None = Field(default=None, ge=1, le=100)
    is_active: bool | None = None


class BudgetRead(ORMModel):
    id: uuid.UUID
    name: str
    provider: str | None
    cloud_account_id: uuid.UUID | None
    monthly_limit: Decimal
    alert_threshold_percent: int
    is_active: bool
    created_at: datetime
    current_spend: Decimal = Decimal("0")
    utilization_percent: float = 0.0


class CostAlertRead(ORMModel):
    id: uuid.UUID
    budget_id: uuid.UUID
    budget_name: str | None = None
    period_month: date
    threshold_percent: int
    actual_amount: Decimal
    budget_limit: Decimal
    severity: str
    acknowledged: bool
    created_at: datetime
