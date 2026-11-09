"""Concrete repositories with the domain-specific queries used by the service layer."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import date, datetime

from sqlalchemy import Select, delete, func, or_, select

from app.models import (
    Alert,
    AuditLog,
    Budget,
    CloudAccount,
    CostAlert,
    CostRecord,
    LoginEvent,
    ProvisioningRequest,
    Resource,
    ResourceChange,
    ResourceMetric,
    SyncJob,
    User,
)
from app.models.enums import AlertStatus, ResourceStatus
from app.repositories.base import Repository


class UserRepository(Repository[User]):
    model = User

    def get_by_email(self, email: str) -> User | None:
        return self.session.scalar(select(User).where(func.lower(User.email) == email.lower()))

    def count(self) -> int:
        return int(self.session.scalar(select(func.count(User.id))) or 0)

    def list(self, limit: int, offset: int, search: str | None = None) -> tuple[list[User], int]:
        stmt = select(User).order_by(User.created_at)
        if search:
            like = f"%{search.lower()}%"
            stmt = stmt.where(
                or_(func.lower(User.email).like(like), func.lower(User.full_name).like(like))
            )
        return self.paginate(stmt, limit, offset)


class CloudAccountRepository(Repository[CloudAccount]):
    model = CloudAccount

    def list(self, provider: str | None = None, active_only: bool = False) -> list[CloudAccount]:
        stmt = select(CloudAccount).order_by(CloudAccount.provider, CloudAccount.name)
        if provider:
            stmt = stmt.where(CloudAccount.provider == provider)
        if active_only:
            stmt = stmt.where(CloudAccount.is_active.is_(True))
        return list(self.session.scalars(stmt))

    def find_by_external(self, provider: str, external_id: str) -> CloudAccount | None:
        return self.session.scalar(
            select(CloudAccount).where(
                CloudAccount.provider == provider, CloudAccount.external_id == external_id
            )
        )

    def resource_counts(self) -> dict[uuid.UUID, int]:
        rows = self.session.execute(
            select(Resource.cloud_account_id, func.count(Resource.id))
            .where(Resource.deleted_at.is_(None))
            .group_by(Resource.cloud_account_id)
        )
        return {row[0]: row[1] for row in rows}


class SyncJobRepository(Repository[SyncJob]):
    model = SyncJob

    def list_for_account(self, account_id: uuid.UUID, limit: int = 20) -> list[SyncJob]:
        stmt = (
            select(SyncJob)
            .where(SyncJob.cloud_account_id == account_id)
            .order_by(SyncJob.created_at.desc())
            .limit(limit)
        )
        return list(self.session.scalars(stmt))


class ResourceRepository(Repository[Resource]):
    model = Resource

    def by_account(self, account_id: uuid.UUID) -> dict[str, Resource]:
        stmt = select(Resource).where(Resource.cloud_account_id == account_id)
        return {r.external_id: r for r in self.session.scalars(stmt)}

    def search_stmt(
        self,
        *,
        provider: str | None = None,
        resource_type: str | None = None,
        status: str | None = None,
        account_id: uuid.UUID | None = None,
        region: str | None = None,
        search: str | None = None,
        include_deleted: bool = False,
    ) -> Select[tuple[Resource]]:
        stmt = select(Resource)
        if not include_deleted:
            stmt = stmt.where(Resource.deleted_at.is_(None))
        if provider:
            stmt = stmt.where(Resource.provider == provider)
        if resource_type:
            stmt = stmt.where(Resource.resource_type == resource_type)
        if status:
            stmt = stmt.where(Resource.status == status)
        if account_id:
            stmt = stmt.where(Resource.cloud_account_id == account_id)
        if region:
            stmt = stmt.where(Resource.region == region)
        if search:
            like = f"%{search.lower()}%"
            stmt = stmt.where(
                or_(
                    func.lower(Resource.name).like(like),
                    func.lower(Resource.external_id).like(like),
                )
            )
        return stmt

    def active(self) -> list[Resource]:
        return list(self.session.scalars(select(Resource).where(Resource.deleted_at.is_(None))))

    def count_by(self, column: str) -> list[tuple[str, int]]:
        col = getattr(Resource, column)
        rows = self.session.execute(
            select(col, func.count(Resource.id))
            .where(Resource.deleted_at.is_(None))
            .group_by(col)
            .order_by(func.count(Resource.id).desc())
        )
        return [(str(r[0]), int(r[1])) for r in rows]

    def changes(
        self, resource_id: uuid.UUID | None, limit: int, offset: int
    ) -> tuple[list[tuple[ResourceChange, str]], int]:
        stmt = (
            select(ResourceChange, Resource.name)
            .join(Resource, Resource.id == ResourceChange.resource_id)
            .order_by(ResourceChange.created_at.desc())
        )
        if resource_id:
            stmt = stmt.where(ResourceChange.resource_id == resource_id)
        total = self.session.scalar(
            select(func.count()).select_from(stmt.order_by(None).subquery())
        )
        rows = [(r[0], r[1]) for r in self.session.execute(stmt.limit(limit).offset(offset))]
        return rows, int(total or 0)

    def metrics(self, resource_id: uuid.UUID, since: datetime) -> list[ResourceMetric]:
        stmt = (
            select(ResourceMetric)
            .where(ResourceMetric.resource_id == resource_id, ResourceMetric.captured_at >= since)
            .order_by(ResourceMetric.captured_at)
        )
        return list(self.session.scalars(stmt))

    def latest_metrics(self) -> list[ResourceMetric]:
        """Most recent metric sample for every active resource."""
        sub = (
            select(ResourceMetric.resource_id, func.max(ResourceMetric.captured_at).label("ts"))
            .group_by(ResourceMetric.resource_id)
            .subquery()
        )
        stmt = (
            select(ResourceMetric)
            .join(
                sub,
                (sub.c.resource_id == ResourceMetric.resource_id)
                & (sub.c.ts == ResourceMetric.captured_at),
            )
            .join(Resource, Resource.id == ResourceMetric.resource_id)
            .where(Resource.deleted_at.is_(None))
        )
        return list(self.session.scalars(stmt))

    def metric_series(
        self, since: datetime
    ) -> Sequence[tuple[datetime, float | None, float | None, float, float]]:
        bucket = func.date_trunc("hour", ResourceMetric.captured_at)
        stmt = (
            select(
                bucket,
                func.avg(ResourceMetric.cpu_percent),
                func.avg(ResourceMetric.memory_percent),
                func.coalesce(func.sum(ResourceMetric.network_in_mb), 0),
                func.coalesce(func.sum(ResourceMetric.network_out_mb), 0),
            )
            .where(ResourceMetric.captured_at >= since)
            .group_by(bucket)
            .order_by(bucket)
        )
        return [tuple(r) for r in self.session.execute(stmt)]  # type: ignore[misc]

    def running_cost_estimate(self) -> float:
        value = self.session.scalar(
            select(func.coalesce(func.sum(Resource.monthly_cost_estimate), 0)).where(
                Resource.deleted_at.is_(None),
                Resource.status.notin_([ResourceStatus.TERMINATED, ResourceStatus.DELETED]),
            )
        )
        return float(value or 0)


class ProvisioningRepository(Repository[ProvisioningRequest]):
    model = ProvisioningRequest

    def list_stmt(
        self, status: str | None = None, account_id: uuid.UUID | None = None
    ) -> Select[tuple[ProvisioningRequest]]:
        stmt = select(ProvisioningRequest).order_by(ProvisioningRequest.created_at.desc())
        if status:
            stmt = stmt.where(ProvisioningRequest.status == status)
        if account_id:
            stmt = stmt.where(ProvisioningRequest.cloud_account_id == account_id)
        return stmt


class CostRepository(Repository[CostRecord]):
    model = CostRecord

    def replace_for_account(self, account_id: uuid.UUID, months: Sequence[date]) -> None:
        self.session.execute(
            delete(CostRecord).where(
                CostRecord.cloud_account_id == account_id, CostRecord.period_month.in_(months)
            )
        )

    def totals_by_provider_month(self, since: date) -> list[tuple[str, date, float]]:
        stmt = (
            select(CostRecord.provider, CostRecord.period_month, func.sum(CostRecord.amount))
            .where(CostRecord.period_month >= since)
            .group_by(CostRecord.provider, CostRecord.period_month)
            .order_by(CostRecord.period_month)
        )
        return [(r[0], r[1], float(r[2])) for r in self.session.execute(stmt)]

    def by_service(self, month: date) -> list[tuple[str, str, float]]:
        stmt = (
            select(CostRecord.provider, CostRecord.service, func.sum(CostRecord.amount))
            .where(CostRecord.period_month == month)
            .group_by(CostRecord.provider, CostRecord.service)
            .order_by(func.sum(CostRecord.amount).desc())
        )
        return [(r[0], r[1], float(r[2])) for r in self.session.execute(stmt)]

    def spend(
        self, month: date, provider: str | None = None, account_id: uuid.UUID | None = None
    ) -> float:
        stmt = select(func.coalesce(func.sum(CostRecord.amount), 0)).where(
            CostRecord.period_month == month
        )
        if provider:
            stmt = stmt.where(CostRecord.provider == provider)
        if account_id:
            stmt = stmt.where(CostRecord.cloud_account_id == account_id)
        return float(self.session.scalar(stmt) or 0)


class BudgetRepository(Repository[Budget]):
    model = Budget

    def list(self, active_only: bool = False) -> list[Budget]:
        stmt = select(Budget).order_by(Budget.name)
        if active_only:
            stmt = stmt.where(Budget.is_active.is_(True))
        return list(self.session.scalars(stmt))


class CostAlertRepository(Repository[CostAlert]):
    model = CostAlert

    def exists(self, budget_id: uuid.UUID, month: date, threshold: int) -> bool:
        return (
            self.session.scalar(
                select(CostAlert.id).where(
                    CostAlert.budget_id == budget_id,
                    CostAlert.period_month == month,
                    CostAlert.threshold_percent == threshold,
                )
            )
            is not None
        )

    def list_with_budget(self, limit: int, offset: int) -> tuple[list[tuple[CostAlert, str]], int]:
        stmt = (
            select(CostAlert, Budget.name)
            .join(Budget, Budget.id == CostAlert.budget_id)
            .order_by(CostAlert.created_at.desc())
        )
        total = self.session.scalar(select(func.count(CostAlert.id)))
        rows = [(r[0], r[1]) for r in self.session.execute(stmt.limit(limit).offset(offset))]
        return rows, int(total or 0)


class AlertRepository(Repository[Alert]):
    model = Alert

    def open_by_fingerprint(self, fingerprint: str) -> Alert | None:
        return self.session.scalar(
            select(Alert).where(
                Alert.fingerprint == fingerprint, Alert.status != AlertStatus.RESOLVED
            )
        )

    def open_with_prefix(self, prefix: str) -> list[Alert]:
        return list(
            self.session.scalars(
                select(Alert).where(
                    Alert.fingerprint.like(f"{prefix}%"), Alert.status != AlertStatus.RESOLVED
                )
            )
        )

    def list_stmt(self, status: str | None, severity: str | None) -> Select[tuple[Alert]]:
        stmt = select(Alert).order_by(Alert.created_at.desc())
        if status:
            stmt = stmt.where(Alert.status == status)
        if severity:
            stmt = stmt.where(Alert.severity == severity)
        return stmt

    def count_open(self, severity: str | None = None) -> int:
        stmt = select(func.count(Alert.id)).where(Alert.status != AlertStatus.RESOLVED)
        if severity:
            stmt = stmt.where(Alert.severity == severity)
        return int(self.session.scalar(stmt) or 0)


class AuditRepository(Repository[AuditLog]):
    model = AuditLog

    def list_stmt(
        self,
        action: str | None = None,
        actor_id: uuid.UUID | None = None,
        target_type: str | None = None,
        status: str | None = None,
    ) -> Select[tuple[AuditLog]]:
        stmt = select(AuditLog).order_by(AuditLog.created_at.desc())
        if action:
            stmt = stmt.where(AuditLog.action.like(f"{action}%"))
        if actor_id:
            stmt = stmt.where(AuditLog.actor_id == actor_id)
        if target_type:
            stmt = stmt.where(AuditLog.target_type == target_type)
        if status:
            stmt = stmt.where(AuditLog.status == status)
        return stmt

    def recent(self, limit: int = 10) -> list[AuditLog]:
        return list(
            self.session.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit))
        )


class LoginEventRepository(Repository[LoginEvent]):
    model = LoginEvent

    def list_stmt(
        self, user_id: uuid.UUID | None = None, success: bool | None = None
    ) -> Select[tuple[LoginEvent]]:
        stmt = select(LoginEvent).order_by(LoginEvent.created_at.desc())
        if user_id:
            stmt = stmt.where(LoginEvent.user_id == user_id)
        if success is not None:
            stmt = stmt.where(LoginEvent.success.is_(success))
        return stmt
