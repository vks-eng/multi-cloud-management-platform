from __future__ import annotations

from sqlalchemy import select

from tests.conftest import AZURE_ACCOUNT, GCP_ACCOUNT

API = "/api/v1"


def _sync(client, headers, account_id):
    resp = client.post(f"{API}/cloud-accounts/{account_id}/sync", headers=headers)
    assert resp.status_code == 202, resp.text
    return resp.json()


def test_sync_discovers_resources_and_costs(client, auth_headers, create_account):
    headers = auth_headers("admin")
    account = create_account(headers)
    job = _sync(client, headers, account["id"])
    assert job["status"] == "succeeded"
    assert job["resources_found"] > 0
    assert job["resources_created"] == job["resources_found"]

    resources = client.get(f"{API}/resources?limit=200", headers=headers).json()
    assert resources["total"] == job["resources_found"]
    types = {r["resource_type"] for r in resources["items"]}
    assert types == {"ec2_instance", "s3_bucket"}
    assert all(r["account_name"] == "AWS Test" for r in resources["items"])

    acct = client.get(f"{API}/cloud-accounts/{account['id']}", headers=headers).json()
    assert (
        acct["status"] == "connected"
        and acct["last_synced_at"]
        and acct["resource_count"] == resources["total"]
    )

    jobs = client.get(f"{API}/cloud-accounts/{account['id']}/sync-jobs", headers=headers).json()
    assert len(jobs) == 1
    assert (
        client.get(f"{API}/cloud-accounts/sync-jobs/{job['id']}", headers=headers).json()["id"]
        == job["id"]
    )

    costs = client.get(f"{API}/costs/trends?months=6", headers=headers).json()
    assert len(costs) == 6 and all(float(p["aws"]) > 0 for p in costs)


def test_resync_is_idempotent_and_tracks_deletions(client, auth_headers, create_account, db):
    from app.models import CloudAccount, Resource, ResourceChange

    headers = auth_headers("operator")
    admin = auth_headers("admin")
    account = create_account(admin)
    first = _sync(client, headers, account["id"])
    second = _sync(client, headers, account["id"])
    assert second["resources_created"] == 0
    assert db.query(Resource).count() == first["resources_found"]

    # Simulate a resource disappearing from the provider.
    victim = db.scalar(select(Resource).order_by(Resource.name))
    acct = db.get(CloudAccount, victim.cloud_account_id)
    acct.provider_state = {**acct.provider_state, "decommissioned": [victim.external_id]}
    db.commit()
    third = _sync(client, headers, account["id"])
    assert third["resources_deleted"] == 1
    db.expire_all()
    gone = db.get(Resource, victim.id)
    assert gone.status == "deleted" and gone.deleted_at is not None
    change_types = {
        c.change_type
        for c in db.scalars(select(ResourceChange).where(ResourceChange.resource_id == victim.id))
    }
    assert {"created", "deleted"} <= change_types

    active = client.get(f"{API}/resources?limit=200", headers=headers).json()["total"]
    with_deleted = client.get(
        f"{API}/resources?limit=200&include_deleted=true", headers=headers
    ).json()["total"]
    assert with_deleted == active + 1


