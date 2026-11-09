from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import select

from tests.conftest import GCP_ACCOUNT

API = "/api/v1"
S3_PARAMS = {
    "name": "team-reports-bucket",
    "region": "us-east-1",
    "versioning": True,
    "tags": {"team": "finance"},
}


def _plan(client, headers, account_id, template="aws_s3_bucket", params=None):
    return client.post(
        f"{API}/infrastructure/provisioning",
        headers=headers,
        json={
            "cloud_account_id": account_id,
            "template_key": template,
            "parameters": params if params is not None else S3_PARAMS,
        },
    )


def test_templates_catalogue(client, auth_headers):
    headers = auth_headers("viewer")
    templates = client.get(f"{API}/infrastructure/templates", headers=headers).json()
    assert len(templates) == 6
    assert {t["provider"] for t in templates} == {"aws", "azure", "gcp"}
    aws_only = client.get(f"{API}/infrastructure/templates?provider=aws", headers=headers).json()
    assert {t["key"] for t in aws_only} == {"aws_ec2_instance", "aws_s3_bucket"}
    assert client.get(f"{API}/infrastructure/templates/nope", headers=headers).status_code == 404
    status = client.get(f"{API}/infrastructure/terraform", headers=headers).json()
    assert status["mock_reason"] and status["apply_enabled"] is False


def test_preview_renders_hardened_hcl(client, auth_headers, create_account):
    headers = auth_headers("admin")
    account = create_account(headers)
    resp = client.post(
        f"{API}/infrastructure/templates/aws_s3_bucket/preview",
        headers=headers,
        json={"cloud_account_id": account["id"], "parameters": S3_PARAMS},
    )
    assert resp.status_code == 200
    hcl = resp.json()["hcl"]
    assert 'resource "aws_s3_bucket" "team_reports_bucket"' in hcl
    assert "block_public_acls       = true" in hcl
    assert '"123456789012"' in hcl  # allowed_account_ids pins the target account
    assert '"managed_by" = "mcmp"' in hcl


@pytest.mark.parametrize(
    "params",
    [
        {**S3_PARAMS, "name": 'evil" } resource "x" "y" {'},
        {**S3_PARAMS, "region": "mars-1"},
        {**S3_PARAMS, "versioning": "yes"},
        {**S3_PARAMS, "unexpected": 1},
        {**S3_PARAMS, "tags": {"bad key!": "v"}},
        {"region": "us-east-1"},
    ],
)
def test_plan_rejects_invalid_parameters(client, auth_headers, create_account, params):
    headers = auth_headers("admin")
    account = create_account(headers)
    resp = _plan(client, headers, account["id"], params=params)
    assert resp.status_code == 422
    assert resp.json()["error"]["details"]["fields"]


def test_template_provider_must_match_account(client, auth_headers, create_account):
    headers = auth_headers("admin")
    gcp = create_account(headers, GCP_ACCOUNT)
    resp = _plan(client, headers, gcp["id"])
    assert resp.status_code == 422
    assert "targets aws" in resp.json()["error"]["message"]


def test_full_plan_confirm_apply_workflow(client, auth_headers, create_account, db):
    from app.models import AuditLog, ProvisioningRequest

    admin = auth_headers("admin")
    operator = auth_headers("operator")
    account = create_account(admin)

    planned = _plan(client, operator, account["id"])
    assert planned.status_code == 201, planned.text
    plan = planned.json()
    assert plan["status"] == "planned"
    assert plan["plan_is_mock"] is True
    assert plan["plan_output"].startswith("[MOCK PLAN]")
    assert plan["plan_summary"] == {"add": 4, "change": 0, "destroy": 0}
    token = plan["confirmation_token"]

    stored = db.get(ProvisioningRequest, plan["id"])
    assert stored.confirmation_token_hash != token and len(stored.confirmation_token_hash) == 64

    # Token is never returned again.
    again = client.get(f"{API}/infrastructure/provisioning/{plan['id']}", headers=operator).json()
    assert "confirmation_token" not in again

    viewer = auth_headers("viewer")
    forbidden = client.post(
        f"{API}/infrastructure/provisioning/{plan['id']}/apply",
        headers=viewer,
        json={"confirmation_token": token, "confirm_resource_name": plan["resource_name"]},
    )
    assert forbidden.status_code == 403

    bad_token = client.post(
        f"{API}/infrastructure/provisioning/{plan['id']}/apply",
        headers=operator,
        json={"confirmation_token": "x" * 20, "confirm_resource_name": plan["resource_name"]},
    )
    assert bad_token.status_code == 403
    bad_name = client.post(
        f"{API}/infrastructure/provisioning/{plan['id']}/apply",
        headers=operator,
        json={"confirmation_token": token, "confirm_resource_name": "something-else"},
    )
    assert bad_name.status_code == 422

    applied = client.post(
        f"{API}/infrastructure/provisioning/{plan['id']}/apply",
        headers=operator,
        json={"confirmation_token": token, "confirm_resource_name": plan["resource_name"]},
    )
    assert applied.status_code == 200
    body = applied.json()
    assert body["status"] == "applied" and body["applied_at"]
    assert body["apply_output"].startswith("[MOCK APPLY]")
    assert body["target_resource_id"]

    resource = client.get(f"{API}/resources/{body['target_resource_id']}", headers=operator).json()
    assert resource["managed_by_platform"] is True and resource["tags"]["team"] == "finance"
    changes = client.get(f"{API}/resources/{resource['id']}/changes", headers=operator).json()[
        "items"
    ]
    assert changes[0]["source"] == "provisioning" and changes[0]["actor_id"]

    replay = client.post(
        f"{API}/infrastructure/provisioning/{plan['id']}/apply",
        headers=operator,
        json={"confirmation_token": token, "confirm_resource_name": plan["resource_name"]},
    )
    assert replay.status_code == 422

    # The provisioned resource survives a subsequent sync (persisted in mock provider state).
    job = client.post(f"{API}/cloud-accounts/{account['id']}/sync", headers=operator).json()
    assert job["status"] == "succeeded"
    still = client.get(f"{API}/resources/{resource['id']}", headers=operator).json()
    assert still["deleted_at"] is None

    actions = [
        (a.action, a.status)
        for a in db.scalars(select(AuditLog).where(AuditLog.action.like("provisioning.%")))
    ]
    assert ("provisioning.plan_create", "success") in actions
    assert actions.count(("provisioning.apply", "failure")) == 3
    assert ("provisioning.apply", "success") in actions

    history = client.get(
        f"{API}/infrastructure/provisioning?status=applied", headers=operator
    ).json()
    assert history["total"] == 1 and history["items"][0]["account_name"] == "AWS Test"


