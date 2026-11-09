"""Real GCP adapter (google-cloud-* client libraries). Optional: `pip install .[gcp]`.

Authenticates with a service account key (JSON) granted `roles/compute.viewer` and
`roles/storage.objectViewer` / a custom role with `storage.buckets.list`.
"""

from __future__ import annotations

import json
from typing import Any

from app.core.errors import ProviderError, ProviderUnavailableError
from app.models.enums import CloudProvider, ResourceStatus, ResourceType
from app.providers.base import (
    CloudProviderAdapter,
    ConnectionResult,
    CostItem,
    DiscoveredResource,
)

_GCE_STATUS = {
    "RUNNING": ResourceStatus.RUNNING,
    "TERMINATED": ResourceStatus.STOPPED,
    "STOPPED": ResourceStatus.STOPPED,
    "SUSPENDED": ResourceStatus.STOPPED,
    "PROVISIONING": ResourceStatus.PROVISIONING,
    "STAGING": ResourceStatus.PROVISIONING,
}


def _import_gcp() -> tuple[Any, Any, Any]:
    try:
        from google.cloud import compute_v1, storage
        from google.oauth2 import service_account
    except ImportError as exc:  # pragma: no cover - optional extra
        raise ProviderUnavailableError(
            "GCP support requires the optional dependency: pip install 'mcmp-backend[gcp]'"
        ) from exc
    return compute_v1, storage, service_account


class GcpAdapter(CloudProviderAdapter):
    provider = CloudProvider.GCP

    def _creds(self) -> Any:
        _, _, service_account = _import_gcp()
        info = json.loads(self._credentials["service_account_json"])
        return service_account.Credentials.from_service_account_info(info)

    def validate_connection(self) -> ConnectionResult:
        _, storage, _ = _import_gcp()
        try:
            client = storage.Client(project=self.context.external_id, credentials=self._creds())
            next(iter(client.list_buckets(max_results=1)), None)
            identity = self._creds().service_account_email
        except Exception as exc:
            return ConnectionResult(
                ok=False, message=f"GCP validation failed: {type(exc).__name__}"
            )
        return ConnectionResult(ok=True, message="Connected to GCP", identity=identity)

    def list_resources(self) -> list[DiscoveredResource]:
        compute_v1, storage, _ = _import_gcp()
        creds = self._creds()
        project = self.context.external_id
        items: list[DiscoveredResource] = []
        try:
            instances = compute_v1.InstancesClient(credentials=creds)
            request = compute_v1.AggregatedListInstancesRequest(project=project)
            for zone, scoped in instances.aggregated_list(request=request):
                for inst in scoped.instances or []:
                    zone_name = zone.split("/")[-1]
                    items.append(
                        DiscoveredResource(
                            external_id=f"projects/{project}/zones/{zone_name}/instances/{inst.name}",
                            name=inst.name,
                            resource_type=ResourceType.GCP_COMPUTE_INSTANCE,
                            region=zone_name.rsplit("-", 1)[0],
                            status=_GCE_STATUS.get(inst.status, ResourceStatus.UNKNOWN),
                            attributes={
                                "instance_size": inst.machine_type.split("/")[-1],
                                "zone": zone_name,
                            },
                            tags=dict(inst.labels or {}),
                        )
                    )
            for bucket in storage.Client(project=project, credentials=creds).list_buckets():
                items.append(
                    DiscoveredResource(
                        external_id=f"gs://{bucket.name}",
                        name=bucket.name,
                        resource_type=ResourceType.GCP_BUCKET,
                        region=(bucket.location or "").lower(),
                        status=ResourceStatus.AVAILABLE,
                        attributes={"storage_class": bucket.storage_class},
                        tags=dict(bucket.labels or {}),
                    )
                )
        except Exception as exc:
            raise ProviderError(f"GCP inventory failed: {type(exc).__name__}") from exc
        return items

    def get_monthly_costs(self, months: int = 6) -> list[CostItem]:
        # GCP billing data is only available through a BigQuery billing export. Not wired up:
        # return no data rather than fabricate numbers for a real account.
        return []
