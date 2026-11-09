from __future__ import annotations

API = "/api/v1"


def _seed_costs(client, headers, create_account):
    account = create_account(headers)
    client.post(f"{API}/cloud-accounts/{account['id']}/sync", headers=headers)
    return account


def test_summary_trends_and_services(client, auth_headers, create_account):
    headers = auth_headers("admin")
    _seed_costs(client, headers, create_account)
    summary = client.get(f"{API}/costs/summary", headers=headers).json()
    assert {p["provider"] for p in summary["by_provider"]} == {"aws", "azure", "gcp"}
    aws = next(p for p in summary["by_provider"] if p["provider"] == "aws")
    assert float(aws["current_month"]) > 0 and float(aws["previous_month"]) > 0
    assert float(summary["forecast_current_month"]) >= float(summary["current_month"])

    trends = client.get(f"{API}/costs/trends?months=3", headers=headers).json()
    assert len(trends) == 3
    assert trends[0]["month"] < trends[-1]["month"]
    for point in trends:
        assert (
            abs(
                float(point["total"])
                - float(point["aws"])
                - float(point["azure"])
                - float(point["gcp"])
            )
            < 0.01
        )

    services = client.get(f"{API}/costs/by-service", headers=headers).json()
    assert {s["service"] for s in services} >= {"Amazon EC2", "Amazon S3"}
    amounts = [float(s["amount"]) for s in services]
    assert amounts == sorted(amounts, reverse=True)


def test_budget_crud_and_threshold_alerts(client, auth_headers, create_account):
    headers = auth_headers("admin")
    _seed_costs(client, headers, create_account)
    spend = float(
        next(
            p
            for p in client.get(f"{API}/costs/summary", headers=headers).json()["by_provider"]
            if p["provider"] == "aws"
        )["current_month"]
    )

    # Limit below spend: crosses both the 50% threshold and 100%.
    created = client.post(
        f"{API}/costs/budgets",
        headers=headers,
        json={
            "name": "AWS tight",
            "provider": "aws",
            "monthly_limit": f"{spend * 0.9:.2f}",
            "alert_threshold_percent": 50,
        },
    )
    assert created.status_code == 201, created.text
    budget = created.json()
    assert budget["utilization_percent"] > 100

    alerts = client.get(f"{API}/costs/alerts", headers=headers).json()
    assert alerts["total"] == 2
    assert {a["threshold_percent"] for a in alerts["items"]} == {50, 100}
    assert {a["severity"] for a in alerts["items"]} == {"warning", "critical"}
    assert alerts["items"][0]["budget_name"] == "AWS tight"

    # Idempotent: re-evaluation does not duplicate records.
    assert client.post(f"{API}/costs/budgets/evaluate", headers=headers).json() == []
    assert client.get(f"{API}/costs/alerts", headers=headers).json()["total"] == 2
    ops_alerts = client.get(f"{API}/alerts?status=open", headers=headers).json()["items"]
    assert sum(a["category"] == "cost" for a in ops_alerts) == 2

    roomy = client.post(
        f"{API}/costs/budgets",
        headers=headers,
        json={"name": "Everything", "monthly_limit": "999999"},
    ).json()
    assert roomy["utilization_percent"] < 50
    updated = client.patch(
        f"{API}/costs/budgets/{roomy['id']}",
        headers=headers,
        json={"monthly_limit": "1000000", "is_active": False},
    ).json()
    assert updated["is_active"] is False and float(updated["monthly_limit"]) == 1000000
    assert len(client.get(f"{API}/costs/budgets", headers=headers).json()) == 2
    assert client.delete(f"{API}/costs/budgets/{roomy['id']}", headers=headers).status_code == 204
    assert len(client.get(f"{API}/costs/budgets", headers=headers).json()) == 1


def test_budget_validation(client, auth_headers):
    headers = auth_headers("admin")
    both = client.post(
        f"{API}/costs/budgets",
        headers=headers,
        json={
            "name": "Bad",
            "provider": "aws",
            "cloud_account_id": "00000000-0000-0000-0000-000000000000",
            "monthly_limit": "10",
        },
    )
    assert both.status_code == 422
    negative = client.post(
        f"{API}/costs/budgets", headers=headers, json={"name": "Neg", "monthly_limit": "-1"}
    )
    assert negative.status_code == 422
    missing_acct = client.post(
        f"{API}/costs/budgets",
        headers=headers,
        json={
            "name": "Ghost",
            "cloud_account_id": "00000000-0000-0000-0000-000000000000",
            "monthly_limit": "10",
        },
    )
    assert missing_acct.status_code == 404
