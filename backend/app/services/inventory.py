"""Resource inventory: synchronisation (reconciliation) and read queries."""

from __future__ import annotations

import copy
import logging
import uuid
from datetime import timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.base import utcnow
from app.models import CloudAccount, Resource, ResourceChange, ResourceMetric, SyncJob
from app.models.enums import (
    AccountStatus,
    AlertCategory,
    AlertSeverity,
    AuditStatus,
    ChangeSource,
    ChangeType,
    ResourceStatus,
    SyncStatus,
)
from app.providers.base import DiscoveredResource
from app.repositories.repos import (
    CloudAccountRepository,
    CostRepository,
    ResourceRepository,
    SyncJobRepository,
)
from app.services.accounts import build_adapter
from app.services.alerts import AlertService
from app.services.audit import AuditService, RequestContext

logger = logging.getLogger(__name__)

HIGH_CPU_THRESHOLD = 85.0
_TRACKED_FIELDS = ("name", "region", "status", "attributes", "tags", "monthly_cost_estimate")


def _jsonable(value: Any) -> Any:
    return str(value) if isinstance(value, Decimal) else value


class InventoryService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.accounts = CloudAccountRepository(session)
        self.resources = ResourceRepository(session)
        self.jobs = SyncJobRepository(session)
        self.costs = CostRepository(session)
        self.alerts = AlertService(session)
        self.audit = AuditService(session)

    # -- job lifecycle ------------------------------------------------------------------
    def create_sync_job(
        self, account_id: uuid.UUID, ctx: RequestContext | None, trigger: str = "manual"
    ) -> SyncJob:
        account = self.accounts.get_or_404(account_id)
        job = self.jobs.add(
            SyncJob(
                cloud_account_id=account.id,
                status=SyncStatus.QUEUED.value,
                trigger=trigger,
                triggered_by_id=ctx.user.id if ctx and ctx.user else None,
            )
        )
        self.audit.record(
            ctx,
            "resource.sync_requested",
            target_type="cloud_account",
            target_id=account.id,
            details={"job_id": str(job.id), "trigger": trigger},
        )
        self.session.commit()
        return job

    def run_sync(self, job_id: uuid.UUID) -> SyncJob:
        job = self.jobs.get_or_404(job_id)
        account = self.accounts.get_or_404(job.cloud_account_id)
        job.status = SyncStatus.RUNNING.value
        job.started_at = utcnow()
        self.session.commit()
        try:
            adapter = build_adapter(account)
            discovered = adapter.list_resources()
            stats = self._reconcile(account, discovered)
            cost_items = adapter.get_monthly_costs(6)
            self._store_costs(account, cost_items)
            account.provider_state = copy.deepcopy(adapter.context.state)
        except Exception as exc:
            self.session.rollback()
            message = (
                exc.message if isinstance(exc, AppError) else f"{type(exc).__name__}: sync failed"
            )
            logger.warning("Sync failed for account %s: %s", account.id, message)
            job = self.jobs.get_or_404(job_id)
            account = self.accounts.get_or_404(job.cloud_account_id)
            job.status = SyncStatus.FAILED.value
            job.error = message
            job.finished_at = utcnow()
            account.status = AccountStatus.ERROR.value
            account.status_message = message
            self.alerts.raise_alert(
                fingerprint=f"account:{account.id}:sync",
                severity=AlertSeverity.CRITICAL,
                category=AlertCategory.ACCOUNT,
                title=f"Inventory sync failed for {account.name}",
                message=message,
                cloud_account_id=account.id,
            )
            self.audit.record(
                None,
                "resource.sync",
                target_type="cloud_account",
                target_id=account.id,
                status=AuditStatus.FAILURE,
                details={"job_id": str(job.id), "error": message},
            )
            self.session.commit()
            return job

        now = utcnow()
        account.last_synced_at = now
        account.status = AccountStatus.CONNECTED.value
        account.status_message = "Last sync succeeded"
        self.alerts.resolve(f"account:{account.id}:sync")
        job.status = SyncStatus.SUCCEEDED.value
        job.finished_at = now
        job.resources_found = len(discovered)
        job.resources_created, job.resources_updated, job.resources_deleted = stats
        self.audit.record(
            None,
            "resource.sync",
            target_type="cloud_account",
            target_id=account.id,
            details={
                "job_id": str(job.id),
                "found": len(discovered),
                "created": stats[0],
                "updated": stats[1],
                "deleted": stats[2],
            },
        )
        self.session.commit()

        # Budgets depend on fresh cost data.
        from app.services.costs import CostService

        CostService(self.session).evaluate_budgets()
        return job

    # -- reconciliation -------------------------------------------------------------------
    def _reconcile(
        self, account: CloudAccount, discovered: list[DiscoveredResource]
    ) -> tuple[int, int, int]:
        now = utcnow()
        existing = self.resources.by_account(account.id)
        seen: set[str] = set()
        created = updated = deleted = 0
        firing: set[str] = set()
        prefix = f"acct:{account.id}:res:"

        for item in discovered:
            seen.add(item.external_id)
            res = existing.get(item.external_id)
            if res is None or res.deleted_at is not None:
                if res is None:
                    res = Resource(
                        cloud_account_id=account.id,
                        provider=account.provider,
                        external_id=item.external_id,
                        first_seen_at=now,
                    )
                    self.session.add(res)
                self._apply(res, item)
                res.deleted_at = None
                res.last_seen_at = now
                self.session.flush()
                self.session.add(
                    ResourceChange(
                        resource_id=res.id,
                        change_type=ChangeType.CREATED.value,
                        source=ChangeSource.SYNC.value,
                        changes={"status": item.status, "region": item.region},
                        created_at=now,
                    )
                )
                created += 1
            else:
                diff = self._diff(res, item)
                self._apply(res, item)
                res.last_seen_at = now
                if diff:
                    change_type = (
                        ChangeType.STATUS_CHANGED if set(diff) == {"status"} else ChangeType.UPDATED
                    )
                    self.session.add(
                        ResourceChange(
                            resource_id=res.id,
                            change_type=change_type.value,
                            source=ChangeSource.SYNC.value,
                            changes=diff,
                            created_at=now,
                        )
                    )
                    updated += 1
            if item.usage:
                self.session.add(
                    ResourceMetric(
                        resource_id=res.id,
                        captured_at=now,
                        cpu_percent=item.usage.cpu_percent,
                        memory_percent=item.usage.memory_percent,
                        network_in_mb=item.usage.network_in_mb,
                        network_out_mb=item.usage.network_out_mb,
                        storage_used_gb=item.usage.storage_used_gb,
                    )
                )
            firing |= self._evaluate_resource_alerts(account, res, item, prefix)

        for ext_id, res in existing.items():
            if ext_id in seen or res.deleted_at is not None:
                continue
            previous = res.status
            res.status = ResourceStatus.DELETED.value
            res.deleted_at = now
            self.session.add(
                ResourceChange(
                    resource_id=res.id,
                    change_type=ChangeType.DELETED.value,
                    source=ChangeSource.SYNC.value,
                    changes={"status": {"from": previous, "to": ResourceStatus.DELETED.value}},
                    created_at=now,
                )
            )
            deleted += 1

        self.alerts.resolve_missing(prefix, firing)
        self.session.flush()
        return created, updated, deleted

    @staticmethod
    def _apply(res: Resource, item: DiscoveredResource) -> None:
        res.name = item.name
        res.resource_type = item.resource_type
        res.region = item.region
        res.status = item.status
        res.attributes = item.attributes
        res.tags = item.tags
        res.monthly_cost_estimate = item.monthly_cost_estimate
        if item.tags.get("managed_by") == "mcmp":
            res.managed_by_platform = True

    @staticmethod
    def _diff(res: Resource, item: DiscoveredResource) -> dict[str, Any]:
        diff: dict[str, Any] = {}
        for field in _TRACKED_FIELDS:
            old, new = getattr(res, field), getattr(item, field)
            if field == "monthly_cost_estimate":
                if Decimal(str(old)) == Decimal(str(new)):
                    continue
            elif old == new:
                continue
            diff[field] = {"from": _jsonable(old), "to": _jsonable(new)}
        return diff

    def _evaluate_resource_alerts(
        self, account: CloudAccount, res: Resource, item: DiscoveredResource, prefix: str
    ) -> set[str]:
        firing: set[str] = set()
        if item.usage and (item.usage.cpu_percent or 0) >= HIGH_CPU_THRESHOLD:
            fp = f"{prefix}{res.id}:cpu"
            firing.add(fp)
            self.alerts.raise_alert(
                fingerprint=fp,
                severity=AlertSeverity.WARNING,
                category=AlertCategory.RESOURCE,
                title=f"High CPU on {res.name}",
                message=f"CPU utilisation {item.usage.cpu_percent:.1f}% exceeds {HIGH_CPU_THRESHOLD:.0f}%",
                cloud_account_id=account.id,
                resource_id=res.id,
            )
        if item.attributes.get("public_access_blocked") is False:
            fp = f"{prefix}{res.id}:public"
            firing.add(fp)
            self.alerts.raise_alert(
                fingerprint=fp,
                severity=AlertSeverity.CRITICAL,
                category=AlertCategory.SECURITY,
                title=f"Public access not blocked on {res.name}",
                message="Storage resource allows public access. Enable public access blocking.",
                cloud_account_id=account.id,
                resource_id=res.id,
            )
        return firing

    def _store_costs(self, account: CloudAccount, items: list[Any]) -> None:
        if not items:
            return
        from app.models import CostRecord

        months = sorted({i.period_month for i in items})
        self.costs.replace_for_account(account.id, months)
        aggregated: dict[tuple[str, Any], Decimal] = {}
        for item in items:
            key = (item.service[:80], item.period_month)
            aggregated[key] = aggregated.get(key, Decimal("0")) + item.amount
        for (service, month), amount in aggregated.items():
            self.session.add(
                CostRecord(
                    cloud_account_id=account.id,
                    provider=account.provider,
                    service=service,
                    period_month=month,
                    amount=amount,
                )
            )
        self.session.flush()

    # -- reads ---------------------------------------------------------------------------
    def metrics(self, resource_id: uuid.UUID, hours: int) -> list[ResourceMetric]:
        self.resources.get_or_404(resource_id)
        return self.resources.metrics(resource_id, utcnow() - timedelta(hours=hours))
