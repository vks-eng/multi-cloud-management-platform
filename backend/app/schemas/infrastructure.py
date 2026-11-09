from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import ProvisioningAction, ProvisioningStatus
from app.schemas.common import ORMModel


class TemplateParamRead(BaseModel):
    key: str
    label: str
    type: str
    required: bool
    default: Any = None
    options: list[str] = []
    pattern: str | None = None
    description: str = ""
    minimum: int | None = None
    maximum: int | None = None


class TemplateRead(BaseModel):
    key: str
    provider: str
    resource_type: str
    title: str
    description: str
    terraform_resources: list[str]
    estimated_monthly_cost: str
    params: list[TemplateParamRead]


class TemplatePreview(BaseModel):
    template_key: str
    hcl: str


class ProvisioningCreate(BaseModel):
    cloud_account_id: uuid.UUID
    template_key: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class DecommissionCreate(BaseModel):
    resource_id: uuid.UUID


class ProvisioningApply(BaseModel):
    confirmation_token: str = Field(min_length=10, max_length=200)
    confirm_resource_name: str = Field(
        min_length=1,
        max_length=128,
        description="Must exactly match the resource name, as a typed safety check.",
    )


class ProvisioningRead(ORMModel):
    id: uuid.UUID
    cloud_account_id: uuid.UUID
    account_name: str | None = None
    provider: str | None = None
    action: ProvisioningAction
    template_key: str
    resource_name: str
    parameters: dict[str, Any]
    status: ProvisioningStatus
    rendered_hcl: str
    plan_output: str
    plan_summary: dict[str, int]
    plan_is_mock: bool
    apply_output: str | None
    confirmation_expires_at: datetime | None
    requested_by_id: uuid.UUID | None
    confirmed_by_id: uuid.UUID | None
    applied_at: datetime | None
    error: str | None
    target_resource_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class ProvisioningPlanned(ProvisioningRead):
    """Returned once, right after planning. The token is never retrievable again."""

    confirmation_token: str
