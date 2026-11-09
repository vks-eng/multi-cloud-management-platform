from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import Ctx, DbSession, require
from app.core.permissions import Permission
from app.db.base import utcnow
from app.models.enums import SyncStatus
from app.repositories.repos import SyncJobRepository
from app.schemas.account import (
    CloudAccountCreate,
    CloudAccountRead,
    CloudAccountUpdate,
    ConnectionTestResult,
    CredentialRotate,
    SyncJobRead,
)
from app.services.accounts import CloudAccountService
from app.services.inventory import InventoryService
from app.worker.tasks import dispatch_sync

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/cloud-accounts", tags=["Cloud Accounts"])
_read = Depends(require(Permission.ACCOUNTS_READ))
_write = Depends(require(Permission.ACCOUNTS_WRITE))
_sync = Depends(require(Permission.RESOURCES_SYNC))


def _read_model(account, count: int = 0) -> CloudAccountRead:  # type: ignore[no-untyped-def]
    model = CloudAccountRead.model_validate(account)
    model.resource_count = count
    return model


@router.get("", response_model=list[CloudAccountRead], dependencies=[_read])
def list_accounts(db: DbSession) -> list[CloudAccountRead]:
    return [_read_model(a, c) for a, c in CloudAccountService(db).list()]


@router.post(
    "", response_model=CloudAccountRead, status_code=status.HTTP_201_CREATED, dependencies=[_write]
)
def create_account(data: CloudAccountCreate, db: DbSession, ctx: Ctx) -> CloudAccountRead:
    """Register an account. Credentials are validated, Fernet-encrypted and never returned."""
    return _read_model(CloudAccountService(db).create(data, ctx))


@router.get("/{account_id}", response_model=CloudAccountRead, dependencies=[_read])
def get_account(account_id: uuid.UUID, db: DbSession) -> CloudAccountRead:
    service = CloudAccountService(db)
    account = service.get(account_id)
    return _read_model(account, service.accounts.resource_counts().get(account.id, 0))


@router.patch("/{account_id}", response_model=CloudAccountRead, dependencies=[_write])
def update_account(
    account_id: uuid.UUID, data: CloudAccountUpdate, db: DbSession, ctx: Ctx
) -> CloudAccountRead:
    return _read_model(CloudAccountService(db).update(account_id, data, ctx))


@router.put("/{account_id}/credentials", response_model=CloudAccountRead, dependencies=[_write])
def rotate_credentials(
    account_id: uuid.UUID, data: CredentialRotate, db: DbSession, ctx: Ctx
) -> CloudAccountRead:
    return _read_model(
        CloudAccountService(db).rotate_credentials(account_id, data.credentials, ctx)
    )


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[_write])
def delete_account(account_id: uuid.UUID, db: DbSession, ctx: Ctx) -> Response:
    CloudAccountService(db).delete(account_id, ctx)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{account_id}/validate", response_model=ConnectionTestResult, dependencies=[_write])
def validate_account(account_id: uuid.UUID, db: DbSession, ctx: Ctx) -> ConnectionTestResult:
    return CloudAccountService(db).validate(account_id, ctx)


@router.post(
    "/{account_id}/sync",
    response_model=SyncJobRead,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[_sync],
)
def trigger_sync(account_id: uuid.UUID, db: DbSession, ctx: Ctx) -> SyncJobRead:
    """Queue an inventory + cost sync. Executes inline when Celery runs in eager mode."""
    job = InventoryService(db).create_sync_job(account_id, ctx)
    try:
        dispatch_sync(job.id)
    except Exception as exc:  # broker unreachable
        logger.error("Could not enqueue sync job %s: %s", job.id, type(exc).__name__)
        job.status = SyncStatus.FAILED.value
        job.error = "Task queue unavailable"
        job.finished_at = utcnow()
        db.commit()
    db.expire_all()
    return SyncJobRead.model_validate(SyncJobRepository(db).get_or_404(job.id))


@router.get("/{account_id}/sync-jobs", response_model=list[SyncJobRead], dependencies=[_read])
def list_sync_jobs(account_id: uuid.UUID, db: DbSession) -> list[SyncJobRead]:
    CloudAccountService(db).get(account_id)
    return [
        SyncJobRead.model_validate(j) for j in SyncJobRepository(db).list_for_account(account_id)
    ]


@router.get("/sync-jobs/{job_id}", response_model=SyncJobRead, dependencies=[_read])
def get_sync_job(job_id: uuid.UUID, db: DbSession) -> SyncJobRead:
    return SyncJobRead.model_validate(SyncJobRepository(db).get_or_404(job_id))
