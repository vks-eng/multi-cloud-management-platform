"""Real Azure adapter (Azure SDK for Python). Optional: `pip install .[azure]`.

Authenticates with a service principal (tenant_id, client_id, client_secret) that should be
assigned the built-in **Reader** role on the subscription (plus **Cost Management Reader**
if cost data is required).
"""

from __future__ import annotations

from typing import Any

from app.core.errors import ProviderError, ProviderUnavailableError
from app.models.enums import CloudProvider, ResourceStatus, ResourceType
from app.providers.base import (
    CloudProviderAdapter,
    ConnectionResult,
    CostItem,
    DiscoveredResource,
)


def _import_azure() -> tuple[Any, Any, Any, Any]:
    try:
        from azure.identity import ClientSecretCredential
        from azure.mgmt.compute import ComputeManagementClient
        from azure.mgmt.resource import SubscriptionClient
        from azure.mgmt.storage import StorageManagementClient
    except ImportError as exc:  # pragma: no cover - optional extra
        raise ProviderUnavailableError(
            "Azure support requires the optional dependency: pip install 'mcmp-backend[azure]'"
        ) from exc
    return (
        ClientSecretCredential,
        ComputeManagementClient,
        StorageManagementClient,
        SubscriptionClient,
    )


class AzureAdapter(CloudProviderAdapter):
    provider = CloudProvider.AZURE

    def _credential(self) -> Any:
        client_secret_credential = _import_azure()[0]
        return client_secret_credential(
            tenant_id=self._credentials["tenant_id"],
            client_id=self._credentials["client_id"],
            client_secret=self._credentials["client_secret"],
        )

    def validate_connection(self) -> ConnectionResult:
        _, _, _, subscription_client = _import_azure()
        try:
            client = subscription_client(self._credential())
            sub = client.subscriptions.get(self.context.external_id)
        except Exception as exc:
            return ConnectionResult(
                ok=False, message=f"Azure validation failed: {type(exc).__name__}"
            )
        return ConnectionResult(
            ok=True, message="Connected to Azure", identity=f"{sub.display_name} ({sub.state})"
        )

    def list_resources(self) -> list[DiscoveredResource]:
        _, compute_client_cls, storage_client_cls, _ = _import_azure()
        cred = self._credential()
        sub = self.context.external_id
        items: list[DiscoveredResource] = []
        try:
            compute = compute_client_cls(cred, sub)
            for vm in compute.virtual_machines.list_all():
                status = ResourceStatus.UNKNOWN
                try:
                    rg = vm.id.split("/")[4]
                    view = compute.virtual_machines.instance_view(rg, vm.name)
                    codes = [s.code for s in view.statuses or []]
                    if "PowerState/running" in codes:
                        status = ResourceStatus.RUNNING
                    elif any(c in codes for c in ("PowerState/stopped", "PowerState/deallocated")):
                        status = ResourceStatus.STOPPED
                except Exception:  # noqa: S110 - instance view is best effort
                    pass
                items.append(
                    DiscoveredResource(
                        external_id=vm.id,
                        name=vm.name,
                        resource_type=ResourceType.AZURE_VM,
                        region=vm.location,
                        status=status,
                        attributes={"instance_size": vm.hardware_profile.vm_size},
                        tags=dict(vm.tags or {}),
                    )
                )
            storage = storage_client_cls(cred, sub)
            for acct in storage.storage_accounts.list():
                items.append(
                    DiscoveredResource(
                        external_id=acct.id,
                        name=acct.name,
                        resource_type=ResourceType.AZURE_STORAGE_ACCOUNT,
                        region=acct.location,
                        status=ResourceStatus.AVAILABLE,
                        attributes={"sku": acct.sku.name if acct.sku else None, "kind": acct.kind},
                        tags=dict(acct.tags or {}),
                    )
                )
        except Exception as exc:
            raise ProviderError(f"Azure inventory failed: {type(exc).__name__}") from exc
        return items

    def get_monthly_costs(self, months: int = 6) -> list[CostItem]:
        # Azure Cost Management queries require the azure-mgmt-costmanagement package and the
        # Cost Management Reader role. Not wired up yet: report no cost data rather than guess.
        return []
