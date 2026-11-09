from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utcnow


class CostRecord(UUIDPrimaryKeyMixin, Base):
    """Monthly cost per account and service, as reported by the provider."""

    __tablename__ = "cost_records"
    __table_args__ = (
        UniqueConstraint("cloud_account_id", "service", "period_month", name="uq_cost_records_key"),
    )

    cloud_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cloud_accounts.id", ondelete="CASCADE"), index=True, nullable=False
    )
    provider: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    service: Mapped[str] = mapped_column(String(80), nullable=False)
    period_month: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )


class Budget(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A monthly budget, optionally scoped to a provider or a single cloud account."""

    __tablename__ = "budgets"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    provider: Mapped[str | None] = mapped_column(String(10))
    cloud_account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cloud_accounts.id", ondelete="CASCADE")
    )
    monthly_limit: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    alert_threshold_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=80)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )


class CostAlert(UUIDPrimaryKeyMixin, Base):
    """Raised when spend for a budget crosses its threshold (or 100%) in a month."""

    __tablename__ = "cost_alerts"
    __table_args__ = (
        UniqueConstraint(
            "budget_id", "period_month", "threshold_percent", name="uq_cost_alerts_key"
        ),
    )

    budget_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("budgets.id", ondelete="CASCADE"), index=True, nullable=False
    )
    period_month: Mapped[date] = mapped_column(Date, nullable=False)
    threshold_percent: Mapped[int] = mapped_column(Integer, nullable=False)
    actual_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    budget_limit: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    severity: Mapped[str] = mapped_column(String(10), nullable=False)
    acknowledged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
