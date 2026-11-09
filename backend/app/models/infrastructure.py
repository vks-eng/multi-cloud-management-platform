from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import ProvisioningAction, ProvisioningStatus


class ProvisioningRequest(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A Terraform-backed provisioning / decommissioning request and its full history."""

    __tablename__ = "provisioning_requests"

    cloud_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cloud_accounts.id", ondelete="CASCADE"), index=True, nullable=False
    )
    action: Mapped[str] = mapped_column(
        String(10), nullable=False, default=ProvisioningAction.CREATE
    )
    template_key: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_name: Mapped[str] = mapped_column(String(128), nullable=False)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ProvisioningStatus.PLANNED, index=True
    )
    rendered_hcl: Mapped[str] = mapped_column(Text, nullable=False)
    plan_output: Mapped[str] = mapped_column(Text, nullable=False, default="")
    plan_summary: Mapped[dict[str, int]] = mapped_column(JSONB, nullable=False, default=dict)
    plan_is_mock: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    apply_output: Mapped[str | None] = mapped_column(Text)
    # SHA-256 of the one-time confirmation token returned at plan time.
    confirmation_token_hash: Mapped[str | None] = mapped_column(String(64))
    confirmation_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    requested_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    confirmed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)
    target_resource_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("resources.id", ondelete="SET NULL")
    )
