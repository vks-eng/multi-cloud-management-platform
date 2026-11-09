"""Cloud account management and secure credential handling."""

from __future__ import annotations

import copy
import json
import uuid
from typing import Any

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.crypto import decrypt_credentials, encrypt_credentials, mask_secret
from app.core.errors import BusinessRuleError, ConflictError
from app.db.base import utcnow
from app.models import CloudAccount
from app.models.enums import AccountStatus, AlertCategory, AlertSeverity, AuditStatus, CloudProvider
from app.providers.base import AccountContext, CloudProviderAdapter
from app.providers.factory import get_adapter
from app.repositories.repos import CloudAccountRepository
from app.schemas.account import (
    CloudAccountCreate,
    CloudAccountUpdate,
    ConnectionTestResult,
    parse_credentials,
)
from app.services.alerts import AlertService
from app.services.audit import AuditService, RequestContext


def _credential_hint(provider: CloudProvider, creds: dict[str, str]) -> str:
    if provider == CloudProvider.AWS:
        key = creds.get("access_key_id", "")
        return f"{key[:4]}{mask_secret(key)}"
    if provider == CloudProvider.AZURE:
        return f"client {mask_secret(creds.get('client_id', ''))}"
    try:
        email = json.loads(creds.get("service_account_json", "{}")).get("client_email", "")
    except json.JSONDecodeError:
        email = ""
    return email[:64]


def _validated_credentials(provider: CloudProvider, raw: dict[str, Any]) -> dict[str, str]:
    try:
        return parse_credentials(provider, raw)
    except ValidationError as exc:
        fields = {".".join(str(p) for p in e["loc"]): e["msg"] for e in exc.errors()}
        raise BusinessRuleError("Invalid credentials payload", details={"fields": fields}) from None


def build_adapter(account: CloudAccount) -> CloudProviderAdapter:
    """Instantiate the configured adapter with decrypted credentials (kept in memory only)."""
    context = AccountContext(
        provider=CloudProvider(account.provider),
        external_id=account.external_id,
        default_region=account.default_region,
        # Deep copy: adapters mutate state; the service persists it back explicitly.
        state=copy.deepcopy(account.provider_state or {}),
    )
    return get_adapter(context, decrypt_credentials(account.encrypted_credentials))


class CloudAccountService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.accounts = CloudAccountRepository(session)
        self.audit = AuditService(session)
        self.alerts = AlertService(session)

    def list(self) -> list[tuple[CloudAccount, int]]:
        counts = self.accounts.resource_counts()
        return [(a, counts.get(a.id, 0)) for a in self.accounts.list()]

    def get(self, account_id: uuid.UUID) -> CloudAccount:
        return self.accounts.get_or_404(account_id)

    def create(self, data: CloudAccountCreate, ctx: RequestContext) -> CloudAccount:
        if self.accounts.find_by_external(data.provider, data.external_id):
            raise ConflictError("This cloud account is already registered")
        creds = _validated_credentials(data.provider, data.credentials)
        account = self.accounts.add(
            CloudAccount(
                name=data.name,
                provider=data.provider.value,
                external_id=data.external_id,
                default_region=data.default_region,
                description=data.description,
                encrypted_credentials=encrypt_credentials(creds),
                credential_hint=_credential_hint(data.provider, creds),
                credentials_rotated_at=utcnow(),
                status=AccountStatus.PENDING.value,
                created_by_id=ctx.user.id if ctx.user else None,
                provider_state={},
            )
        )
        self.audit.record(
            ctx,
            "cloud_account.create",
            target_type="cloud_account",
            target_id=account.id,
            details={
                "provider": account.provider,
                "external_id": account.external_id,
                "name": account.name,
            },
        )
        self.session.commit()
        return account

    def update(
        self, account_id: uuid.UUID, data: CloudAccountUpdate, ctx: RequestContext
    ) -> CloudAccount:
        account = self.get(account_id)
        changes = data.model_dump(exclude_unset=True)
        for key, value in changes.items():
            setattr(account, key, value)
        self.audit.record(
            ctx,
            "cloud_account.update",
            target_type="cloud_account",
            target_id=account.id,
            details={"changes": changes},
        )
        self.session.commit()
        return account

    def rotate_credentials(
        self, account_id: uuid.UUID, raw: dict[str, Any], ctx: RequestContext
    ) -> CloudAccount:
        account = self.get(account_id)
        provider = CloudProvider(account.provider)
        creds = _validated_credentials(provider, raw)
        account.encrypted_credentials = encrypt_credentials(creds)
        account.credential_hint = _credential_hint(provider, creds)
        account.credentials_rotated_at = utcnow()
        account.status = AccountStatus.PENDING.value
        account.status_message = "Credentials rotated; validation pending"
        self.audit.record(
            ctx,
            "cloud_account.credentials_rotate",
            target_type="cloud_account",
            target_id=account.id,
        )
        self.session.commit()
        return account

    def delete(self, account_id: uuid.UUID, ctx: RequestContext) -> None:
        account = self.get(account_id)
        self.audit.record(
            ctx,
            "cloud_account.delete",
            target_type="cloud_account",
            target_id=account.id,
            details={"provider": account.provider, "external_id": account.external_id},
        )
        self.accounts.delete(account)
        self.session.commit()

    def validate(self, account_id: uuid.UUID, ctx: RequestContext | None) -> ConnectionTestResult:
        account = self.get(account_id)
        adapter = build_adapter(account)
        result = adapter.validate_connection()
        account.last_validated_at = utcnow()
        account.status = (AccountStatus.CONNECTED if result.ok else AccountStatus.ERROR).value
        account.status_message = result.message
        fingerprint = f"account:{account.id}:connection"
        if result.ok:
            self.alerts.resolve(fingerprint)
        else:
            self.alerts.raise_alert(
                fingerprint=fingerprint,
                severity=AlertSeverity.CRITICAL,
                category=AlertCategory.ACCOUNT,
                title=f"Connection failed for {account.name}",
                message=result.message,
                cloud_account_id=account.id,
            )
        self.audit.record(
            ctx,
            "cloud_account.validate",
            target_type="cloud_account",
            target_id=account.id,
            status=AuditStatus.SUCCESS if result.ok else AuditStatus.FAILURE,
            details={"message": result.message},
        )
        self.session.commit()
        return ConnectionTestResult(
            ok=result.ok,
            message=result.message,
            identity=result.identity,
            adapter=type(adapter).__name__,
        )
