"""Cost analytics, budgets and budget-threshold alerting."""

from __future__ import annotations

import calendar
import uuid
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from app.models import Budget, CostAlert
from app.models.enums import AlertCategory, AlertSeverity, CloudProvider
from app.repositories.repos import (
    BudgetRepository,
    CloudAccountRepository,
    CostAlertRepository,
    CostRepository,
)
from app.schemas.cost import (
    BudgetCreate,
    BudgetRead,
    BudgetUpdate,
    CostSummary,
    MonthlyTrendPoint,
    ProviderCost,
    ServiceCost,
)
from app.services.alerts import AlertService
from app.services.audit import AuditService, RequestContext


def month_start(d: date, back: int = 0) -> date:
    idx = d.year * 12 + (d.month - 1) - back
    return date(idx // 12, idx % 12 + 1, 1)


def _money(value: float | Decimal) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _change(current: float, previous: float) -> float | None:
    if previous <= 0:
        return None
    return round((current - previous) / previous * 100, 1)


class CostService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.costs = CostRepository(session)
        self.budgets = BudgetRepository(session)
        self.cost_alerts = CostAlertRepository(session)
        self.accounts = CloudAccountRepository(session)
        self.audit = AuditService(session)

    @staticmethod
    def today() -> date:
        return datetime.now(UTC).date()

    # -- analytics -----------------------------------------------------------------------
    def summary(self) -> CostSummary:
        today = self.today()
        current, previous = month_start(today), month_start(today, 1)
        rows = self.costs.totals_by_provider_month(previous)
        totals: dict[tuple[str, date], float] = {(p, m): a for p, m, a in rows}
        days = calendar.monthrange(today.year, today.month)[1]
        # Month-to-date spend is extrapolated so the comparison with last month is like-for-like.
        run_rate = days / max(today.day, 1)
        by_provider = []
        for provider in CloudProvider:
            cur = totals.get((provider.value, current), 0.0)
            prev = totals.get((provider.value, previous), 0.0)
            by_provider.append(
                ProviderCost(
                    provider=provider.value,
                    current_month=_money(cur),
                    previous_month=_money(prev),
                    change_percent=_change(cur * run_rate, prev),
                )
            )
        cur_total = sum(p.current_month for p in by_provider)
        prev_total = sum(p.previous_month for p in by_provider)
        forecast = Decimal(cur_total) * Decimal(days) / Decimal(max(today.day, 1))
        return CostSummary(
            current_month=_money(cur_total),
            previous_month=_money(prev_total),
            change_percent=_change(float(forecast), float(prev_total)),
            forecast_current_month=_money(forecast),
            by_provider=by_provider,
        )

    def trends(self, months: int = 6) -> list[MonthlyTrendPoint]:
        today = self.today()
        start = month_start(today, months - 1)
        points = {
            month_start(today, b): MonthlyTrendPoint(month=month_start(today, b))
            for b in range(months - 1, -1, -1)
        }
        for provider, month, amount in self.costs.totals_by_provider_month(start):
            point = points.get(month)
            if point is None or provider not in ("aws", "azure", "gcp"):
                continue
            setattr(point, provider, _money(amount))
        for point in points.values():
            point.total = _money(point.aws + point.azure + point.gcp)
        return list(points.values())

    def by_service(self, month: date | None = None) -> list[ServiceCost]:
        target = month_start(month or self.today())
        return [
            ServiceCost(provider=p, service=s, amount=_money(a))
            for p, s, a in self.costs.by_service(target)
        ]

    # -- budgets -------------------------------------------------------------------------
    def _spend_for(self, budget: Budget, month: date) -> float:
        return self.costs.spend(month, provider=budget.provider, account_id=budget.cloud_account_id)

    def to_read(self, budget: Budget) -> BudgetRead:
        spend = self._spend_for(budget, month_start(self.today()))
        limit = float(budget.monthly_limit)
        read = BudgetRead.model_validate(budget)
        read.current_spend = _money(spend)
        read.utilization_percent = round(spend / limit * 100, 1) if limit else 0.0
        return read

    def list_budgets(self) -> list[BudgetRead]:
        return [self.to_read(b) for b in self.budgets.list()]

    def create_budget(self, data: BudgetCreate, ctx: RequestContext) -> Budget:
        if data.cloud_account_id:
            self.accounts.get_or_404(data.cloud_account_id)
        budget = self.budgets.add(
            Budget(
                name=data.name,
                provider=data.provider.value if data.provider else None,
                cloud_account_id=data.cloud_account_id,
                monthly_limit=data.monthly_limit,
                alert_threshold_percent=data.alert_threshold_percent,
                created_by_id=ctx.user.id if ctx.user else None,
            )
        )
        self.audit.record(
            ctx,
            "budget.create",
            target_type="budget",
            target_id=budget.id,
            details={"name": budget.name, "limit": str(budget.monthly_limit)},
        )
        self.session.commit()
        self.evaluate_budgets()
        return budget

    def update_budget(
        self, budget_id: uuid.UUID, data: BudgetUpdate, ctx: RequestContext
    ) -> Budget:
        budget = self.budgets.get_or_404(budget_id)
        changes = data.model_dump(exclude_unset=True)
        for key, value in changes.items():
            setattr(budget, key, value)
        self.audit.record(
            ctx,
            "budget.update",
            target_type="budget",
            target_id=budget.id,
            details={k: str(v) for k, v in changes.items()},
        )
        self.session.commit()
        self.evaluate_budgets()
        return budget

    def delete_budget(self, budget_id: uuid.UUID, ctx: RequestContext) -> None:
        budget = self.budgets.get_or_404(budget_id)
        self.audit.record(
            ctx,
            "budget.delete",
            target_type="budget",
            target_id=budget.id,
            details={"name": budget.name},
        )
        self.budgets.delete(budget)
        self.session.commit()

    def evaluate_budgets(self) -> list[CostAlert]:
        """Create cost alert records for every threshold crossed this month (idempotent)."""
        month = month_start(self.today())
        created: list[CostAlert] = []
        alerts = AlertService(self.session)
        for budget in self.budgets.list(active_only=True):
            spend = self._spend_for(budget, month)
            limit = float(budget.monthly_limit)
            if limit <= 0:
                continue
            utilization = spend / limit * 100
            for threshold in sorted({budget.alert_threshold_percent, 100}):
                if utilization < threshold or self.cost_alerts.exists(budget.id, month, threshold):
                    continue
                severity = AlertSeverity.CRITICAL if threshold >= 100 else AlertSeverity.WARNING
                created.append(
                    self.cost_alerts.add(
                        CostAlert(
                            budget_id=budget.id,
                            period_month=month,
                            threshold_percent=threshold,
                            actual_amount=_money(spend),
                            budget_limit=budget.monthly_limit,
                            severity=severity.value,
                        )
                    )
                )
                alerts.raise_alert(
                    fingerprint=f"budget:{budget.id}:{month.isoformat()}:{threshold}",
                    severity=severity,
                    category=AlertCategory.COST,
                    title=f"Budget '{budget.name}' reached {threshold}%",
                    message=(
                        f"Month-to-date spend ${spend:,.2f} is {utilization:.1f}% of the "
                        f"${limit:,.2f} monthly budget."
                    ),
                    cloud_account_id=budget.cloud_account_id,
                )
        self.session.commit()
        return created
