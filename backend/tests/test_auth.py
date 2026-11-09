from __future__ import annotations

from sqlalchemy import select

from tests.conftest import PASSWORD

API = "/api/v1"


def _register(client, email="first@example.com", password="Valid-Pass-123", name="First User"):
    return client.post(
        f"{API}/auth/register", json={"email": email, "password": password, "full_name": name}
    )


def test_first_registered_user_becomes_admin_then_viewer(client):
    first = _register(client)
    assert first.status_code == 201
    assert first.json()["role"] == "admin"
    assert "hashed_password" not in first.json()

    second = _register(client, email="second@example.com")
    assert second.status_code == 201
    assert second.json()["role"] == "viewer"


def test_register_duplicate_email_conflicts(client):
    _register(client)
    resp = _register(client, email="FIRST@example.com")
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "conflict"


def test_register_rejects_weak_password(client):
    resp = _register(client, password="onlyletters")
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"


def test_login_success_returns_token_and_records_access(client, db):
    from app.models import AuditLog, LoginEvent

    _register(client)
    resp = client.post(
        f"{API}/auth/login", json={"email": "first@example.com", "password": "Valid-Pass-123"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == "first@example.com"
    events = db.scalars(select(LoginEvent)).all()
    assert len(events) == 1 and events[0].success
    assert db.scalar(select(AuditLog).where(AuditLog.action == "auth.login")) is not None


def test_login_failure_is_generic_and_audited(client, db):
    from app.models import AuditLog, LoginEvent

    _register(client)
    bad_pw = client.post(
        f"{API}/auth/login", json={"email": "first@example.com", "password": "wrong-password-1"}
    )
    unknown = client.post(
        f"{API}/auth/login", json={"email": "nobody@example.com", "password": "wrong-password-1"}
    )
    assert bad_pw.status_code == unknown.status_code == 401
    assert bad_pw.json()["error"]["message"] == unknown.json()["error"]["message"]
    reasons = {e.failure_reason for e in db.scalars(select(LoginEvent)).all()}
    assert reasons == {"bad_password", "unknown_email"}
    failures = db.scalars(select(AuditLog).where(AuditLog.status == "failure")).all()
    assert len(failures) == 2


def test_inactive_user_cannot_login(client, make_user):
    make_user(email="sleepy@example.com", active=False)
    resp = client.post(
        f"{API}/auth/login", json={"email": "sleepy@example.com", "password": PASSWORD}
    )
    assert resp.status_code == 401


def test_oauth2_token_endpoint(client, make_user):
    make_user(email="form@example.com")
    resp = client.post(
        f"{API}/auth/token", data={"username": "form@example.com", "password": PASSWORD}
    )
    assert resp.status_code == 200
    assert resp.json()["access_token"]


def test_protected_endpoint_requires_valid_token(client):
    assert client.get(f"{API}/auth/me").status_code == 401
    resp = client.get(f"{API}/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert resp.status_code == 401
    assert resp.headers["www-authenticate"] == "Bearer"


def test_profile_update_and_password_change(client, auth_headers):
    headers = auth_headers("viewer")
    resp = client.patch(
        f"{API}/auth/me", json={"full_name": "New Name", "job_title": "SRE"}, headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["full_name"] == "New Name"
    assert resp.json()["job_title"] == "SRE"

    wrong = client.post(
        f"{API}/auth/me/password",
        json={"current_password": "nope-nope-1", "new_password": "Brand-New-Pass-9"},
        headers=headers,
    )
    assert wrong.status_code == 422

    ok = client.post(
        f"{API}/auth/me/password",
        json={"current_password": PASSWORD, "new_password": "Brand-New-Pass-9"},
        headers=headers,
    )
    assert ok.status_code == 200
    relogin = client.post(
        f"{API}/auth/login", json={"email": "viewer@example.com", "password": "Brand-New-Pass-9"}
    )
    assert relogin.status_code == 200


def test_expired_token_rejected(client, make_user):
    from app.core.security import create_access_token

    user = make_user(email="old@example.com")
    token = create_access_token(user.id, user.role, expires_minutes=-1)
    resp = client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
