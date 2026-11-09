"""Adapter selection (dependency-injection seam for the cloud layer)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.core.config import Settings, get_settings
from app.models.enums import CloudProvider
from app.providers.base import AccountContext, CloudProviderAdapter
from app.providers.mock import MockCloudAdapter

AdapterFactory = Callable[[AccountContext, dict[str, Any]], CloudProviderAdapter]


def _real_adapter_cls(provider: CloudProvider) -> type[CloudProviderAdapter]:
    # Imported lazily so the cloud SDKs stay optional.
    if provider == CloudProvider.AWS:
        from app.providers.aws import AwsAdapter

        return AwsAdapter
    if provider == CloudProvider.AZURE:
        from app.providers.azure import AzureAdapter

        return AzureAdapter
    from app.providers.gcp import GcpAdapter

    return GcpAdapter


def get_adapter(
    context: AccountContext,
    credentials: dict[str, Any],
    settings: Settings | None = None,
) -> CloudProviderAdapter:
    settings = settings or get_settings()
    if settings.cloud_provider_mode == "mock":
        return MockCloudAdapter(context, credentials)
    return _real_adapter_cls(context.provider)(context, credentials)
