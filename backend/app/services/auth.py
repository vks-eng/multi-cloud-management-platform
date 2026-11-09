"""Authentication, registration, profile and user administration."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import (
    AuthenticationError,
    BusinessRuleError,
    ConflictError,
    PermissionDeniedError,
)
from app.core.permissions import Role
from app.core.security import create_access_token, hash_password, verify_password
from app.db.base import utcnow
from app.models import LoginEvent, User
from app.models.enums import AuditStatus
from app.repositories.repos import LoginEventRepository, UserRepository
from app.schemas.user import (
    PasswordChange,
    ProfileUpdate,
    UserAdminUpdate,
    UserCreateByAdmin,
    UserRegister,
)
from app.services.audit import AuditService, RequestContext

# A fixed hash used to keep login timing similar for unknown e-mails (user enumeration).
_DUMMY_HASH = hash_password("timing-equaliser-not-a-real-password-1")


class AuthService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.logins = LoginEventRepository(session)
        self.audit = AuditService(session)

    def register(self, data: UserRegister, ctx: RequestContext) -> User:
        settings = get_settings()
        is_first_user = self.users.count() == 0
        if not settings.allow_self_registration and not is_first_user:
            raise PermissionDeniedError("Self-registration is disabled; ask an administrator")
        if self.users.get_by_email(data.email):
            raise ConflictError("An account with this e-mail already exists")
        # Bootstrap: the very first user becomes the administrator.
        role = Role.ADMIN if is_first_user else Role.VIEWER
        user = self.users.add(
            User(
                email=data.email.lower(),
                full_name=data.full_name.strip(),
                hashed_password=hash_password(data.password),
                role=role.value,
            )
        )
        self.audit.record(
            RequestContext(user=user, ip_address=ctx.ip_address),
            "user.register",
            target_type="user",
            target_id=user.id,
            details={"role": role.value, "bootstrap_admin": is_first_user},
        )
        self.session.commit()
        return user

    def authenticate(self, email: str, password: str, ctx: RequestContext) -> tuple[User, str]:
        user = self.users.get_by_email(email)
        reason: str | None = None
        if user is None:
            verify_password(password, _DUMMY_HASH)
            reason = "unknown_email"
        elif not verify_password(password, user.hashed_password):
            reason = "bad_password"
        elif not user.is_active:
            reason = "inactive"

        self.logins.add(
            LoginEvent(
                user_id=user.id if user else None,
                email=email.lower(),
                success=reason is None,
                failure_reason=reason,
                ip_address=ctx.ip_address,
                user_agent=(ctx.user_agent or "")[:400] or None,
            )
        )
        if reason is not None or user is None:
            self.audit.record(
                ctx,
                "auth.login",
                target_type="user",
                status=AuditStatus.FAILURE,
                actor_email=email.lower(),
                details={"reason": reason},
            )
            self.session.commit()
            raise AuthenticationError("Incorrect e-mail or password")

        user.last_login_at = utcnow()
        self.audit.record(
            RequestContext(user=user, ip_address=ctx.ip_address),
            "auth.login",
            target_type="user",
            target_id=user.id,
        )
        self.session.commit()
        return user, create_access_token(user.id, user.role)

    def update_profile(self, user: User, data: ProfileUpdate, ctx: RequestContext) -> User:
        changes = data.model_dump(exclude_unset=True, exclude_none=True)
        for key, value in changes.items():
            setattr(user, key, value)
        self.audit.record(
            ctx,
            "user.profile_update",
            target_type="user",
            target_id=user.id,
            details={"fields": sorted(changes)},
        )
        self.session.commit()
        return user

    def change_password(self, user: User, data: PasswordChange, ctx: RequestContext) -> None:
        if not verify_password(data.current_password, user.hashed_password):
            self.audit.record(
                ctx,
                "user.password_change",
                target_type="user",
                target_id=user.id,
                status=AuditStatus.FAILURE,
                details={"reason": "bad_current_password"},
            )
            self.session.commit()
            raise BusinessRuleError("Current password is incorrect")
        user.hashed_password = hash_password(data.new_password)
        self.audit.record(ctx, "user.password_change", target_type="user", target_id=user.id)
        self.session.commit()

    # -- administration ----------------------------------------------------------------
    def create_user(self, data: UserCreateByAdmin, ctx: RequestContext) -> User:
        if self.users.get_by_email(data.email):
            raise ConflictError("An account with this e-mail already exists")
        user = self.users.add(
            User(
                email=data.email.lower(),
                full_name=data.full_name.strip(),
                hashed_password=hash_password(data.password),
                role=data.role.value,
            )
        )
        self.audit.record(
            ctx,
            "user.create",
            target_type="user",
            target_id=user.id,
            details={"email": user.email, "role": user.role},
        )
        self.session.commit()
        return user

    def admin_update(self, user_id: uuid.UUID, data: UserAdminUpdate, ctx: RequestContext) -> User:
        user = self.users.get_or_404(user_id)
        actor = ctx.user
        if (
            actor
            and actor.id == user.id
            and ((data.role is not None and data.role != Role.ADMIN) or data.is_active is False)
        ):
            raise BusinessRuleError("You cannot demote or deactivate your own account")
        before = {"role": user.role, "is_active": user.is_active}
        if data.role is not None:
            user.role = data.role.value
        if data.is_active is not None:
            user.is_active = data.is_active
        self.audit.record(
            ctx,
            "user.admin_update",
            target_type="user",
            target_id=user.id,
            details={"before": before, "after": {"role": user.role, "is_active": user.is_active}},
        )
        self.session.commit()
        return user
