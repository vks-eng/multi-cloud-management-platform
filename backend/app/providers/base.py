"""Common interface implemented by every cloud provider adapter (real or mock).

Services only depend on `CloudProviderAdapter`; the concrete implementation is selected by
`app.providers.factory.get_adapter` based on configuration.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from app.models.enums import CloudProvider


@dataclass(slots=True)
class AccountContext:
    """Non-secret account configuration handed to adapters alongside decrypted credentials."""

    provider: CloudProvider
    external_id: str
    default_region: str
    state: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ConnectionResult:
    ok: bool
    message: str
    identity: str | None = None


@dataclass(slots=True)
class ResourceUsage:
    cpu_percent: float | None = None
    memory_percent: float | None = None
    network_in_mb: float | None = None
    network_out_mb: float | None = None
    storage_used_gb: float | None = None


@dataclass(slots=True)
class DiscoveredResource:
    external_id: str
    name: str
    resource_type: str
    region: str
    status: str
    attributes: dict[str, Any] = field(default_factory=dict)
    tags: dict[str, str] = field(default_factory=dict)
    monthly_cost_estimate: Decimal = Decimal("0")
    usage: ResourceUsage | None = None


@dataclass(slots=True)
class CostItem:
    service: str
    period_month: date
    amount: Decimal
    currency: str = "USD"


class CloudProviderAdapter(abc.ABC):
    """Abstract adapter. Implementations must never log or return credential material."""

    provider: CloudProvider
    is_mock: bool = False

    def __init__(self, context: AccountContext, credentials: dict[str, Any]) -> None:
        self.context = context
        self._credentials = credentials

    @abc.abstractmethod
    def validate_connection(self) -> ConnectionResult:
        """Verify credentials work and identify the principal."""

    @abc.abstractmethod
    def list_resources(self) -> list[DiscoveredResource]:
        """Discover the supported resource types in this account."""

    @abc.abstractmethod
    def get_monthly_costs(self, months: int = 6) -> list[CostItem]:
        """Return monthly cost per service for the last `months` months (incl. current)."""

    def provision(
        self, resource_type: str, name: str, params: dict[str, Any]
    ) -> DiscoveredResource:
        """Directly create a resource. Real adapters provision through Terraform instead."""
        raise NotImplementedError("Provisioning is performed through Terraform for this adapter")

    def decommission(self, resource_type: str, external_id: str) -> None:
        raise NotImplementedError("Decommissioning is performed through Terraform for this adapter")

    def __repr__(self) -> str:  # never include credentials
        return f"<{type(self).__name__} {self.context.provider}:{self.context.external_id}>"
