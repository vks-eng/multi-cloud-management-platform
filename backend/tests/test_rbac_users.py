from __future__ import annotations

import pytest

from tests.conftest import AWS_ACCOUNT

API = "/api/v1"


@pytest.mark.parametrize(
    ("role", "method", "path", "body", "expected"),
    [
        ("viewer", "post", "/cloud-accounts", AWS_ACCOUNT, 403),
        ("operator", "post", "/cloud-accounts", AWS_ACCOUNT, 403),
        ("viewer", "get", "/users", None, 403),
        ("operator", "get", "/users", None, 403),
        ("viewer", "get", "/audit/logs", None, 403),
        ("operator", "get", "/audit/logs", None, 403),
        ("viewer", "post", "/costs/budgets", {"name": "B1", "monthly_limit": "10"}, 403),
        (
            "viewer",
            "post",
            "/infrastructure/provisioning",
            {
                "cloud_account_id": "00000000-0000-0000-0000-000000000000",
                "template_key": "aws_s3_bucket",
            },
            403,
        ),
        ("viewer", "get", "/resources", None, 200),
        ("viewer", "get", "/costs/summary", None, 200),
        ("viewer", "get", "/dashboard/overview", None, 200),
        ("operator", "get", "/infrastructure/templates", None, 200),
        ("admin", "get", "/audit/logs", None, 200),
    ],
)
def test_role_permissions_enforced(client, auth_headers, role, method, path, body, expected):
    headers = auth_headers(role)
    resp = getattr(client, method)(
        f"{API}{path}", headers=headers, **({"json": body} if body else {})
    )
    assert resp.status_code == expected, resp.text
    if expected == 403:
        assert resp.json()["error"]["code"] == "permission_denied"


def test_roles_matrix(client, auth_headers):
    resp = client.get(f"{API}/users/roles", headers=auth_headers("viewer"))
    assert resp.status_code == 200
    roles = {r["role"]: set(r["permissions"]) for r in resp.json()}
    assert "users:manage" in roles["admin"]
    assert "infra:apply" in roles["operator"] and "users:manage" not in roles["operator"]
    assert all(
        not p.endswith(("write", "manage", "apply", "plan", "sync")) for p in roles["viewer"]
    )


def test_admin_user_management(client, auth_headers, db):
    from app.models import AuditLog

    headers = auth_headers("admin")
    created = client.post(
        f"{API}/users",
        headers=headers,
        json={
            "email": "new@example.com",
            "password": "Another-Pass-1",
            "full_name": "New Person",
            "role": "operator",
        },
    )
    assert created.status_code == 201
    user_id = created.json()["id"]

    listed = client.get(f"{API}/users?search=new@", headers=headers)
    assert listed.json()["total"] == 1

    updated = client.patch(
        f"{API}/users/{user_id}", headers=headers, json={"role": "viewer", "is_active": False}
    )
    assert updated.status_code == 200
    assert updated.json() | {"role": "viewer", "is_active": False} == updated.json()
    assert db.query(AuditLog).filter(AuditLog.action == "user.admin_update").count() == 1


def test_admin_cannot_demote_self(client, auth_headers):
    headers = auth_headers("admin")
    me = client.get(f"{API}/auth/me", headers=headers).json()
    resp = client.patch(f"{API}/users/{me['id']}", headers=headers, json={"role": "viewer"})
    assert resp.status_code == 422


def test_access_history_scoped_to_self_for_non_admins(client, auth_headers):
    admin = auth_headers("admin")
    viewer = auth_headers("viewer")
    own = client.get(f"{API}/audit/access-history", headers=viewer).json()
    assert own["total"] == 1
    assert {e["email"] for e in own["items"]} == {"viewer@example.com"}
    everyone = client.get(f"{API}/audit/access-history", headers=admin).json()
    assert everyone["total"] == 2
