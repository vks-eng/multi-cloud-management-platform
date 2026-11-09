"""Shared fixtures. The app is imported lazily so DATABASE_URL can be set first."""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from cryptography.fernet import Fernet

from tests.pg import PostgresUnavailable, resolve_test_database_url

PASSWORD = "Str0ng-Test-Pass"


def pytest_configure(config: pytest.Config) -> None:
    try:
        url = resolve_test_database_url()
    except PostgresUnavailable as exc:
        pytest.exit(str(exc), returncode=3)
    os.environ["DATABASE_URL"] = url
    os.environ["ENVIRONMENT"] = "test"
    os.environ["CLOUD_PROVIDER_MODE"] = "mock"
    os.environ["CELERY_TASK_ALWAYS_EAGER"] = "true"
    os.environ["TERRAFORM_MODE"] = "auto"
    os.environ["TERRAFORM_APPLY_ENABLED"] = "false"
    os.environ["JWT_SECRET_KEY"] = "test-secret-key-that-is-long-enough-0123456789"
    os.environ["CREDENTIALS_ENCRYPTION_KEYS"] = Fernet.generate_key().decode()
    os.environ["LOG_LEVEL"] = "WARNING"


@pytest.fixture(scope="session")
def migrated_engine() -> Iterator[Any]:
    """Apply the real Alembic migrations once per session."""
    from alembic.config import Config

    from alembic import command
    from app.db.session import get_engine

    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg = Config(os.path.join(backend_dir, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(backend_dir, "alembic"))
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    yield get_engine()


@pytest.fixture(autouse=True)
def clean_db(migrated_engine: Any) -> Iterator[None]:
    yield
    from sqlalchemy import text

    from app.db.base import Base

    tables = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    with migrated_engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


@pytest.fixture
def db(migrated_engine: Any) -> Iterator[Any]:
    from app.db.session import get_session_factory

    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(migrated_engine: Any) -> Iterator[Any]:
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def make_user(db: Any) -> Callable[..., Any]:
    from app.core.security import hash_password
    from app.models import User

    def _make(email: str = "user@example.com", role: str = "viewer", active: bool = True) -> Any:
        user = User(
            email=email,
            full_name=email.split("@")[0],
            role=role,
            is_active=active,
            hashed_password=hash_password(PASSWORD),
        )
        db.add(user)
        db.commit()
        return user

    return _make


@pytest.fixture
def auth_headers(client: Any, make_user: Callable[..., Any]) -> Callable[[str], dict[str, str]]:
    """Return a factory: auth_headers('admin') -> Authorization header for a new user."""

    def _headers(role: str = "admin", email: str | None = None) -> dict[str, str]:
        email = email or f"{role}@example.com"
        make_user(email=email, role=role)
        resp = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
        assert resp.status_code == 200, resp.text
        return {"Authorization": f"Bearer {resp.json()['access_token']}"}

    return _headers


AWS_ACCOUNT = {
    "name": "AWS Test",
    "provider": "aws",
    "external_id": "123456789012",
    "default_region": "us-east-1",
    "credentials": {"access_key_id": "AKIATESTKEY00001", "secret_access_key": "super-secret-value"},
}
AZURE_ACCOUNT = {
    "name": "Azure Test",
    "provider": "azure",
    "external_id": "3f2b8c1e-9a4d-4e6f-8b7a-1c2d3e4f5a6b",
    "default_region": "westeurope",
    "credentials": {"tenant_id": "t-1", "client_id": "c-1", "client_secret": "azure-secret-value"},
}
GCP_ACCOUNT = {
    "name": "GCP Test",
    "provider": "gcp",
    "external_id": "test-project-01",
    "default_region": "us-central1",
    "credentials": {
        "service_account_json": '{"client_email": "r@test-project-01.iam.gserviceaccount.com", "private_key": "gcp-secret-value"}'
    },
}


@pytest.fixture
def create_account(client: Any) -> Callable[..., dict[str, Any]]:
    def _create(headers: dict[str, str], payload: dict[str, Any] | None = None) -> dict[str, Any]:
        resp = client.post("/api/v1/cloud-accounts", json=payload or AWS_ACCOUNT, headers=headers)
        assert resp.status_code == 201, resp.text
        return resp.json()

    return _create
