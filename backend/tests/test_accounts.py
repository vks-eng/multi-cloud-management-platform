from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from tests.conftest import AWS_ACCOUNT, AZURE_ACCOUNT, GCP_ACCOUNT

API = "/api/v1"
SECRETS = ("super-secret-value", "azure-secret-value", "gcp-secret-value", "AKIATESTKEY00001")


@pytest.mark.parametrize("payload", [AWS_ACCOUNT, AZURE_ACCOUNT, GCP_ACCOUNT])
def test_create_account_never_exposes_credentials(
    client, auth_headers, create_account, db, payload
):
    from app.core.crypto import decrypt_credentials
    from app.models import AuditLog, CloudAccount

    headers = auth_headers("admin")
    body = create_account(headers, payload)
    assert body["status"] == "pending"
    assert "credentials" not in body and "encrypted_credentials" not in body
    raw = json.dumps(body)
    assert not any(secret in raw for secret in SECRETS)

    listed = client.get(f"{API}/cloud-accounts", headers=headers).text
    assert not any(secret in listed for secret in SECRETS)

    stored = db.scalar(select(CloudAccount))
    assert not any(secret in stored.encrypted_credentials for secret in SECRETS)
    decrypted = decrypt_credentials(stored.encrypted_credentials)
    assert set(decrypted) == set(payload["credentials"])

    audit = json.dumps([a.details for a in db.scalars(select(AuditLog)).all()])
    assert not any(secret in audit for secret in SECRETS)


def test_credential_hint_is_masked(auth_headers, create_account):
    body = create_account(auth_headers("admin"))
    assert body["credential_hint"].startswith("AKIA")
    assert "********" in body["credential_hint"]
    assert body["credential_hint"] != AWS_ACCOUNT["credentials"]["access_key_id"]


@pytest.mark.parametrize(
    ("override", "status"),
    [
        ({"external_id": "12345"}, 422),
        ({"provider": "azure"}, 422),  # AWS-style id is not a GUID
        ({"credentials": {"access_key_id": "nope", "secret_access_key": "x"}}, 422),
        ({"credentials": {}}, 422),
    ],
)
def test_create_account_validation(client, auth_headers, override, status):
    resp = client.post(
        f"{API}/cloud-accounts", json={**AWS_ACCOUNT, **override}, headers=auth_headers("admin")
    )
    assert resp.status_code == status


def test_duplicate_account_conflicts(client, auth_headers, create_account):
    headers = auth_headers("admin")
    create_account(headers)
    resp = client.post(f"{API}/cloud-accounts", json=AWS_ACCOUNT, headers=headers)
    assert resp.status_code == 409


def test_validate_connection_success_and_failure(client, auth_headers, create_account):
    headers = auth_headers("admin")
    good = create_account(headers)
    ok = client.post(f"{API}/cloud-accounts/{good['id']}/validate", headers=headers).json()
    assert ok["ok"] is True and ok["adapter"] == "MockCloudAdapter"
    assert (
        client.get(f"{API}/cloud-accounts/{good['id']}", headers=headers).json()["status"]
        == "connected"
    )

    bad_payload = {
        **GCP_ACCOUNT,
        "credentials": {"service_account_json": '{"client_email": "invalid@x"}'},
    }
    bad = create_account(headers, bad_payload)
    result = client.post(f"{API}/cloud-accounts/{bad['id']}/validate", headers=headers).json()
    assert result["ok"] is False
    assert (
        client.get(f"{API}/cloud-accounts/{bad['id']}", headers=headers).json()["status"] == "error"
    )
    alerts = client.get(f"{API}/alerts?severity=critical", headers=headers).json()
    assert alerts["total"] == 1 and alerts["items"][0]["category"] == "account"


def test_rotate_update_and_delete(client, auth_headers, create_account, db):
    from app.core.crypto import decrypt_credentials
    from app.models import CloudAccount

    headers = auth_headers("admin")
    account = create_account(headers)
    rotated = client.put(
        f"{API}/cloud-accounts/{account['id']}/credentials",
        headers=headers,
        json={"credentials": {"access_key_id": "AKIAROTATED00002", "secret_access_key": "new"}},
    )
    assert rotated.status_code == 200
    assert rotated.json()["credential_hint"].endswith("0002")
    stored = db.scalar(select(CloudAccount))
    assert decrypt_credentials(stored.encrypted_credentials)["secret_access_key"] == "new"

    renamed = client.patch(
        f"{API}/cloud-accounts/{account['id']}", headers=headers, json={"name": "Renamed"}
    )
    assert renamed.json()["name"] == "Renamed"

    assert (
        client.delete(f"{API}/cloud-accounts/{account['id']}", headers=headers).status_code == 204
    )
    assert client.get(f"{API}/cloud-accounts/{account['id']}", headers=headers).status_code == 404


def test_unknown_account_returns_404_envelope(client, auth_headers):
    resp = client.get(
        f"{API}/cloud-accounts/00000000-0000-0000-0000-000000000000", headers=auth_headers("viewer")
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"
