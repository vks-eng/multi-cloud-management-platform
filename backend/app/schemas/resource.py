from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from app.schemas.common import ORMModel


class ResourceRead(ORMModel):
    id: uuid.UUID
    cloud_account_id: uuid.UUID
    account_name: str | None = None
    provider: str
    resource_type: str
    external_id: str
    name: str
    region: str
    status: str
    attributes: dict[str, Any]
    tags: dict[str, str]
    monthly_cost_estimate: Decimal
    managed_by_platform: bool
    first_seen_at: datetime
    last_seen_at: datetime
    deleted_at: datetime | None


class ResourceChangeRead(ORMModel):
    id: uuid.UUID
    resource_id: uuid.UUID
    resource_name: str | None = None
    change_type: str
    source: str
    changes: dict[str, Any]
    actor_id: uuid.UUID | None
    created_at: datetime


class ResourceMetricRead(ORMModel):
    captured_at: datetime
    cpu_percent: float | None
    memory_percent: float | None
    network_in_mb: float | None
    network_out_mb: float | None
    storage_used_gb: float | None
