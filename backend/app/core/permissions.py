"""Role-based access control: roles, permissions and the role -> permission matrix."""

from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


class Permission(StrEnum):
    USERS_MANAGE = "users:manage"
    ACCOUNTS_READ = "accounts:read"
    ACCOUNTS_WRITE = "accounts:write"
    RESOURCES_READ = "resources:read"
    RESOURCES_SYNC = "resources:sync"
    INFRA_READ = "infra:read"
    INFRA_PLAN = "infra:plan"
    INFRA_APPLY = "infra:apply"
    COSTS_READ = "costs:read"
    BUDGETS_WRITE = "budgets:write"
    ALERTS_MANAGE = "alerts:manage"
    AUDIT_READ = "audit:read"


_READ_ONLY = {
    Permission.ACCOUNTS_READ,
    Permission.RESOURCES_READ,
    Permission.INFRA_READ,
    Permission.COSTS_READ,
}

ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.VIEWER: frozenset(_READ_ONLY),
    Role.OPERATOR: frozenset(
        _READ_ONLY
        | {
            Permission.RESOURCES_SYNC,
            Permission.INFRA_PLAN,
            Permission.INFRA_APPLY,
            Permission.ALERTS_MANAGE,
        }
    ),
    Role.ADMIN: frozenset(Permission),
}

ROLE_DESCRIPTIONS: dict[Role, str] = {
    Role.ADMIN: "Full access: users, cloud accounts and credentials, budgets, audit logs.",
    Role.OPERATOR: "Day-to-day operations: sync inventory, plan/apply provisioning, manage alerts.",
    Role.VIEWER: "Read-only access to accounts, inventory, infrastructure history and costs.",
}


def has_permission(role: str | Role, permission: Permission) -> bool:
    try:
        return permission in ROLE_PERMISSIONS[Role(role)]
    except ValueError:
        return False
