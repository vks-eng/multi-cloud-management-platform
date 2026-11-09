from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from app.schemas.common import ORMModel


class AuditLogRead(ORMModel):
    id: uuid.UUID
    actor_id: uuid.UUID | None
    actor_email: str | None
    action: str
    target_type: str | None
    target_id: str | None
    status: str
    details: dict[str, Any]
    ip_address: str | None
    created_at: datetime


class LoginEventRead(ORMModel):
    id: uuid.UUID
    user_id: uuid.UUID | None
    email: str
    success: bool
    failure_reason: str | None
    ip_address: str | None
    user_agent: str | None
    created_at: datetime


class AlertRead(ORMModel):
    id: uuid.UUID
    severity: str
    category: str
    title: str
    message: str
    status: str
    cloud_account_id: uuid.UUID | None
    resource_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None
