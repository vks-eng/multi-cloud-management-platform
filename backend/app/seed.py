"""Populate a database with demo data using the MOCK cloud providers.

    python -m app.seed            # idempotent: skips if demo users already exist
    python -m app.seed --reset    # truncate all tables first (DESTRUCTIVE, dev only)

Demo credentials (LOCAL DEVELOPMENT ONLY - never use in a shared environment):
    admin@cloudorbit.dev     / CloudOrbit!2026   (admin)
    operator@cloudorbit.dev  / CloudOrbit!2026   (operator)
    viewer@cloudorbit.dev    / CloudOrbit!2026   (viewer)
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import sys
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import text

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.permissions import Role
from app.core.security import hash_password
from app.db.base import Base, utcnow
from app.db.session import session_scope
from app.models import ResourceMetric, User
from app.models.enums import COMPUTE_TYPES, CloudProvider, ResourceStatus
from app.repositories.repos import ResourceRepository, UserRepository
from app.schemas.account import CloudAccountCreate
from app.schemas.cost import BudgetCreate
from app.schemas.infrastructure import ProvisioningApply, ProvisioningCreate
from app.services.accounts import CloudAccountService
from app.services.audit import RequestContext
from app.services.costs import CostService
from app.services.inventory import InventoryService
from app.services.provisioning import ProvisioningService

logger = logging.getLogger("app.seed")

DEMO_PASSWORD = "CloudOrbit!2026"
DEMO_USERS = [
    ("admin@cloudorbit.dev", "Avery Admin", Role.ADMIN, "Platform Lead"),
    ("operator@cloudorbit.dev", "Oliver Operator", Role.OPERATOR, "Cloud Operations Engineer"),
    ("viewer@cloudorbit.dev", "Vera Viewer", Role.VIEWER, "Finance Analyst"),
]

_FAKE_GCP_KEY = json.dumps(
    {
        "type": "service_account",
        "project_id": "orbit-analytics-prod",
        "client_email": "mcmp-viewer@orbit-analytics-prod.iam.gserviceaccount.com",
        "private_key_id": "mock-key-id",
        "private_key": "mock-not-a-real-key",
    }
)

DEMO_ACCOUNTS = [
    CloudAccountCreate(
        name="AWS Production",
        provider=CloudProvider.AWS,
        external_id="123456789012",
        default_region="us-east-1",
        description="Customer-facing production workloads",
        credentials={"access_key_id": "AKIAMOCKPROD0001", "secret_access_key": "mock-secret-1"},
    ),
    CloudAccountCreate(
        name="AWS Staging",
        provider=CloudProvider.AWS,
        external_id="210987654321",
        default_region="eu-west-1",
        description="Pre-production environment",
        credentials={"access_key_id": "AKIAMOCKSTAG0002", "secret_access_key": "mock-secret-2"},
    ),
    CloudAccountCreate(
        name="Azure Corporate",
        provider=CloudProvider.AZURE,
        external_id="3f2b8c1e-9a4d-4e6f-8b7a-1c2d3e4f5a6b",
        default_region="westeurope",
        description="Internal apps and identity workloads",
        credentials={
            "tenant_id": "11111111-2222-3333-4444-555555555555",
            "client_id": "66666666-7777-8888-9999-000000000000",
            "client_secret": "mock-client-secret",
        },
    ),
    CloudAccountCreate(
        name="GCP Analytics",
        provider=CloudProvider.GCP,
        external_id="orbit-analytics-prod",
        default_region="us-central1",
        description="Data platform and BigQuery",
        credentials={"service_account_json": _FAKE_GCP_KEY},
    ),
]


def _reset() -> None:
    with session_scope() as session:
        tables = ", ".join(f'"{t.name}"' for t in reversed(Base.metadata.sorted_tables))
        session.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


def _backfill_metrics(hours: int = 24) -> int:
    """Add hourly utilisation samples for the past day so charts have history (demo only)."""
    rng = random.Random(2026)
    now = utcnow()
    count = 0
    compute = {t.value for t in COMPUTE_TYPES}
    with session_scope() as session:
        for res in ResourceRepository(session).active():
            if res.resource_type not in compute or res.status != ResourceStatus.RUNNING:
                continue
            base = rng.uniform(15, 60)
            for h in range(hours, 0, -1):
                daily = 15 * (1 if 9 <= (now - timedelta(hours=h)).hour <= 18 else -0.5)
                session.add(
                    ResourceMetric(
                        resource_id=res.id,
                        captured_at=now - timedelta(hours=h),
                        cpu_percent=round(max(2, min(97, base + daily + rng.uniform(-8, 8))), 1),
                        memory_percent=round(rng.uniform(30, 80), 1),
                        network_in_mb=round(rng.uniform(20, 900), 1),
                        network_out_mb=round(rng.uniform(10, 600), 1),
                    )
                )
                count += 1
    return count


def seed(reset: bool = False) -> None:
    settings = get_settings()
    if settings.environment == "production":
        sys.exit("Refusing to seed demo data in production")
    if settings.cloud_provider_mode != "mock":
        sys.exit("Seeding requires CLOUD_PROVIDER_MODE=mock")
    if reset:
        _reset()

    with session_scope() as session:
        users = UserRepository(session)
        if users.get_by_email(DEMO_USERS[0][0]):
            logger.info("Demo data already present - nothing to do (use --reset to rebuild)")
            return
        created_users = [
            users.add(
                User(
                    email=e,
                    full_name=n,
                    role=r.value,
                    job_title=t,
                    hashed_password=hash_password(DEMO_PASSWORD),
                )
            )
            for e, n, r, t in DEMO_USERS
        ]
        admin_id, operator_id = created_users[0].id, created_users[1].id

    with session_scope() as session:
        ctx = RequestContext(user=session.get(User, admin_id), ip_address="127.0.0.1")
        service = CloudAccountService(session)
        account_ids = []
        for data in DEMO_ACCOUNTS:
            account = service.create(data, ctx)
            service.validate(account.id, ctx)
            account_ids.append(account.id)

    for account_id in account_ids:
        with session_scope() as session:
            inventory = InventoryService(session)
            ctx = RequestContext(user=session.get(User, operator_id), ip_address="127.0.0.1")
            job = inventory.create_sync_job(account_id, ctx, trigger="seed")
            inventory.run_sync(job.id)

    samples = _backfill_metrics()

    with session_scope() as session:
        ctx = RequestContext(user=session.get(User, admin_id), ip_address="127.0.0.1")
        costs = CostService(session)
        summary = costs.summary()
        aws_now = next(p.current_month for p in summary.by_provider if p.provider == "aws")
        costs.create_budget(
            BudgetCreate(
                name="Total cloud spend", monthly_limit=Decimal("9000"), alert_threshold_percent=80
            ),
            ctx,
        )
        costs.create_budget(
            BudgetCreate(
                name="AWS monthly",
                provider=CloudProvider.AWS,
                monthly_limit=max(
                    Decimal("100"), (aws_now * Decimal("1.1")).quantize(Decimal("1"))
                ),
                alert_threshold_percent=75,
            ),
            ctx,
        )
        costs.create_budget(
            BudgetCreate(
                name="GCP analytics",
                provider=CloudProvider.GCP,
                monthly_limit=Decimal("2500"),
                alert_threshold_percent=90,
            ),
            ctx,
        )

    with session_scope() as session:
        ctx = RequestContext(user=session.get(User, operator_id), ip_address="127.0.0.1")
        prov = ProvisioningService(session)
        req, token = prov.plan(
            ProvisioningCreate(
                cloud_account_id=account_ids[0],
                template_key="aws_s3_bucket",
                parameters={
                    "name": "orbit-reports-archive",
                    "region": "us-east-1",
                    "versioning": True,
                    "tags": {"team": "finance", "environment": "prod"},
                },
            ),
            ctx,
        )
        prov.apply(
            req.id,
            ProvisioningApply(confirmation_token=token, confirm_resource_name=req.resource_name),
            ctx,
        )
        prov.plan(
            ProvisioningCreate(
                cloud_account_id=account_ids[3],
                template_key="gcp_compute_instance",
                parameters={
                    "name": "etl-runner-01",
                    "region": "us-central1",
                    "instance_size": "e2-medium",
                },
            ),
            ctx,
        )

    logger.info(
        "Seed complete: %d users, %d accounts, %d metric samples",
        len(DEMO_USERS),
        len(account_ids),
        samples,
    )
    logger.info("Demo login (local only): %s / %s", DEMO_USERS[0][0], "<see app/seed.py docstring>")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--reset", action="store_true", help="truncate all tables first (dev only)")
    args = parser.parse_args()
    configure_logging("INFO")
    seed(reset=args.reset)


if __name__ == "__main__":
    main()
