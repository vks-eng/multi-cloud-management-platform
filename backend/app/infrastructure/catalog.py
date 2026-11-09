"""Catalogue of Terraform templates exposed to users, with typed parameter definitions.

Parameter values are strictly validated (type, enum, regex) BEFORE rendering, and the
renderer additionally escapes every value as an HCL string literal, so user input can never
inject arbitrary HCL.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

from app.core.errors import BusinessRuleError, NotFoundError
from app.models.enums import CloudProvider, ResourceType

ParamType = Literal["string", "integer", "boolean", "enum"]

_NAME_RE = r"^[a-z][a-z0-9-]{2,40}[a-z0-9]$"
_TAG_KEY_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]{0,62}$")
_TAG_VALUE_RE = re.compile(r"^[A-Za-z0-9 _.:/=+@-]{0,128}$")


@dataclass(frozen=True, slots=True)
class TemplateParam:
    key: str
    label: str
    type: ParamType = "string"
    required: bool = True
    default: Any = None
    options: tuple[str, ...] = ()
    pattern: str | None = None
    description: str = ""
    minimum: int | None = None
    maximum: int | None = None


@dataclass(frozen=True, slots=True)
class TemplateSpec:
    key: str
    provider: CloudProvider
    resource_type: ResourceType
    title: str
    description: str
    file: str
    terraform_resources: tuple[str, ...]
    params: tuple[TemplateParam, ...] = field(default_factory=tuple)
    estimated_monthly_cost: str = ""


_NAME = TemplateParam(
    "name",
    "Resource name",
    pattern=_NAME_RE,
    description="Lowercase letters, digits and hyphens (4-42 chars).",
)

TEMPLATES: dict[str, TemplateSpec] = {
    t.key: t
    for t in (
        TemplateSpec(
            key="aws_ec2_instance",
            provider=CloudProvider.AWS,
            resource_type=ResourceType.EC2_INSTANCE,
            title="AWS EC2 instance",
            description="General purpose EC2 instance with IMDSv2 enforced and encrypted root volume.",
            file="aws_ec2_instance.tf.j2",
            terraform_resources=("aws_instance",),
            estimated_monthly_cost="$7 - $125",
            params=(
                _NAME,
                TemplateParam(
                    "region",
                    "Region",
                    "enum",
                    default="us-east-1",
                    options=("us-east-1", "us-west-2", "eu-west-1", "ap-south-1"),
                ),
                TemplateParam(
                    "instance_size",
                    "Instance type",
                    "enum",
                    default="t3.micro",
                    options=("t3.micro", "t3.medium", "m5.large", "c6i.xlarge"),
                ),
                TemplateParam(
                    "ami_id",
                    "AMI ID",
                    pattern=r"^ami-[0-9a-f]{8,17}$",
                    default="ami-0abcdef1234567890",
                ),
                TemplateParam(
                    "root_volume_gb",
                    "Root volume (GiB)",
                    "integer",
                    default=20,
                    minimum=8,
                    maximum=1024,
                ),
            ),
        ),
        TemplateSpec(
            key="aws_s3_bucket",
            provider=CloudProvider.AWS,
            resource_type=ResourceType.S3_BUCKET,
            title="AWS S3 bucket",
            description="Private S3 bucket with public access blocked, SSE and optional versioning.",
            file="aws_s3_bucket.tf.j2",
            terraform_resources=(
                "aws_s3_bucket",
                "aws_s3_bucket_public_access_block",
                "aws_s3_bucket_server_side_encryption_configuration",
                "aws_s3_bucket_versioning",
            ),
            estimated_monthly_cost="$0.023 / GB",
            params=(
                _NAME,
                TemplateParam(
                    "region",
                    "Region",
                    "enum",
                    default="us-east-1",
                    options=("us-east-1", "us-west-2", "eu-west-1", "ap-south-1"),
                ),
                TemplateParam("versioning", "Enable versioning", "boolean", default=True),
            ),
        ),
        TemplateSpec(
            key="azure_vm",
            provider=CloudProvider.AZURE,
            resource_type=ResourceType.AZURE_VM,
            title="Azure Linux virtual machine",
            description="Ubuntu VM with SSH-key auth only, in a new NIC on an existing subnet.",
            file="azure_vm.tf.j2",
            terraform_resources=("azurerm_network_interface", "azurerm_linux_virtual_machine"),
            estimated_monthly_cost="$8 - $125",
            params=(
                _NAME,
                TemplateParam(
                    "region",
                    "Location",
                    "enum",
                    default="eastus",
                    options=("eastus", "westeurope", "southeastasia", "centralindia"),
                ),
                TemplateParam(
                    "resource_group",
                    "Resource group",
                    pattern=r"^[A-Za-z0-9_.()-]{1,90}$",
                    default="rg-mcmp",
                ),
                TemplateParam(
                    "instance_size",
                    "VM size",
                    "enum",
                    default="Standard_B1s",
                    options=("Standard_B1s", "Standard_B2s", "Standard_D2s_v5", "Standard_F4s_v2"),
                ),
                TemplateParam(
                    "subnet_id",
                    "Subnet resource ID",
                    pattern=r"^/subscriptions/[A-Za-z0-9/_.()-]+$",
                    default="/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-network/providers/Microsoft.Network/virtualNetworks/vnet-main/subnets/default",
                ),
                TemplateParam(
                    "admin_username",
                    "Admin username",
                    pattern=r"^[a-z_][a-z0-9_-]{2,31}$",
                    default="azureops",
                ),
            ),
        ),
        TemplateSpec(
            key="azure_storage_account",
            provider=CloudProvider.AZURE,
            resource_type=ResourceType.AZURE_STORAGE_ACCOUNT,
            title="Azure storage account",
            description="StorageV2 account with TLS 1.2 minimum and public blob access disabled.",
            file="azure_storage_account.tf.j2",
            terraform_resources=("azurerm_storage_account",),
            estimated_monthly_cost="$0.02 / GB",
            params=(
                TemplateParam(
                    "name",
                    "Account name",
                    pattern=r"^[a-z0-9]{3,24}$",
                    description="3-24 lowercase letters and digits.",
                ),
                TemplateParam(
                    "region",
                    "Location",
                    "enum",
                    default="eastus",
                    options=("eastus", "westeurope", "southeastasia", "centralindia"),
                ),
                TemplateParam(
                    "resource_group",
                    "Resource group",
                    pattern=r"^[A-Za-z0-9_.()-]{1,90}$",
                    default="rg-mcmp",
                ),
                TemplateParam(
                    "replication",
                    "Replication",
                    "enum",
                    default="LRS",
                    options=("LRS", "ZRS", "GRS"),
                ),
            ),
        ),
        TemplateSpec(
            key="gcp_compute_instance",
            provider=CloudProvider.GCP,
            resource_type=ResourceType.GCP_COMPUTE_INSTANCE,
            title="GCP Compute Engine instance",
            description="Debian VM with Shielded VM enabled and no external IP.",
            file="gcp_compute_instance.tf.j2",
            terraform_resources=("google_compute_instance",),
            estimated_monthly_cost="$6 - $152",
            params=(
                _NAME,
                TemplateParam(
                    "region",
                    "Region",
                    "enum",
                    default="us-central1",
                    options=("us-central1", "europe-west1", "asia-south1"),
                ),
                TemplateParam(
                    "instance_size",
                    "Machine type",
                    "enum",
                    default="e2-micro",
                    options=("e2-micro", "e2-medium", "n2-standard-2", "c3-standard-4"),
                ),
                TemplateParam(
                    "image",
                    "Boot image",
                    "enum",
                    default="debian-cloud/debian-12",
                    options=("debian-cloud/debian-12", "ubuntu-os-cloud/ubuntu-2404-lts-amd64"),
                ),
            ),
        ),
        TemplateSpec(
            key="gcp_storage_bucket",
            provider=CloudProvider.GCP,
            resource_type=ResourceType.GCP_BUCKET,
            title="GCP Cloud Storage bucket",
            description="Bucket with uniform bucket-level access and public access prevention.",
            file="gcp_storage_bucket.tf.j2",
            terraform_resources=("google_storage_bucket",),
            estimated_monthly_cost="$0.020 / GB",
            params=(
                _NAME,
                TemplateParam(
                    "region",
                    "Location",
                    "enum",
                    default="us-central1",
                    options=("us-central1", "europe-west1", "asia-south1"),
                ),
                TemplateParam(
                    "storage_class",
                    "Storage class",
                    "enum",
                    default="STANDARD",
                    options=("STANDARD", "NEARLINE", "COLDLINE"),
                ),
                TemplateParam("versioning", "Enable versioning", "boolean", default=True),
            ),
        ),
    )
}


def get_template(key: str) -> TemplateSpec:
    try:
        return TEMPLATES[key]
    except KeyError:
        raise NotFoundError(f"Unknown template '{key}'") from None


def validate_parameters(spec: TemplateSpec, raw: dict[str, Any]) -> dict[str, Any]:
    """Coerce and validate user-supplied parameters. Returns the cleaned dict incl. tags."""
    errors: dict[str, str] = {}
    cleaned: dict[str, Any] = {}
    known = {p.key for p in spec.params} | {"tags"}
    for extra in set(raw) - known:
        errors[extra] = "Unknown parameter"

    for p in spec.params:
        value = raw.get(p.key, p.default)
        if value is None or value == "":
            if p.required:
                errors[p.key] = "This field is required"
            continue
        if p.type == "boolean":
            if not isinstance(value, bool):
                errors[p.key] = "Must be true or false"
                continue
        elif p.type == "integer":
            if isinstance(value, bool) or not isinstance(value, int):
                errors[p.key] = "Must be an integer"
                continue
            if (p.minimum is not None and value < p.minimum) or (
                p.maximum is not None and value > p.maximum
            ):
                errors[p.key] = f"Must be between {p.minimum} and {p.maximum}"
                continue
        else:
            if not isinstance(value, str):
                errors[p.key] = "Must be a string"
                continue
            if p.type == "enum" and value not in p.options:
                errors[p.key] = f"Must be one of: {', '.join(p.options)}"
                continue
            if p.pattern and not re.fullmatch(p.pattern, value):
                errors[p.key] = f"Invalid format ({p.description or p.pattern})"
                continue
        cleaned[p.key] = value

    tags = raw.get("tags") or {}
    if not isinstance(tags, dict):
        errors["tags"] = "Tags must be an object of key/value strings"
    else:
        for k, v in tags.items():
            if (
                not _TAG_KEY_RE.match(str(k))
                or not isinstance(v, str)
                or not _TAG_VALUE_RE.match(v)
            ):
                errors["tags"] = f"Invalid tag '{k}'"
                break
        cleaned["tags"] = {str(k): str(v) for k, v in tags.items()}

    if errors:
        raise BusinessRuleError("Invalid template parameters", details={"fields": errors})
    return cleaned
