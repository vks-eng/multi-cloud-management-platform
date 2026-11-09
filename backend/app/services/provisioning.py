"""Terraform provisioning workflow: render -> plan -> explicit confirmation -> apply.

Safety properties:
* Nothing is ever applied automatically. `plan` only returns a one-time confirmation token.
* `apply` requires that token (stored as a SHA-256 hash, expiring) AND the resource name typed
  by the user, plus the `infra:apply` permission. Every attempt (good or bad) is audited.
* Real `terraform apply` additionally requires TERRAFORM_APPLY_ENABLED=true.
"""

from __future__ import annotations

import copy
import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.crypto import decrypt_credentials
from app.core.errors import AppError, BusinessRuleError, PermissionDeniedError
from app.core.security import generate_confirmation_token, hash_token, tokens_match
from app.db.base import utcnow
from app.infrastructure.catalog import TEMPLATES, TemplateSpec, get_template, validate_parameters
from app.infrastructure.renderer import render_template
from app.infrastructure.runner import TerraformRunner, terraform_env
from app.models import ProvisioningRequest, Resource, ResourceChange
from app.models.enums import (
    AuditStatus,
    ChangeSource,
    ChangeType,
    ProvisioningAction,
    ProvisioningStatus,
    ResourceStatus,
)
from app.repositories.repos import (
    CloudAccountRepository,
    ProvisioningRepository,
    ResourceRepository,
)
from app.schemas.infrastructure import DecommissionCreate, ProvisioningApply, ProvisioningCreate
from app.services.accounts import build_adapter
from app.services.audit import AuditService, RequestContext


