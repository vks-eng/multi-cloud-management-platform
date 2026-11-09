from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import AccountStatus, SyncStatus


class CloudAccount(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An AWS account, Azure subscription or GCP project."""

    __tablename__ = "cloud_accounts"
    __table_args__ = (UniqueConstraint("provider", "external_id", name="uq_cloud_accounts_ext"),)

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    provider: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    # AWS account id / Azure subscription id / GCP project id
    external_id: Mapped[str] = mapped_column(String(128), nullable=False)
    default_region: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    # Fernet token of the JSON-serialised credentials. Never exposed via the API.
    encrypted_credentials: Mapped[str] = mapped_column(Text, nullable=False)
    # Non-secret hint shown in the UI, e.g. "AKIA********WXYZ".
    credential_hint: Mapped[str | None] = mapped_column(String(64))
    credentials_rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=AccountStatus.PENDING)
    status_message: Mapped[str | None] = mapped_column(Text)
    last_validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Adapter-scoped state. Used by the mock adapter to persist simulated provisioning.
    provider_state: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )


class SyncJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A single inventory/cost synchronisation run for one cloud account."""

    __tablename__ = "sync_jobs"

    cloud_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cloud_accounts.id", ondelete="CASCADE"), index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=SyncStatus.QUEUED)
    trigger: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")
    triggered_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resources_found: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    resources_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    resources_updated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    resources_deleted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text)
