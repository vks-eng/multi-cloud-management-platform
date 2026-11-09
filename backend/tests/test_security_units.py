"""Unit tests for security primitives, configuration guards, adapters and the runner."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import pytest
from cryptography.fernet import Fernet


def test_password_hashing_roundtrip_and_long_passwords():
    from app.core.security import hash_password, verify_password

    long_pw = "x" * 200 + "1"
    hashed = hash_password(long_pw)
    assert verify_password(long_pw, hashed)
    assert not verify_password("x" * 200 + "2", hashed)  # bcrypt 72-byte truncation avoided
    assert not verify_password("anything", "not-a-hash")


def test_credentials_encryption_and_key_rotation(monkeypatch):
    from app.core import crypto
    from app.core.config import get_settings

    old_key, new_key = Fernet.generate_key().decode(), Fernet.generate_key().decode()
    settings = get_settings()
    monkeypatch.setattr(settings, "credentials_encryption_keys", [old_key])
    crypto.get_cipher.cache_clear()
    token = crypto.encrypt_credentials({"secret": "s3cr3t"})
    assert "s3cr3t" not in token

    monkeypatch.setattr(settings, "credentials_encryption_keys", [new_key, old_key])
    crypto.get_cipher.cache_clear()
    assert crypto.decrypt_credentials(token) == {"secret": "s3cr3t"}

    monkeypatch.setattr(settings, "credentials_encryption_keys", [new_key])
    crypto.get_cipher.cache_clear()
    with pytest.raises(crypto.CredentialDecryptionError):
        crypto.decrypt_credentials(token)
    crypto.get_cipher.cache_clear()


def test_mask_secret():
    from app.core.crypto import mask_secret

    assert mask_secret("ABCDEFGH1234") == "********1234"
    assert mask_secret("abc") == "***"
    assert mask_secret("") == ""


def test_redaction_of_dicts_and_log_records(caplog):
    from app.core.logging import REDACTED, RedactingFilter, redact, redact_text

    data = {"name": "ok", "client_secret": "x", "nested": [{"password": "p", "region": "eu"}]}
    assert redact(data) == {
        "name": "ok",
        "client_secret": REDACTED,
        "nested": [{"password": REDACTED, "region": "eu"}],
    }
    assert "hunter2" not in redact_text('{"password": "hunter2", "user": "bob"}')

    logger = logging.getLogger("test.redaction")
    logger.addFilter(RedactingFilter())
    with caplog.at_level(logging.INFO, logger="test.redaction"):
        logger.info("payload secret_access_key=AKIA123SECRET region=us")
    assert "AKIA123SECRET" not in caplog.text
    assert REDACTED in caplog.text


def test_settings_guards():
    from app.core.config import Settings

    with pytest.raises(ValueError, match="PostgreSQL"):
        Settings(database_url="sqlite:///x.db")
    with pytest.raises(ValueError, match="JWT_SECRET_KEY"):
        Settings(
            environment="production",
            jwt_secret_key="too-short",
            credentials_encryption_keys=[Fernet.generate_key().decode()],
        )
    with pytest.raises(ValueError, match="CREDENTIALS_ENCRYPTION_KEYS"):
        Settings(environment="production", jwt_secret_key="y" * 40, credentials_encryption_keys=[])
    ok = Settings(
        environment="production",
        jwt_secret_key="y" * 40,
        credentials_encryption_keys="k1, k2",
        cors_origins="https://a.example,https://b.example",
    )
    assert ok.credentials_encryption_keys == ["k1", "k2"]
    assert ok.cors_origins == ["https://a.example", "https://b.example"]


def test_permission_helper():
    from app.core.permissions import Permission, has_permission

    assert has_permission("admin", Permission.USERS_MANAGE)
    assert has_permission("operator", Permission.INFRA_APPLY)
    assert not has_permission("viewer", Permission.RESOURCES_SYNC)
    assert not has_permission("superuser", Permission.ACCOUNTS_READ)


def test_hcl_escaping_prevents_interpolation():
    from app.infrastructure.renderer import hcl_map, hcl_string

    assert hcl_string('a"b') == '"a\\"b"'
    assert hcl_string('${file("/etc/passwd")}') == '"$${file(\\"/etc/passwd\\")}"'
    assert hcl_string("%{ if x }") == '"%%{ if x }"'
    assert hcl_string(True) == "true" and hcl_string(5) == "5"
    assert hcl_map({}) == "{}"


def _ctx(provider="aws", ext="123456789012"):
    from app.models.enums import CloudProvider
    from app.providers.base import AccountContext

    return AccountContext(
        provider=CloudProvider(provider), external_id=ext, default_region="us-east-1"
    )


def test_mock_adapter_is_deterministic_and_stateful():
    from app.providers.mock import MockCloudAdapter

    a = MockCloudAdapter(_ctx(), {"k": "v"})
    b = MockCloudAdapter(_ctx(), {"k": "v"})
    assert {r.external_id for r in a.list_resources()} == {
        r.external_id for r in b.list_resources()
    }
    other = MockCloudAdapter(_ctx(ext="999999999999"), {"k": "v"})
    assert {r.external_id for r in other.list_resources()} != {
        r.external_id for r in a.list_resources()
    }

    created = a.provision("ec2_instance", "new-box-01", {"instance_size": "t3.medium"})
    assert created.external_id in {r.external_id for r in a.list_resources()}
    a.decommission("ec2_instance", created.external_id)
    assert created.external_id not in {r.external_id for r in a.list_resources()}
    with pytest.raises(ValueError):
        a.provision("gcp_bucket", "wrong-provider", {})

    costs = a.get_monthly_costs(4)
    assert len({c.period_month for c in costs}) == 4
    assert all(c.amount > 0 for c in costs)
    assert a.validate_connection().ok
    assert not MockCloudAdapter(_ctx(), {"k": "invalid"}).validate_connection().ok
    assert "v" not in repr(a)


def test_factory_selects_adapter_by_mode():
    from app.core.config import Settings
    from app.providers.aws import AwsAdapter
    from app.providers.factory import get_adapter
    from app.providers.mock import MockCloudAdapter

    assert isinstance(
        get_adapter(_ctx(), {}, Settings(cloud_provider_mode="mock")), MockCloudAdapter
    )
    assert isinstance(get_adapter(_ctx(), {}, Settings(cloud_provider_mode="real")), AwsAdapter)


def test_real_adapters_report_missing_sdk_cleanly():
    pytest.importorskip("app.providers.aws")
    try:
        import boto3  # noqa: F401
    except ImportError:
        from app.core.errors import ProviderUnavailableError
        from app.providers.aws import AwsAdapter

        with pytest.raises(ProviderUnavailableError, match=r"\[aws\]"):
            AwsAdapter(
                _ctx(), {"access_key_id": "x", "secret_access_key": "y"}
            ).validate_connection()
    else:  # pragma: no cover - SDK installed in this environment
        pytest.skip("boto3 installed; missing-SDK path not applicable")


def test_runner_mock_reasons_and_apply_guard(tmp_path):
    from app.core.config import Settings
    from app.core.errors import BusinessRuleError
    from app.infrastructure.runner import TerraformRunner

    assert "TERRAFORM_MODE=mock" in TerraformRunner(Settings(terraform_mode="mock")).mock_reason()
    assert (
        "CLOUD_PROVIDER_MODE" in TerraformRunner(Settings(cloud_provider_mode="mock")).mock_reason()
    )
    missing = Settings(cloud_provider_mode="real", terraform_binary="definitely-not-terraform-xyz")
    assert "not found" in TerraformRunner(missing).mock_reason()

    disabled = TerraformRunner(Settings(terraform_workdir=str(tmp_path)))
    with pytest.raises(BusinessRuleError, match="disabled"):
        disabled.apply("run-1")
    enabled = TerraformRunner(
        Settings(terraform_workdir=str(tmp_path), terraform_apply_enabled=True)
    )
    with pytest.raises(BusinessRuleError, match="No saved plan"):
        enabled.apply("run-2")


def test_terraform_env_mapping():
    from app.infrastructure.runner import terraform_env

    assert terraform_env(
        "aws", {"access_key_id": "a", "secret_access_key": "b", "session_token": "c"}
    ) == {"AWS_ACCESS_KEY_ID": "a", "AWS_SECRET_ACCESS_KEY": "b", "AWS_SESSION_TOKEN": "c"}
    assert set(terraform_env("azure", {})) == {
        "ARM_TENANT_ID",
        "ARM_CLIENT_ID",
        "ARM_CLIENT_SECRET",
    }
    assert terraform_env("gcp", {"service_account_json": "{}"}) == {"GOOGLE_CREDENTIALS": "{}"}


def test_health_endpoints(client):
    assert client.get("/api/v1/health/live").json() == {"status": "ok"}
    body = client.get("/api/v1/health").json()
    assert body["database"] == "ok" and body["cloud_provider_mode"] == "mock"


def test_security_headers_and_openapi(client):
    resp = client.get("/api/v1/health/live")
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["x-frame-options"] == "DENY"
    spec = client.get("/api/v1/openapi.json").json()
    assert spec["info"]["title"].startswith("CloudOrbit")


def test_month_start_helper():
    from datetime import date

    from app.services.costs import month_start

    assert month_start(date(2026, 1, 15), 1) == date(2025, 12, 1)
    assert month_start(date(2026, 3, 31), 0) == date(2026, 3, 1)
    assert datetime.now(UTC).year >= 2024


def test_seed_script_populates_demo_data(db):
    from app.models import CloudAccount, ProvisioningRequest, Resource, User
    from app.seed import seed

    seed()
    assert db.query(User).count() == 3
    assert db.query(CloudAccount).filter(CloudAccount.status == "connected").count() == 4
    assert db.query(Resource).count() > 20
    assert db.query(ProvisioningRequest).count() == 2
    seed()  # idempotent
    assert db.query(User).count() == 3
