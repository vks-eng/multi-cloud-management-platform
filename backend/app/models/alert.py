from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import AlertStatus


class Alert(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Operational alert (unhealthy resource, failed account connection, budget breach...)."""

    __tablename__ = "alerts"

    severity: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=AlertStatus.OPEN, index=True
    )
    # Deduplication key: an open alert with the same fingerprint is not raised twice.
    fingerprint: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    cloud_account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cloud_accounts.id", ondelete="CASCADE")
    )
    resource_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("resources.id", ondelete="CASCADE")
    )
    acknowledged_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
