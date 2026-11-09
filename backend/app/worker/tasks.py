"""Background tasks: inventory/cost synchronisation and budget evaluation."""

from __future__ import annotations

import logging
import uuid

from app.db.session import session_scope
from app.repositories.repos import CloudAccountRepository
from app.services.costs import CostService
from app.services.inventory import InventoryService
from app.worker.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="mcmp.sync_account", bind=True, max_retries=2, default_retry_delay=30)
def sync_account_task(self, job_id: str) -> str:  # type: ignore[no-untyped-def]
    with session_scope() as session:
        job = InventoryService(session).run_sync(uuid.UUID(job_id))
        return job.status


@celery_app.task(name="mcmp.sync_all_accounts")
def sync_all_accounts_task() -> int:
    with session_scope() as session:
        service = InventoryService(session)
        job_ids = [
            str(service.create_sync_job(account.id, None, trigger="scheduled").id)
            for account in CloudAccountRepository(session).list(active_only=True)
        ]
    for job_id in job_ids:
        sync_account_task.delay(job_id)
    return len(job_ids)


@celery_app.task(name="mcmp.evaluate_budgets")
def evaluate_budgets_task() -> int:
    with session_scope() as session:
        return len(CostService(session).evaluate_budgets())


def dispatch_sync(job_id: uuid.UUID) -> None:
    """Queue a sync job (runs inline when CELERY_TASK_ALWAYS_EAGER=true)."""
    sync_account_task.delay(str(job_id))
