# Connecting real AWS, Azure and GCP accounts

CloudOrbit runs on **mock adapters by default** (`CLOUD_PROVIDER_MODE=mock`). The real adapters live in
`backend/app/providers/{aws,azure,gcp}.py` and are imported lazily, so the SDKs are optional extras.

> **Verification status:** the real adapters are implemented against the documented SDK APIs, but they are
> **not exercised by the automated test-suite or CI** (no cloud credentials there). Test them in a sandbox
> account before relying on them.

```bash
cd backend
pip install -r requirements-cloud.txt          # or: pip install -e ".[aws,azure,gcp]"
export CLOUD_PROVIDER_MODE=real
```

When the mode is `real` and an SDK is missing, the API answers `501 provider_unavailable` with the install
command. Nothing silently falls back to mock data.

## Principle: read-only for inventory, separate identity for Terraform

* The credentials stored in CloudOrbit are used for **inventory, validation and cost reads**. Give them
  **read-only** permissions.
* Real `terraform apply` is disabled unless `TERRAFORM_APPLY_ENABLED=true`. If you enable it, the same
  stored credentials are passed to Terraform as environment variables for that run only, so use a
  **separate CloudOrbit account entry** whose principal is scoped to what the templates create.
* Prefer short-lived credentials (AWS STS session tokens, Azure workload identity, GCP short-lived keys)
  and rotate with `PUT /api/v1/cloud-accounts/{id}/credentials`.

## AWS

Payload: `{"access_key_id": "...", "secret_access_key": "...", "session_token": "...optional"}`.
`validate` calls `sts:GetCallerIdentity` and checks the account id matches the one you registered.

Least-privilege inventory + cost policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "CloudOrbitInventory",
      "Effect": "Allow",
      "Action": [
        "sts:GetCallerIdentity",
        "ec2:DescribeInstances",
        "s3:ListAllMyBuckets",
        "s3:GetBucketLocation",
        "ce:GetCostAndUsage"
      ],
      "Resource": "*"
    }
  ]
}
```

Terraform principal (only if applies are enabled), scoped to the `aws_ec2_instance` and `aws_s3_bucket`
templates: `ec2:RunInstances`, `ec2:CreateTags`, `ec2:Describe*`, `s3:CreateBucket`,
`s3:PutBucketPublicAccessBlock`, `s3:PutEncryptionConfiguration`, `s3:PutBucketVersioning`,
`s3:PutBucketTagging`, `s3:Get*` on `arn:aws:s3:::<your-prefix>-*`. Add a permissions boundary and
restrict `aws:RequestedRegion`.

## Azure

Payload: `{"tenant_id": "...", "client_id": "...", "client_secret": "..."}` (service principal).

```bash
az ad sp create-for-rbac --name cloudorbit-reader --role Reader \
  --scopes /subscriptions/<subscription-id>
```

* Inventory: built-in **Reader** on the subscription.
* Costs: the Azure cost adapter is **not implemented yet** and returns no data. **Cost Management Reader**
  will be needed once it is.
* Terraform (optional): a custom role limited to `Microsoft.Compute/virtualMachines/*`,
  `Microsoft.Network/networkInterfaces/*` and `Microsoft.Storage/storageAccounts/*` on the target
  resource group, never Contributor on the whole subscription.

## GCP

Payload: `{"service_account_json": "<contents of the key file>"}`.

```bash
gcloud iam service-accounts create cloudorbit-viewer
gcloud projects add-iam-policy-binding <project> \
  --member serviceAccount:cloudorbit-viewer@<project>.iam.gserviceaccount.com --role roles/compute.viewer
gcloud projects add-iam-policy-binding <project> \
  --member serviceAccount:cloudorbit-viewer@<project>.iam.gserviceaccount.com --role roles/storage.objectViewer
```

* Costs: GCP billing data needs a BigQuery billing export. The GCP cost adapter is **not implemented yet**
  and returns no data.
* Prefer Workload Identity Federation over long-lived keys where your hosting platform supports it.

## Terraform binary

`TERRAFORM_MODE=auto` runs the real binary only when it is on `PATH` **and** `CLOUD_PROVIDER_MODE=real`.
Plans run in `TERRAFORM_WORKDIR/<request-id>/` with `terraform init -input=false` and
`terraform plan -out=tfplan`. Apply runs `terraform apply tfplan` (the saved plan, exactly what was
reviewed). The workdir uses local state, so for production you should add a remote backend
(S3 + DynamoDB lock / Azure Blob / GCS) to the templates. That is on the roadmap.
