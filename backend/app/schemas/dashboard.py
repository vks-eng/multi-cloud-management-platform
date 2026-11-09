from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.schemas.audit import AlertRead, AuditLogRead


class CountItem(BaseModel):
    key: str
    count: int


class UsagePoint(BaseModel):
    timestamp: datetime
    avg_cpu_percent: float | None
    avg_memory_percent: float | None
    network_in_mb: float
    network_out_mb: float


class UsageSummary(BaseModel):
    avg_cpu_percent: float | None
    avg_memory_percent: float | None
    total_storage_gb: float
    high_cpu_resources: int
    series: list[UsagePoint]


class AccountHealth(BaseModel):
    connected: int
    error: int
    pending: int
    last_sync_at: datetime | None


class DashboardOverview(BaseModel):
    total_resources: int
    running_compute: int
    stopped_compute: int
    storage_resources: int
    accounts: AccountHealth
    by_provider: list[CountItem]
    by_status: list[CountItem]
    by_type: list[CountItem]
    by_region: list[CountItem]
    usage: UsageSummary
    month_to_date_cost: Decimal
    estimated_monthly_run_rate: Decimal
    open_alerts: int
    critical_alerts: int
    recent_alerts: list[AlertRead]
    recent_activity: list[AuditLogRead]
