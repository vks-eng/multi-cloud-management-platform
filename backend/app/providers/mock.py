"""Mock provider adapters used for local development, demos and tests (the default).

The simulated inventory is deterministic per account (seeded from the external id) so the
same account always shows the same base estate, with small time-based variations
(CPU usage, occasional status flips) so repeated syncs produce realistic change history.
Provisioned / decommissioned resources are persisted in `AccountContext.state`.
"""

from __future__ import annotations

import calendar
import hashlib
import random
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from app.models.enums import CloudProvider, ResourceStatus, ResourceType
from app.providers.base import (
    CloudProviderAdapter,
    ConnectionResult,
    CostItem,
    DiscoveredResource,
    ResourceUsage,
)


@dataclass(frozen=True, slots=True)
class _Profile:
    compute_type: ResourceType
    storage_type: ResourceType
    sizes: tuple[tuple[str, Decimal], ...]
    regions: tuple[str, ...]
    services: tuple[tuple[str, int], ...]  # (service name, base monthly amount)
    identity_fmt: str


_PROFILES: dict[CloudProvider, _Profile] = {
    CloudProvider.AWS: _Profile(
        compute_type=ResourceType.EC2_INSTANCE,
        storage_type=ResourceType.S3_BUCKET,
        sizes=(
            ("t3.micro", Decimal("7.59")),
            ("t3.medium", Decimal("30.37")),
            ("m5.large", Decimal("70.08")),
            ("c6i.xlarge", Decimal("124.10")),
        ),
        regions=("us-east-1", "us-west-2", "eu-west-1"),
        services=(
            ("Amazon EC2", 820),
            ("Amazon S3", 140),
            ("Amazon RDS", 410),
            ("Amazon CloudWatch", 55),
            ("Data Transfer", 95),
        ),
        identity_fmt="arn:aws:iam::{ext}:user/mcmp-readonly",
    ),
    CloudProvider.AZURE: _Profile(
        compute_type=ResourceType.AZURE_VM,
        storage_type=ResourceType.AZURE_STORAGE_ACCOUNT,
        sizes=(
            ("Standard_B1s", Decimal("7.59")),
            ("Standard_B2s", Decimal("30.37")),
            ("Standard_D2s_v5", Decimal("70.08")),
            ("Standard_F4s_v2", Decimal("123.37")),
        ),
        regions=("eastus", "westeurope", "southeastasia"),
        services=(
            ("Virtual Machines", 690),
            ("Storage", 120),
            ("Azure SQL Database", 360),
            ("Bandwidth", 70),
            ("Azure Monitor", 40),
        ),
        identity_fmt="spn:mcmp-reader@{ext}",
    ),
    CloudProvider.GCP: _Profile(
        compute_type=ResourceType.GCP_COMPUTE_INSTANCE,
        storage_type=ResourceType.GCP_BUCKET,
        sizes=(
            ("e2-micro", Decimal("6.11")),
            ("e2-medium", Decimal("24.46")),
            ("n2-standard-2", Decimal("70.90")),
            ("c3-standard-4", Decimal("152.35")),
        ),
        regions=("us-central1", "europe-west1", "asia-south1"),
        services=(
            ("Compute Engine", 610),
            ("Cloud Storage", 95),
            ("BigQuery", 230),
            ("Networking", 60),
            ("Cloud Logging", 30),
        ),
        identity_fmt="mcmp-viewer@{ext}.iam.gserviceaccount.com",
    ),
}

_COMPUTE_NAMES = ("web", "api", "worker", "bastion", "batch", "cache", "ci-runner", "analytics")
_STORAGE_NAMES = ("assets", "backups", "logs", "data-lake", "artifacts", "reports")
_ENVS = ("prod", "staging", "dev")
_TEAMS = ("platform", "payments", "data", "web")


def _seed(*parts: str) -> int:
    return int(hashlib.sha256("::".join(parts).encode()).hexdigest()[:12], 16)