class ProvisioningService:
    def __init__(self, session: Session, runner: TerraformRunner | None = None) -> None:
        self.session = session
        self.settings = get_settings()
        self.runner = runner or TerraformRunner(self.settings)
        self.requests = ProvisioningRepository(session)
        self.accounts = CloudAccountRepository(session)
        self.resources = ResourceRepository(session)
        self.audit = AuditService(session)

    # -- planning ------------------------------------------------------------------------
    def preview(self, template_key: str, params: dict[str, Any], account_external_id: str) -> str:
        spec = get_template(template_key)
        return render_template(
            spec, validate_parameters(spec, params), account_external_id=account_external_id
        )

    def plan(
        self, data: ProvisioningCreate, ctx: RequestContext
    ) -> tuple[ProvisioningRequest, str]:
        account = self.accounts.get_or_404(data.cloud_account_id)
        spec = get_template(data.template_key)
        if spec.provider != account.provider:
            raise BusinessRuleError(
                f"Template '{spec.key}' targets {spec.provider.value} but the account is {account.provider}"
            )
        if not account.is_active:
            raise BusinessRuleError("Cloud account is disabled")
        params = validate_parameters(spec, data.parameters)
        hcl = render_template(spec, params, account_external_id=account.external_id)
        return self._plan(account, spec, ProvisioningAction.CREATE, params, hcl, ctx, None)

    def plan_decommission(
        self, data: DecommissionCreate, ctx: RequestContext
    ) -> tuple[ProvisioningRequest, str]:
        resource = self.resources.get_or_404(data.resource_id)
        if resource.deleted_at is not None:
            raise BusinessRuleError("Resource is already deleted")
        account = self.accounts.get_or_404(resource.cloud_account_id)
        if not self.runner.mock_reason():
            raise BusinessRuleError(
                "Decommissioning real resources requires the Terraform state that created them; "
                "run `terraform destroy` from your state backend instead."
            )
        spec = next(
            (t for t in TEMPLATES.values() if t.resource_type == resource.resource_type), None
        )
        if spec is None:
            raise BusinessRuleError(f"No template supports {resource.resource_type}")
        params: dict[str, Any] = {p.key: p.default for p in spec.params}
        params.update(name=resource.name, region=resource.region, tags={})
        if "instance_size" in params and resource.attributes.get("instance_size"):
            params["instance_size"] = resource.attributes["instance_size"]
        hcl = render_template(spec, params, account_external_id=account.external_id)
        return self._plan(account, spec, ProvisioningAction.DESTROY, params, hcl, ctx, resource.id)

    def _plan(
        self,
        account,
        spec: TemplateSpec,
        action: ProvisioningAction,
        params: dict[str, Any],
        hcl: str,
        ctx: RequestContext,
        target_id: uuid.UUID | None,
    ) -> tuple[ProvisioningRequest, str]:  # type: ignore[no-untyped-def]
        token = generate_confirmation_token()
        req = self.requests.add(
            ProvisioningRequest(
                cloud_account_id=account.id,
                action=action.value,
                template_key=spec.key,
                resource_name=params["name"],
                parameters=params,
                rendered_hcl=hcl,
                status=ProvisioningStatus.PLANNED.value,
                requested_by_id=ctx.user.id if ctx.user else None,
                target_resource_id=target_id,
            )
        )
        env = {}
        if not self.runner.mock_reason():
            env = terraform_env(
                account.provider, decrypt_credentials(account.encrypted_credentials)
            )
        try:
            result = self.runner.plan(str(req.id), hcl, action.value, env)
        except AppError as exc:
            req.status = ProvisioningStatus.FAILED.value
            req.error = exc.message
            req.plan_output = str(exc.details.get("output", ""))
            self.audit.record(
                ctx,
                f"provisioning.plan_{action.value}",
                target_type="provisioning",
                target_id=req.id,
                status=AuditStatus.FAILURE,
                details={"error": exc.message},
            )
            self.session.commit()
            raise
        req.plan_output = result.output
        req.plan_summary = result.summary
        req.plan_is_mock = result.is_mock
        req.confirmation_token_hash = hash_token(token)
        req.confirmation_expires_at = utcnow() + timedelta(
            minutes=self.settings.provisioning_confirmation_ttl_minutes
        )
        self.audit.record(
            ctx,
            f"provisioning.plan_{action.value}",
            target_type="provisioning",
            target_id=req.id,
            details={
                "template": spec.key,
                "resource_name": req.resource_name,
                "account_id": str(account.id),
                "summary": result.summary,
                "mock": result.is_mock,
            },
        )
        self.session.commit()
        return req, token

    # -- confirmation + apply --------------------------------------------------------------
    def apply(
        self, request_id: uuid.UUID, body: ProvisioningApply, ctx: RequestContext
    ) -> ProvisioningRequest:
        req = self.requests.get_or_404(request_id)
        if req.status != ProvisioningStatus.PLANNED:
            self._reject(req, ctx, f"not_planned:{req.status}")
            raise BusinessRuleError(
                f"Request is '{req.status}', only planned requests can be applied"
            )
        if req.confirmation_expires_at and req.confirmation_expires_at < utcnow():
            req.status = ProvisioningStatus.EXPIRED.value
            req.confirmation_token_hash = None
            self.audit.record(
                ctx,
                "provisioning.apply",
                target_type="provisioning",
                target_id=req.id,
                status=AuditStatus.FAILURE,
                details={"reason": "expired"},
            )
            self.session.commit()
            raise BusinessRuleError("Confirmation window expired; create a new plan")
        if not req.confirmation_token_hash or not tokens_match(
            body.confirmation_token, req.confirmation_token_hash
        ):
            self._reject(req, ctx, "invalid_token")
            raise PermissionDeniedError("Invalid confirmation token")
        if body.confirm_resource_name != req.resource_name:
            self._reject(req, ctx, "name_mismatch")
            raise BusinessRuleError("Typed resource name does not match the planned resource")

        req.status = ProvisioningStatus.APPLYING.value
        req.confirmed_by_id = ctx.user.id if ctx.user else None
        req.confirmation_token_hash = None  # one-time use
        self.session.commit()

        try:
            if req.plan_is_mock:
                req.apply_output = self._apply_simulated(req, ctx)
            else:
                account = self.accounts.get_or_404(req.cloud_account_id)
                env = terraform_env(
                    account.provider, decrypt_credentials(account.encrypted_credentials)
                )
                req.apply_output = self.runner.apply(str(req.id), env)
        except Exception as exc:
            self.session.rollback()
            req = self.requests.get_or_404(request_id)
            req.status = ProvisioningStatus.FAILED.value
            req.error = (
                exc.message if isinstance(exc, AppError) else f"{type(exc).__name__}: apply failed"
            )
            self.audit.record(
                ctx,
                "provisioning.apply",
                target_type="provisioning",
                target_id=req.id,
                status=AuditStatus.FAILURE,
                details={"error": req.error},
            )
            self.session.commit()
            return req

        req.status = ProvisioningStatus.APPLIED.value
        req.applied_at = utcnow()
        self.audit.record(
            ctx,
            "provisioning.apply",
            target_type="provisioning",
            target_id=req.id,
            details={
                "action": req.action,
                "resource_name": req.resource_name,
                "mock": req.plan_is_mock,
            },
        )
        self.session.commit()
        return req

    def _reject(self, req: ProvisioningRequest, ctx: RequestContext, reason: str) -> None:
        self.audit.record(
            ctx,
            "provisioning.apply",
            target_type="provisioning",
            target_id=req.id,
            status=AuditStatus.FAILURE,
            details={"reason": reason},
        )
        self.session.commit()

    def _apply_simulated(self, req: ProvisioningRequest, ctx: RequestContext) -> str:
        account = self.accounts.get_or_404(req.cloud_account_id)
        spec = get_template(req.template_key)
        adapter = build_adapter(account)
        now = utcnow()
        actor = ctx.user.id if ctx.user else None
        if req.action == ProvisioningAction.CREATE:
            item = adapter.provision(spec.resource_type, req.resource_name, req.parameters)
            res = self.resources.by_account(account.id).get(item.external_id)
            if res is None:
                res = Resource(
                    cloud_account_id=account.id,
                    provider=account.provider,
                    external_id=item.external_id,
                    first_seen_at=now,
                )
                self.session.add(res)
            res.name, res.resource_type, res.region = item.name, item.resource_type, item.region
            res.status, res.attributes, res.tags = item.status, item.attributes, item.tags
            res.monthly_cost_estimate = item.monthly_cost_estimate
            res.managed_by_platform = True
            res.last_seen_at, res.deleted_at = now, None
            self.session.flush()
            self.session.add(
                ResourceChange(
                    resource_id=res.id,
                    change_type=ChangeType.CREATED.value,
                    source=ChangeSource.PROVISIONING.value,
                    actor_id=actor,
                    created_at=now,
                    changes={"provisioning_request_id": str(req.id), "template": spec.key},
                )
            )
            req.target_resource_id = res.id
            summary = f"Apply complete! Resources: {req.plan_summary.get('add', 1)} added, 0 changed, 0 destroyed."
        else:
            res = self.resources.get_or_404(req.target_resource_id)  # type: ignore[arg-type]
            adapter.decommission(res.resource_type, res.external_id)
            previous = res.status
            res.status, res.deleted_at = ResourceStatus.DELETED.value, now
            self.session.add(
                ResourceChange(
                    resource_id=res.id,
                    change_type=ChangeType.DELETED.value,
                    source=ChangeSource.PROVISIONING.value,
                    actor_id=actor,
                    created_at=now,
                    changes={
                        "status": {"from": previous, "to": ResourceStatus.DELETED.value},
                        "provisioning_request_id": str(req.id),
                    },
                )
            )
            summary = (
                f"Destroy complete! Resources: {req.plan_summary.get('destroy', 1)} destroyed."
            )
        account.provider_state = copy.deepcopy(adapter.context.state)
        return f"[MOCK APPLY] Simulated by the {type(adapter).__name__}; no real cloud API was called.\n{summary}"

    def cancel(self, request_id: uuid.UUID, ctx: RequestContext) -> ProvisioningRequest:
        req = self.requests.get_or_404(request_id)
        if req.status != ProvisioningStatus.PLANNED:
            raise BusinessRuleError("Only planned requests can be cancelled")
        req.status = ProvisioningStatus.CANCELLED.value
        req.confirmation_token_hash = None
        self.audit.record(ctx, "provisioning.cancel", target_type="provisioning", target_id=req.id)
        self.session.commit()
        return req
