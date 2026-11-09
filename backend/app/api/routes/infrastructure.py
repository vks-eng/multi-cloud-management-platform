from __future__ import annotations

import uuid
from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field

from app.api.deps import Ctx, DbSession, PageParams, require
from app.core.permissions import Permission
from app.infrastructure.catalog import TEMPLATES, TemplateSpec, get_template
from app.infrastructure.runner import TerraformRunner
from app.models import CloudAccount, ProvisioningRequest
from app.repositories.repos import CloudAccountRepository, ProvisioningRepository
from app.schemas.common import Page
from app.schemas.infrastructure import (
    DecommissionCreate,
    ProvisioningApply,
    ProvisioningCreate,
    ProvisioningPlanned,
    ProvisioningRead,
    TemplateParamRead,
    TemplatePreview,
    TemplateRead,
)
from app.services.provisioning import ProvisioningService

router = APIRouter(prefix="/infrastructure", tags=["Infrastructure (Terraform)"])
_read = Depends(require(Permission.INFRA_READ))
_plan = Depends(require(Permission.INFRA_PLAN))
_apply = Depends(require(Permission.INFRA_APPLY))


class TerraformStatus(BaseModel):
    binary_found: bool
    binary_path: str | None
    mode: str
    mock_reason: str | None
    apply_enabled: bool


class PreviewRequest(BaseModel):
    cloud_account_id: uuid.UUID
    parameters: dict[str, Any] = Field(default_factory=dict)


def _template_read(spec: TemplateSpec) -> TemplateRead:
    return TemplateRead(
        key=spec.key,
        provider=spec.provider.value,
        resource_type=spec.resource_type.value,
        title=spec.title,
        description=spec.description,
        terraform_resources=list(spec.terraform_resources),
        estimated_monthly_cost=spec.estimated_monthly_cost,
        params=[
            TemplateParamRead(**{**asdict(p), "options": list(p.options)}) for p in spec.params
        ],
    )


def _read_model(req: ProvisioningRequest, account: CloudAccount | None) -> dict[str, Any]:
    data = ProvisioningRead.model_validate(req).model_dump()
    data["account_name"] = account.name if account else None
    data["provider"] = account.provider if account else None
    return data


@router.get("/terraform", response_model=TerraformStatus, dependencies=[_read])
def terraform_status() -> TerraformStatus:
    runner = TerraformRunner()
    return TerraformStatus(
        binary_found=runner.binary_path() is not None,
        binary_path=runner.binary_path(),
        mode=runner.settings.terraform_mode,
        mock_reason=runner.mock_reason(),
        apply_enabled=runner.settings.terraform_apply_enabled,
    )


@router.get("/templates", response_model=list[TemplateRead], dependencies=[_read])
def list_templates(provider: str | None = None) -> list[TemplateRead]:
    return [_template_read(t) for t in TEMPLATES.values() if not provider or t.provider == provider]


@router.get("/templates/{key}", response_model=TemplateRead, dependencies=[_read])
def get_template_detail(key: str) -> TemplateRead:
    return _template_read(get_template(key))


@router.post("/templates/{key}/preview", response_model=TemplatePreview, dependencies=[_plan])
def preview_template(key: str, body: PreviewRequest, db: DbSession) -> TemplatePreview:
    """Render HCL without creating a request (no plan, nothing persisted)."""
    account = CloudAccountRepository(db).get_or_404(body.cloud_account_id)
    hcl = ProvisioningService(db).preview(key, body.parameters, account.external_id)
    return TemplatePreview(template_key=key, hcl=hcl)


@router.get("/provisioning", response_model=Page[ProvisioningRead], dependencies=[_read])
def list_requests(
    db: DbSession,
    page: PageParams,
    status_filter: str | None = Query(default=None, alias="status"),
    account_id: uuid.UUID | None = None,
) -> Page[ProvisioningRead]:
    repo = ProvisioningRepository(db)
    items, total = repo.paginate(repo.list_stmt(status_filter, account_id), page.limit, page.offset)
    accounts = {a.id: a for a in CloudAccountRepository(db).list()}
    return Page(
        items=[ProvisioningRead(**_read_model(r, accounts.get(r.cloud_account_id))) for r in items],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.post(
    "/provisioning",
    response_model=ProvisioningPlanned,
    status_code=status.HTTP_201_CREATED,
    dependencies=[_plan],
)
def create_plan(data: ProvisioningCreate, db: DbSession, ctx: Ctx) -> ProvisioningPlanned:
    """Render HCL and run `terraform plan` (or a labelled mock plan). Never applies.

    The response contains a one-time `confirmation_token` required by the apply endpoint.
    """
    req, token = ProvisioningService(db).plan(data, ctx)
    account = CloudAccountRepository(db).get(req.cloud_account_id)
    return ProvisioningPlanned(**_read_model(req, account), confirmation_token=token)


@router.post(
    "/decommission",
    response_model=ProvisioningPlanned,
    status_code=status.HTTP_201_CREATED,
    dependencies=[_plan],
)
def create_destroy_plan(data: DecommissionCreate, db: DbSession, ctx: Ctx) -> ProvisioningPlanned:
    req, token = ProvisioningService(db).plan_decommission(data, ctx)
    account = CloudAccountRepository(db).get(req.cloud_account_id)
    return ProvisioningPlanned(**_read_model(req, account), confirmation_token=token)


@router.get("/provisioning/{request_id}", response_model=ProvisioningRead, dependencies=[_read])
def get_request(request_id: uuid.UUID, db: DbSession) -> ProvisioningRead:
    req = ProvisioningRepository(db).get_or_404(request_id)
    return ProvisioningRead(
        **_read_model(req, CloudAccountRepository(db).get(req.cloud_account_id))
    )


@router.post(
    "/provisioning/{request_id}/apply", response_model=ProvisioningRead, dependencies=[_apply]
)
def apply_request(
    request_id: uuid.UUID, body: ProvisioningApply, db: DbSession, ctx: Ctx
) -> ProvisioningRead:
    """Apply a planned request after explicit confirmation (token + typed resource name)."""
    req = ProvisioningService(db).apply(request_id, body, ctx)
    return ProvisioningRead(
        **_read_model(req, CloudAccountRepository(db).get(req.cloud_account_id))
    )


@router.post(
    "/provisioning/{request_id}/cancel", response_model=ProvisioningRead, dependencies=[_plan]
)
def cancel_request(request_id: uuid.UUID, db: DbSession, ctx: Ctx) -> ProvisioningRead:
    req = ProvisioningService(db).cancel(request_id, ctx)
    return ProvisioningRead(
        **_read_model(req, CloudAccountRepository(db).get(req.cloud_account_id))
    )