def _money(value: float | Decimal) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _month_start(d: date, back: int) -> date:
    month_index = d.year * 12 + (d.month - 1) - back
    return date(month_index // 12, month_index % 12 + 1, 1)


class MockCloudAdapter(CloudProviderAdapter):
    is_mock = True

    def __init__(self, context, credentials):  # type: ignore[no-untyped-def]
        super().__init__(context, credentials)
        self.provider = context.provider
        self.profile = _PROFILES[context.provider]
        self.context.state.setdefault("provisioned", {})
        self.context.state.setdefault("decommissioned", [])

    # -- connection -----------------------------------------------------------------
    def validate_connection(self) -> ConnectionResult:
        if any("invalid" in str(v).lower() for v in self._credentials.values()):
            return ConnectionResult(ok=False, message="Mock provider rejected the credentials")
        identity = self.profile.identity_fmt.format(ext=self.context.external_id)
        return ConnectionResult(ok=True, message="Connected (mock provider)", identity=identity)

    # -- inventory ------------------------------------------------------------------
    def _base_inventory(self) -> list[DiscoveredResource]:
        rng = random.Random(_seed(self.provider, self.context.external_id))
        p = self.profile
        items: list[DiscoveredResource] = []
        for i in range(rng.randint(4, 7)):
            size, price = rng.choice(p.sizes)
            env = rng.choice(_ENVS)
            region = rng.choice((self.context.default_region, *p.regions))
            name = f"{env}-{rng.choice(_COMPUTE_NAMES)}-{i + 1:02d}"
            ext = self._compute_external_id(rng, name, region)
            status = ResourceStatus.RUNNING if rng.random() > 0.2 else ResourceStatus.STOPPED
            items.append(
                DiscoveredResource(
                    external_id=ext,
                    name=name,
                    resource_type=p.compute_type,
                    region=region,
                    status=status,
                    attributes={
                        "instance_size": size,
                        "os": rng.choice(["linux", "windows"]),
                        "private_ip": f"10.{rng.randint(0, 255)}.{rng.randint(0, 255)}.{rng.randint(2, 250)}",
                    },
                    tags={"environment": env, "team": rng.choice(_TEAMS)},
                    monthly_cost_estimate=price
                    if status == ResourceStatus.RUNNING
                    else _money(price * Decimal("0.1")),
                )
            )
        for i in range(rng.randint(2, 4)):
            env = rng.choice(_ENVS)
            region = rng.choice((self.context.default_region, *p.regions))
            name = self._storage_name(f"{env}-{rng.choice(_STORAGE_NAMES)}-{i + 1}")
            size_gb = rng.randint(5, 4000)
            items.append(
                DiscoveredResource(
                    external_id=self._storage_external_id(name),
                    name=name,
                    resource_type=p.storage_type,
                    region=region,
                    status=ResourceStatus.AVAILABLE,
                    attributes={
                        "storage_class": rng.choice(["standard", "infrequent", "archive"]),
                        "size_gb": size_gb,
                        "versioning": rng.random() > 0.5,
                        "public_access_blocked": rng.random() > 0.1,
                    },
                    tags={"environment": env, "team": rng.choice(_TEAMS)},
                    monthly_cost_estimate=_money(size_gb * 0.023),
                )
            )
        return items

    def _compute_external_id(self, rng: random.Random, name: str, region: str) -> str:
        if self.provider == CloudProvider.AWS:
            return f"i-{rng.getrandbits(64):016x}"[:19]
        if self.provider == CloudProvider.AZURE:
            return (
                f"/subscriptions/{self.context.external_id}/resourceGroups/rg-{region}"
                f"/providers/Microsoft.Compute/virtualMachines/{name}"
            )
        return f"projects/{self.context.external_id}/zones/{region}-a/instances/{name}"

    def _storage_name(self, raw: str) -> str:
        if self.provider == CloudProvider.AZURE:  # storage account names: 3-24 lowercase alnum
            return ("st" + "".join(ch for ch in raw if ch.isalnum()))[:24].lower()
        return f"{raw}-{self.context.external_id[-6:]}".lower()

    def _storage_external_id(self, name: str) -> str:
        if self.provider == CloudProvider.AWS:
            return f"arn:aws:s3:::{name}"
        if self.provider == CloudProvider.AZURE:
            return (
                f"/subscriptions/{self.context.external_id}/resourceGroups/rg-storage"
                f"/providers/Microsoft.Storage/storageAccounts/{name}"
            )
        return f"gs://{name}"

    def _usage(self, res: DiscoveredResource, rng: random.Random) -> ResourceUsage:
        if res.resource_type == self.profile.storage_type:
            size = float(res.attributes.get("size_gb", 10))
            return ResourceUsage(
                storage_used_gb=round(size * rng.uniform(0.95, 1.05), 1),
                network_out_mb=round(rng.uniform(10, 5000), 1),
            )
        if res.status != ResourceStatus.RUNNING:
            return ResourceUsage(
                cpu_percent=0.0, memory_percent=0.0, network_in_mb=0.0, network_out_mb=0.0
            )
        hot = rng.random() < 0.12
        return ResourceUsage(
            cpu_percent=round(rng.uniform(86, 98) if hot else rng.uniform(4, 72), 1),
            memory_percent=round(rng.uniform(20, 85), 1),
            network_in_mb=round(rng.uniform(5, 2500), 1),
            network_out_mb=round(rng.uniform(5, 1800), 1),
        )

    def list_resources(self) -> list[DiscoveredResource]:
        now = datetime.now(UTC)
        bucket = now.strftime("%Y%m%d%H")
        removed = set(self.context.state.get("decommissioned", []))
        items = [r for r in self._base_inventory() if r.external_id not in removed]
        for raw in self.context.state.get("provisioned", {}).values():
            if raw["external_id"] in removed:
                continue
            items.append(
                DiscoveredResource(
                    **{**raw, "monthly_cost_estimate": Decimal(raw["monthly_cost_estimate"])}
                )
            )

        rng = random.Random(_seed(self.provider, self.context.external_id, bucket))
        for res in items:
            # Occasionally flip a compute resource's power state to simulate drift.
            if res.resource_type == self.profile.compute_type and rng.random() < 0.08:
                res.status = (
                    ResourceStatus.STOPPED
                    if res.status == ResourceStatus.RUNNING
                    else ResourceStatus.RUNNING
                )
            res.usage = self._usage(res, rng)
        return items

    # -- provisioning (simulated) -----------------------------------------------------
    def provision(
        self, resource_type: str, name: str, params: dict[str, Any]
    ) -> DiscoveredResource:
        rng = random.Random(_seed(self.provider, self.context.external_id, "prov", name))
        region = params.get("region") or self.context.default_region
        if resource_type == self.profile.compute_type:
            ext = self._compute_external_id(rng, name, region)
            size = params.get("instance_size") or self.profile.sizes[0][0]
            price = dict(self.profile.sizes).get(size, Decimal("25.00"))
            res = DiscoveredResource(
                external_id=ext,
                name=name,
                resource_type=resource_type,
                region=region,
                status=ResourceStatus.RUNNING,
                attributes={"instance_size": size, "os": "linux", "provisioned_via": "terraform"},
                tags={**params.get("tags", {}), "managed_by": "mcmp"},
                monthly_cost_estimate=price,
            )
        elif resource_type == self.profile.storage_type:
            storage_name = self._storage_name(name)
            res = DiscoveredResource(
                external_id=self._storage_external_id(storage_name),
                name=storage_name,
                resource_type=resource_type,
                region=region,
                status=ResourceStatus.AVAILABLE,
                attributes={
                    "storage_class": params.get("storage_class", "standard"),
                    "size_gb": 0,
                    "versioning": bool(params.get("versioning", True)),
                    "public_access_blocked": True,
                    "provisioned_via": "terraform",
                },
                tags={**params.get("tags", {}), "managed_by": "mcmp"},
                monthly_cost_estimate=Decimal("0.00"),
            )
        else:
            raise ValueError(f"{resource_type} is not supported by the {self.provider} adapter")

        self.context.state["provisioned"][res.external_id] = {
            "external_id": res.external_id,
            "name": res.name,
            "resource_type": res.resource_type,
            "region": res.region,
            "status": res.status,
            "attributes": res.attributes,
            "tags": res.tags,
            "monthly_cost_estimate": str(res.monthly_cost_estimate),
        }
        return res

    def decommission(self, resource_type: str, external_id: str) -> None:
        removed: list[str] = self.context.state["decommissioned"]
        if external_id not in removed:
            removed.append(external_id)

    # -- costs ------------------------------------------------------------------------
    def get_monthly_costs(self, months: int = 6) -> list[CostItem]:
        today = datetime.now(UTC).date()
        base_rng = random.Random(_seed(self.provider, self.context.external_id, "cost"))
        scale = base_rng.uniform(0.6, 1.6)
        growth = base_rng.uniform(-0.02, 0.06)
        items: list[CostItem] = []
        for back in range(months - 1, -1, -1):
            month = _month_start(today, back)
            month_rng = random.Random(_seed(self.provider, self.context.external_id, str(month)))
            trend = (1 + growth) ** (months - 1 - back)
            for service, base in self.profile.services:
                amount = base * scale * trend * month_rng.uniform(0.85, 1.15)
                if back == 0:  # month-to-date for the current month
                    days = calendar.monthrange(today.year, today.month)[1]
                    amount *= today.day / days
                items.append(CostItem(service=service, period_month=month, amount=_money(amount)))
        return items
