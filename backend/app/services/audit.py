"""Audit logging service. Every security-relevant mutation goes through `AuditService.record`."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.core.logging import redact
from app.models import AuditLog, User
from app.models.enums import AuditStatus

logger = logging.getLogger("app.audit")


@dataclass(slots=True)
class RequestContext:
    """Who is acting and from where; built by the API layer and passed to services."""

    user: User | None = None
    ip_address: str | None = None
    user_agent: str | None = None


class AuditService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def record(
        self,
        ctx: RequestContext | None,
        action: str,
        *,
        target_type: str | None = None,
        target_id: object | None = None,
        details: dict[str, Any] | None = None,
        status: AuditStatus = AuditStatus.SUCCESS,
        actor_email: str | None = None,
    ) -> AuditLog:
        user = ctx.user if ctx else None
        entry = AuditLog(
            actor_id=user.id if user else None,
            actor_email=actor_email or (user.email if user else None),
            action=action,
            target_type=target_type,
            target_id=str(target_id) if target_id is not None else None,
            status=status.value,
            details=redact(details or {}),
            ip_address=ctx.ip_address if ctx else None,
        )
        self.session.add(entry)
        self.session.flush()
        logger.info(
            "audit action=%s status=%s actor=%s target=%s:%s",
            action,
            status.value,
            entry.actor_email,
            target_type,
            entry.target_id,
        )
        return entry
