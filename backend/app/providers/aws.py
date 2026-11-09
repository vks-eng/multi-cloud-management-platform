"""Real AWS adapter (boto3). Optional: install with `pip install .[aws]`.

Required IAM permissions (read-only): sts:GetCallerIdentity, ec2:DescribeInstances,
ec2:DescribeRegions, s3:ListAllMyBuckets, s3:GetBucketLocation, ce:GetCostAndUsage.
See docs/cloud-providers.md for a least-privilege policy.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from app.core.errors import ProviderError, ProviderUnavailableError
from app.models.enums import CloudProvider, ResourceStatus, ResourceType
from app.providers.base import (
    CloudProviderAdapter,
    ConnectionResult,
    CostItem,
    DiscoveredResource,
)

_EC2_STATE_MAP = {
    "running": ResourceStatus.RUNNING,
    "stopped": ResourceStatus.STOPPED,
    "stopping": ResourceStatus.STOPPED,
    "pending": ResourceStatus.PROVISIONING,
    "terminated": ResourceStatus.TERMINATED,
    "shutting-down": ResourceStatus.TERMINATED,
}


def _import_boto3() -> Any:
    try:
        import boto3
    except ImportError as exc:  # pragma: no cover - depends on optional extra
        raise ProviderUnavailableError(
            "AWS support requires the optional dependency: pip install 'mcmp-backend[aws]'"
        ) from exc
    return boto3


class AwsAdapter(CloudProviderAdapter):
    provider = CloudProvider.AWS

    def _session(self) -> Any:
        boto3 = _import_boto3()
        return boto3.session.Session(
            aws_access_key_id=self._credentials.get("access_key_id"),
            aws_secret_access_key=self._credentials.get("secret_access_key"),
            aws_session_token=self._credentials.get("session_token") or None,
            region_name=self.context.default_region,
        )

    def validate_connection(self) -> ConnectionResult:
        try:
            identity = self._session().client("sts").get_caller_identity()
        except ProviderUnavailableError:
            raise
        except Exception as exc:
            return ConnectionResult(
                ok=False, message=f"AWS validation failed: {type(exc).__name__}"
            )
        if identity.get("Account") != self.context.external_id:
            return ConnectionResult(
                ok=False,
                message="Credentials belong to a different AWS account than configured",
            )
        return ConnectionResult(ok=True, message="Connected to AWS", identity=identity.get("Arn"))

    def list_resources(self) -> list[DiscoveredResource]:
        session = self._session()
        items: list[DiscoveredResource] = []
        try:
            regions = self._credentials.get("regions") or [self.context.default_region]
            for region in regions:
                ec2 = session.client("ec2", region_name=region)
                for page in ec2.get_paginator("describe_instances").paginate():
                    for reservation in page.get("Reservations", []):
                        for inst in reservation.get("Instances", []):
                            tags = {t["Key"]: t["Value"] for t in inst.get("Tags", [])}
                            items.append(
                                DiscoveredResource(
                                    external_id=inst["InstanceId"],
                                    name=tags.get("Name", inst["InstanceId"]),
                                    resource_type=ResourceType.EC2_INSTANCE,
                                    region=region,
                                    status=_EC2_STATE_MAP.get(
                                        inst["State"]["Name"], ResourceStatus.UNKNOWN
                                    ),
                                    attributes={
                                        "instance_size": inst.get("InstanceType"),
                                        "private_ip": inst.get("PrivateIpAddress"),
                                        "image_id": inst.get("ImageId"),
                                        "launch_time": str(inst.get("LaunchTime")),
                                    },
                                    tags=tags,
                                )
                            )
            s3 = session.client("s3")
            for bucket in s3.list_buckets().get("Buckets", []):
                loc = s3.get_bucket_location(Bucket=bucket["Name"]).get("LocationConstraint")
                items.append(
                    DiscoveredResource(
                        external_id=f"arn:aws:s3:::{bucket['Name']}",
                        name=bucket["Name"],
                        resource_type=ResourceType.S3_BUCKET,
                        region=loc or "us-east-1",
                        status=ResourceStatus.AVAILABLE,
                        attributes={"created": str(bucket.get("CreationDate"))},
                    )
                )
        except Exception as exc:
            raise ProviderError(f"AWS inventory failed: {type(exc).__name__}") from exc
        return items

    def get_monthly_costs(self, months: int = 6) -> list[CostItem]:
        today = datetime.now(UTC).date()
        idx = today.year * 12 + today.month - 1 - (months - 1)
        start = date(idx // 12, idx % 12 + 1, 1)
        try:
            ce = self._session().client("ce", region_name="us-east-1")
            result = ce.get_cost_and_usage(
                TimePeriod={"Start": start.isoformat(), "End": today.isoformat()},
                Granularity="MONTHLY",
                Metrics=["UnblendedCost"],
                GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
            )
        except Exception as exc:
            raise ProviderError(f"AWS Cost Explorer failed: {type(exc).__name__}") from exc
        items: list[CostItem] = []
        for period in result.get("ResultsByTime", []):
            month = date.fromisoformat(period["TimePeriod"]["Start"]).replace(day=1)
            for group in period.get("Groups", []):
                metric = group["Metrics"]["UnblendedCost"]
                items.append(
                    CostItem(
                        service=group["Keys"][0],
                        period_month=month,
                        amount=Decimal(metric["Amount"]).quantize(Decimal("0.01")),
                        currency=metric.get("Unit", "USD"),
                    )
                )
        return items
