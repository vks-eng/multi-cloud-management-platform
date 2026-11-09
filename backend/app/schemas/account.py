from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, SecretStr, field_validator, model_validator

from app.models.enums import AccountStatus, CloudProvider, SyncStatus
from app.schemas.common import ORMModel

_EXTERNAL_ID_RULES: dict[CloudProvider, tuple[str, str]] = {
    CloudProvider.AWS: (r"^\d{12}$", "AWS account id must be 12 digits"),
    CloudProvider.AZURE: (
        r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
        "Azure subscription id must be a GUID",
    ),
    CloudProvider.GCP: (r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$", "Invalid GCP project id"),
}


class AwsCredentials(BaseModel):
    access_key_id: SecretStr = Field(description="IAM access key id (AKIA... / ASIA...)")
    secret_access_key: SecretStr
    session_token: SecretStr | None = None

    @field_validator("access_key_id")
    @classmethod
    def _key_format(cls, v: SecretStr) -> SecretStr:
        if not re.fullmatch(r"(AKIA|ASIA)[A-Z0-9]{12,20}", v.get_secret_value()):
            raise ValueError("access_key_id must look like an AWS access key id")
        return v


class AzureCredentials(BaseModel):
    tenant_id: SecretStr
    client_id: SecretStr
    client_secret: SecretStr


class GcpCredentials(BaseModel):
    service_account_json: SecretStr

    @field_validator("service_account_json")
    @classmethod
    def _valid_json(cls, v: SecretStr) -> SecretStr:
        try:
            data = json.loads(v.get_secret_value())
        except json.JSONDecodeError as exc:
            raise ValueError("service_account_json must be valid JSON") from exc
        if not isinstance(data, dict) or "client_email" not in data:
            raise ValueError("service_account_json must be a service account key (client_email)")
        return v


CREDENTIAL_MODELS: dict[CloudProvider, type[BaseModel]] = {
    CloudProvider.AWS: AwsCredentials,
    CloudProvider.AZURE: AzureCredentials,
    CloudProvider.GCP: GcpCredentials,
}


def parse_credentials(provider: CloudProvider, raw: dict[str, Any]) -> dict[str, str]:
    """Validate provider-specific credentials and return plain values for encryption."""
    model = CREDENTIAL_MODELS[provider].model_validate(raw)
    plain: dict[str, str] = {}
    for key, value in model:
        if value is None:
            continue
        plain[key] = value.get_secret_value() if isinstance(value, SecretStr) else str(value)
    return plain


class CloudAccountCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    provider: CloudProvider
    external_id: str = Field(min_length=3, max_length=128)
    default_region: str = Field(min_length=2, max_length=64, pattern=r"^[a-z0-9-]+$")
    description: str | None = Field(default=None, max_length=1000)
    credentials: dict[str, Any] = Field(repr=False)

    @model_validator(mode="after")
    def _validate(self) -> CloudAccountCreate:
        pattern, message = _EXTERNAL_ID_RULES[self.provider]
        if not re.fullmatch(pattern, self.external_id):
            raise ValueError(message)
        return self


class CloudAccountUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    default_region: str | None = Field(
        default=None, min_length=2, max_length=64, pattern=r"^[a-z0-9-]+$"
    )
    description: str | None = Field(default=None, max_length=1000)
    is_active: bool | None = None


class CredentialRotate(BaseModel):
    credentials: dict[str, Any] = Field(repr=False)


class CloudAccountRead(ORMModel):
    """Public representation. Deliberately has no credential fields."""

    id: uuid.UUID
    name: str
    provider: CloudProvider
    external_id: str
    default_region: str
    description: str | None
    credential_hint: str | None
    credentials_rotated_at: datetime | None
    status: AccountStatus
    status_message: str | None
    last_validated_at: datetime | None
    last_synced_at: datetime | None
    is_active: bool
    created_at: datetime
    resource_count: int = 0


class ConnectionTestResult(BaseModel):
    ok: bool
    message: str
    identity: str | None = None
    adapter: str


class SyncJobRead(ORMModel):
    id: uuid.UUID
    cloud_account_id: uuid.UUID
    status: SyncStatus
    trigger: str
    started_at: datetime | None
    finished_at: datetime | None
    resources_found: int
    resources_created: int
    resources_updated: int
    resources_deleted: int
    error: str | None
    created_at: datetime