def test_expired_confirmation_cannot_apply(client, auth_headers, create_account, db):
    from app.db.base import utcnow
    from app.models import ProvisioningRequest

    headers = auth_headers("admin")
    plan = _plan(client, headers, create_account(headers)["id"]).json()
    req = db.get(ProvisioningRequest, plan["id"])
    req.confirmation_expires_at = utcnow() - timedelta(minutes=1)
    db.commit()
    resp = client.post(
        f"{API}/infrastructure/provisioning/{plan['id']}/apply",
        headers=headers,
        json={
            "confirmation_token": plan["confirmation_token"],
            "confirm_resource_name": plan["resource_name"],
        },
    )
    assert resp.status_code == 422
    assert (
        client.get(f"{API}/infrastructure/provisioning/{plan['id']}", headers=headers).json()[
            "status"
        ]
        == "expired"
    )


def test_cancel_plan(client, auth_headers, create_account):
    headers = auth_headers("admin")
    plan = _plan(client, headers, create_account(headers)["id"]).json()
    cancelled = client.post(
        f"{API}/infrastructure/provisioning/{plan['id']}/cancel", headers=headers
    )
    assert cancelled.json()["status"] == "cancelled"
    resp = client.post(
        f"{API}/infrastructure/provisioning/{plan['id']}/apply",
        headers=headers,
        json={
            "confirmation_token": plan["confirmation_token"],
            "confirm_resource_name": plan["resource_name"],
        },
    )
    assert resp.status_code == 422


def test_decommission_workflow(client, auth_headers, create_account):
    headers = auth_headers("admin")
    account = create_account(headers, GCP_ACCOUNT)
    client.post(f"{API}/cloud-accounts/{account['id']}/sync", headers=headers)
    vm = client.get(
        f"{API}/resources?resource_type=gcp_compute_instance&limit=1", headers=headers
    ).json()["items"][0]

    plan = client.post(
        f"{API}/infrastructure/decommission", headers=headers, json={"resource_id": vm["id"]}
    ).json()
    assert plan["action"] == "destroy"
    assert plan["plan_summary"]["destroy"] == 1
    assert "will be destroyed" in plan["plan_output"]

    applied = client.post(
        f"{API}/infrastructure/provisioning/{plan['id']}/apply",
        headers=headers,
        json={
            "confirmation_token": plan["confirmation_token"],
            "confirm_resource_name": vm["name"],
        },
    ).json()
    assert applied["status"] == "applied"
    gone = client.get(f"{API}/resources/{vm['id']}", headers=headers).json()
    assert gone["status"] == "deleted"

    # It stays gone after a re-sync, and cannot be decommissioned twice.
    client.post(f"{API}/cloud-accounts/{account['id']}/sync", headers=headers)
    assert (
        client.get(f"{API}/resources/{vm['id']}", headers=headers).json()["deleted_at"] is not None
    )
    again = client.post(
        f"{API}/infrastructure/decommission", headers=headers, json={"resource_id": vm["id"]}
    )
    assert again.status_code == 422


@pytest.mark.parametrize(
    "template",
    [
        "aws_ec2_instance",
        "azure_vm",
        "azure_storage_account",
        "gcp_compute_instance",
        "gcp_storage_bucket",
        "aws_s3_bucket",
    ],
)
def test_every_template_renders_with_defaults(template):
    from app.infrastructure.catalog import get_template, validate_parameters
    from app.infrastructure.renderer import render_template
    from app.infrastructure.runner import TerraformRunner

    spec = get_template(template)
    name = "teststore01" if template == "azure_storage_account" else "test-resource-01"
    params = validate_parameters(spec, {"name": name})
    hcl = render_template(spec, params, account_external_id="acct-1")
    assert hcl.count("{") == hcl.count("}")
    plan = TerraformRunner.mock_plan(hcl, "create", "test")
    assert plan.summary["add"] == len(spec.terraform_resources)
    assert all(r.split(".")[0] in spec.terraform_resources for r in plan.resources)
