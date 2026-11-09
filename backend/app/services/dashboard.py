"""Monitoring dashboard aggregation."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.models.enums import (
    COMPUTE_TYPES,
    AccountStatus,
    AlertSeverity,
    ResourceStatus,
)
from app.repositories.repos import (
    AlertRepository,
    AuditRepository,
    CloudAccountRepository,
    CostRepository,
    ResourceRepository,
)
from app.schemas.audit import AlertRead, AuditLogRead
from app.schemas.dashboard import (
    AccountHealth,
    CountItem,
    DashboardOverview,
    UsagePoint,
    UsageSummary,
)
from app.services.costs import month_start
from app.services.inventory import HIGH_CPU_THRESHOLD


class DashboardService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.resources = ResourceRepository(session)
        self.accounts = CloudAccountRepository(session)
        self.alerts = AlertRepository(session)
        self.audit = AuditRepository(session)
        self.costs = CostRepository(session)

    def overview(self, usage_hours: int = 24) -> DashboardOverview:
        active = self.resources.active()
        compute_values = {t.value for t in COMPUTE_TYPES}
        running = sum(
            1
            for r in active
            if r.resource_type in compute_values and r.status == ResourceStatus.RUNNING
        )
        stopped = sum(
            1
            for r in active
            if r.resource_type in compute_values and r.status == ResourceStatus.STOPPED
        )
        storage = sum(1 for r in active if r.resource_type not in compute_values)

        accounts = self.accounts.list()
        health = AccountHealth(
            connected=sum(a.status == AccountStatus.CONNECTED for a in accounts),
            error=sum(a.status == AccountStatus.ERROR for a in accounts),
            pending=sum(a.status == AccountStatus.PENDING for a in accounts),
            last_sync_at=max(
                (a.last_synced_at for a in accounts if a.last_synced_at), default=None
            ),
        )

        latest = self.resources.latest_metrics()
        cpu = [m.cpu_percent for m in latest if m.cpu_percent is not None and m.cpu_percent > 0]
        mem = [
            m.memory_percent
            for m in latest
            if m.memory_percent is not None and m.memory_percent > 0
        ]
        series = [
            UsagePoint(
                timestamp=ts,
                avg_cpu_percent=round(c, 1) if c is not None else None,
                avg_memory_percent=round(m, 1) if m is not None else None,
                network_in_mb=round(float(ni), 1),
                network_out_mb=round(float(no), 1),
            )
            for ts, c, m, ni, no in self.resources.metric_series(
                utcnow() - timedelta(hours=usage_hours)
            )
        ]
        usage = UsageSummary(
            avg_cpu_percent=round(sum(cpu) / len(cpu), 1) if cpu else None,
            avg_memory_percent=round(sum(mem) / len(mem), 1) if mem else None,
            total_storage_gb=round(sum(m.storage_used_gb or 0 for m in latest), 1),
            high_cpu_resources=sum(1 for c in cpu if c >= HIGH_CPU_THRESHOLD),
            series=series,
        )

        def counts(column: str) -> list[CountItem]:
            return [CountItem(key=k, count=c) for k, c in self.resources.count_by(column)]

        recent_alerts = list(self.session.scalars(self.alerts.list_stmt("open", None).limit(5)))
        return DashboardOverview(
            total_resources=len(active),
            running_compute=running,
            stopped_compute=stopped,
            storage_resources=storage,
            accounts=health,
            by_provider=counts("provider"),
            by_status=counts("status"),
            by_type=counts("resource_type"),
            by_region=counts("region")[:8],
            usage=usage,
            month_to_date_cost=Decimal(
                str(round(self.costs.spend(month_start(utcnow().date())), 2))
            ),
            estimated_monthly_run_rate=Decimal(
                str(round(self.resources.running_cost_estimate(), 2))
            ),
            open_alerts=self.alerts.count_open(),
            critical_alerts=self.alerts.count_open(AlertSeverity.CRITICAL.value),
            recent_alerts=[AlertRead.model_validate(a) for a in recent_alerts],
            recent_activity=[AuditLogRead.model_validate(a) for a in self.audit.recent(10)],
        )
