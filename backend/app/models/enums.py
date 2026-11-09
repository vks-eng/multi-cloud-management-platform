"""Domain enumerations (stored as strings for migration friendliness)."""

from __future__ import annotations

from enum import StrEnum


class CloudProvider(StrEnum):
    AWS = "aws"
    AZURE = "azure"
    GCP = "gcp"


class AccountStatus(StrEnum):
    PENDING = "pending"
    CONNECTED = "connected"
    ERROR = "error"


class ResourceType(StrEnum):
    EC2_INSTANCE = "ec2_instance"
    S3_BUCKET = "s3_bucket"
    AZURE_VM = "azure_vm"
    AZURE_STORAGE_ACCOUNT = "azure_storage_account"
    GCP_COMPUTE_INSTANCE = "gcp_compute_instance"
    GCP_BUCKET = "gcp_bucket"


RESOURCE_TYPE_PROVIDER: dict[ResourceType, CloudProvider] = {
    ResourceType.EC2_INSTANCE: CloudProvider.AWS,
    ResourceType.S3_BUCKET: CloudProvider.AWS,
    ResourceType.AZURE_VM: CloudProvider.AZURE,
    ResourceType.AZURE_STORAGE_ACCOUNT: CloudProvider.AZURE,
    ResourceType.GCP_COMPUTE_INSTANCE: CloudProvider.GCP,
    ResourceType.GCP_BUCKET: CloudProvider.GCP,
}

COMPUTE_TYPES = {
    ResourceType.EC2_INSTANCE,
    ResourceType.AZURE_VM,
    ResourceType.GCP_COMPUTE_INSTANCE,
}


class ResourceStatus(StrEnum):
    RUNNING = "running"
    STOPPED = "stopped"
    AVAILABLE = "available"
    PROVISIONING = "provisioning"
    ERROR = "error"
    TERMINATED = "terminated"
    DELETED = "deleted"
    UNKNOWN = "unknown"


class ChangeType(StrEnum):
    CREATED = "created"
    UPDATED = "updated"
    STATUS_CHANGED = "status_changed"
    DELETED = "deleted"


class ChangeSource(StrEnum):
    SYNC = "sync"
    PROVISIONING = "provisioning"
    MANUAL = "manual"


class SyncStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ProvisioningAction(StrEnum):
    CREATE = "create"
    DESTROY = "destroy"


class ProvisioningStatus(StrEnum):
    PLANNED = "planned"
    APPLYING = "applying"
    APPLIED = "applied"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class AlertSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertStatus(StrEnum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class AlertCategory(StrEnum):
    RESOURCE = "resource"
    ACCOUNT = "account"
    COST = "cost"
    SECURITY = "security"


class AuditStatus(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
