"""Operational alerts with fingerprint-based de-duplication."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.core.errors import BusinessRuleError
from app.db.base import utcnow
from app.models import Alert
from app.models.enums import AlertCategory, AlertSeverity, AlertStatus
from app.repositories.repos import AlertRepository
from app.services.audit import AuditService, RequestContext


class AlertService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.alerts = AlertRepository(session)

    def raise_alert(
        self,
        *,
        fingerprint: str,
        severity: AlertSeverity,
        category: AlertCategory,
        title: str,
        message: str,
        cloud_account_id: uuid.UUID | None = None,
        resource_id: uuid.UUID | None = None,
    ) -> Alert:
        existing = self.alerts.open_by_fingerprint(fingerprint)
        if existing:
            existing.message = message
            existing.severity = severity.value
            existing.updated_at = utcnow()
            return existing
        return self.alerts.add(
            Alert(
                fingerprint=fingerprint,
                severity=severity.value,
                category=category.value,
                title=title,
                message=message,
                cloud_account_id=cloud_account_id,
                resource_id=resource_id,
                status=AlertStatus.OPEN.value,
            )
        )

    def resolve(self, fingerprint: str) -> None:
        existing = self.alerts.open_by_fingerprint(fingerprint)
        if existing:
            existing.status = AlertStatus.RESOLVED.value
            existing.resolved_at = utcnow()

    def resolve_missing(self, prefix: str, still_firing: set[str]) -> None:
        for alert in self.alerts.open_with_prefix(prefix):
            if alert.fingerprint not in still_firing:
                alert.status = AlertStatus.RESOLVED.value
                alert.resolved_at = utcnow()

    def transition(self, alert_id: uuid.UUID, target: AlertStatus, ctx: RequestContext) -> Alert:
        alert = self.alerts.get_or_404(alert_id)
        if alert.status == AlertStatus.RESOLVED:
            raise BusinessRuleError("Alert is already resolved")
        alert.status = target.value
        if target == AlertStatus.ACKNOWLEDGED and ctx.user:
            alert.acknowledged_by_id = ctx.user.id
        if target == AlertStatus.RESOLVED:
            alert.resolved_at = utcnow()
        AuditService(self.session).record(
            ctx,
            f"alert.{target.value}",
            target_type="alert",
            target_id=alert.id,
            details={"title": alert.title},
        )
        self.session.commit()
        return alert