def test_resource_filters_detail_changes_and_metrics(client, auth_headers, create_account):
    headers = auth_headers("admin")
    for payload in (AZURE_ACCOUNT, GCP_ACCOUNT):
        _sync(client, headers, create_account(headers, payload)["id"])

    azure = client.get(f"{API}/resources?provider=azure&limit=200", headers=headers).json()
    assert azure["total"] > 0 and all(r["provider"] == "azure" for r in azure["items"])
    buckets = client.get(f"{API}/resources?resource_type=gcp_bucket", headers=headers).json()
    assert all(r["resource_type"] == "gcp_bucket" for r in buckets["items"])

    page = client.get(f"{API}/resources?limit=2&offset=0&sort=-cost", headers=headers).json()
    assert len(page["items"]) == 2 and page["limit"] == 2
    costs = [float(r["monthly_cost_estimate"]) for r in page["items"]]
    assert costs == sorted(costs, reverse=True)

    target = azure["items"][0]
    name_fragment = target["name"][:5]
    search = client.get(f"{API}/resources?search={name_fragment}", headers=headers).json()
    assert any(r["id"] == target["id"] for r in search["items"])

    detail = client.get(f"{API}/resources/{target['id']}", headers=headers).json()
    assert detail["external_id"] == target["external_id"]
    changes = client.get(f"{API}/resources/{target['id']}/changes", headers=headers).json()
    assert changes["items"][0]["change_type"] == "created"
    metrics = client.get(f"{API}/resources/{target['id']}/metrics?hours=1", headers=headers).json()
    assert len(metrics) == 1

    all_changes = client.get(f"{API}/resources/changes?limit=5", headers=headers).json()
    assert all_changes["total"] >= azure["total"] and len(all_changes["items"]) == 5


def test_dashboard_overview(client, auth_headers, create_account):
    headers = auth_headers("admin")
    _sync(client, headers, create_account(headers)["id"])
    _sync(client, headers, create_account(headers, GCP_ACCOUNT)["id"])
    overview = client.get(f"{API}/dashboard/overview", headers=headers).json()
    assert overview["total_resources"] == sum(i["count"] for i in overview["by_provider"])
    assert {i["key"] for i in overview["by_provider"]} == {"aws", "gcp"}
    assert (
        overview["running_compute"] + overview["stopped_compute"] + overview["storage_resources"]
        == overview["total_resources"]
    )
    assert overview["accounts"]["connected"] == 2
    assert len(overview["usage"]["series"]) >= 1
    assert float(overview["month_to_date_cost"]) > 0
    assert any(a["action"] == "resource.sync" for a in overview["recent_activity"])


def test_sync_failure_marks_job_and_raises_alert(client, auth_headers, create_account, monkeypatch):
    from app.core.errors import ProviderError
    from app.providers.mock import MockCloudAdapter

    def boom(self):
        raise ProviderError("simulated outage")

    monkeypatch.setattr(MockCloudAdapter, "list_resources", boom)
    headers = auth_headers("admin")
    account = create_account(headers)
    job = _sync(client, headers, account["id"])
    assert job["status"] == "failed" and job["error"] == "simulated outage"
    acct = client.get(f"{API}/cloud-accounts/{account['id']}", headers=headers).json()
    assert acct["status"] == "error"
    alerts = client.get(f"{API}/alerts?status=open", headers=headers).json()["items"]
    assert any("sync failed" in a["title"] for a in alerts)


def test_alert_acknowledge_and_resolve(client, auth_headers, db):
    from app.models.enums import AlertCategory, AlertSeverity
    from app.services.alerts import AlertService

    alert = AlertService(db).raise_alert(
        fingerprint="t:1",
        severity=AlertSeverity.WARNING,
        category=AlertCategory.RESOURCE,
        title="Test",
        message="m",
    )
    db.commit()
    # De-duplication: same fingerprint does not create a second open alert.
    AlertService(db).raise_alert(
        fingerprint="t:1",
        severity=AlertSeverity.WARNING,
        category=AlertCategory.RESOURCE,
        title="Test",
        message="m2",
    )
    db.commit()
    headers = auth_headers("operator")
    assert client.get(f"{API}/alerts", headers=headers).json()["total"] == 1
    ack = client.post(f"{API}/alerts/{alert.id}/acknowledge", headers=headers).json()
    assert ack["status"] == "acknowledged" and ack["message"] == "m2"
    res = client.post(f"{API}/alerts/{alert.id}/resolve", headers=headers).json()
    assert res["status"] == "resolved" and res["resolved_at"]
    again = client.post(f"{API}/alerts/{alert.id}/resolve", headers=headers)
    assert again.status_code == 422
    viewer = auth_headers("viewer")
    assert client.post(f"{API}/alerts/{alert.id}/acknowledge", headers=viewer).status_code == 403
