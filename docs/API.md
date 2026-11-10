# CloudOrbit API reference

Generated from the live OpenAPI schema (`/api/v1/openapi.json`); interactive docs at `/docs` (Swagger UI) and `/redoc`.
**52 operations** in 9 groups. All paths are prefixed with `/api/v1`.

## Authentication

Send `Authorization: Bearer <access_token>`. Obtain a token with `POST /api/v1/auth/login` (JSON) or `POST /api/v1/auth/token` (OAuth2 form, used by Swagger's *Authorize*).

```bash
TOKEN=$(curl -s -X POST localhost:8000/api/v1/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"admin@cloudorbit.dev","password":"CloudOrbit!2026"}' | jq -r .access_token)
curl -s localhost:8000/api/v1/dashboard/overview -H "Authorization: Bearer $TOKEN"
```

## Error envelope

Every error has the same shape:

```json
{"error": {"code": "permission_denied", "message": "Your role 'viewer' lacks the 'accounts:write' permission", "details": {}}}
```

| HTTP | `code` | When |
|---|---|---|
| 401 | `not_authenticated` | Missing/invalid/expired token, bad login (generic message) |
| 403 | `permission_denied` | Role lacks the endpoint's permission; invalid provisioning confirmation token |
| 404 | `not_found` | Unknown id |
| 409 | `conflict` | Duplicate e-mail or cloud account |
| 422 | `validation_error` | Request schema validation failed (`details.errors`) |
| 422 | `business_rule_violation` | Domain rule failed, e.g. bad template parameters (`details.fields`), expired plan, name mismatch |
| 500 | `credential_decryption_failed` / `internal_error` | Encryption key mismatch / unexpected error (no internals leaked) |
| 501 | `provider_unavailable` | Real-cloud mode without the optional SDK installed |
| 502 | `provider_error` | Cloud API or terraform call failed |

## Auth

| Method | Path | Permission | Summary |
|---|---|---|---|
| `POST` | `/api/v1/auth/register` | public | Register - Self-registration. The first user to register becomes the administrator. |
| `POST` | `/api/v1/auth/login` | public | Login |
| `POST` | `/api/v1/auth/token` | public | Login Form - OAuth2 password flow (used by the Swagger UI 'Authorize' button). |
| `GET` | `/api/v1/auth/me` | authenticated | Me |
| `PATCH` | `/api/v1/auth/me` | authenticated | Update Me |
| `POST` | `/api/v1/auth/me/password` | authenticated | Change Password |

## Users

| Method | Path | Permission | Summary |
|---|---|---|---|
| `GET` | `/api/v1/users/roles` | authenticated | Roles - Role -> permission matrix (visible to every authenticated user). |
| `GET` | `/api/v1/users` | `users:manage` | List Users |
| `POST` | `/api/v1/users` | `users:manage` | Create User |
| `PATCH` | `/api/v1/users/{user_id}` | `users:manage` | Update User |

## Cloud Accounts

| Method | Path | Permission | Summary |
|---|---|---|---|
| `GET` | `/api/v1/cloud-accounts` | `accounts:read` | List Accounts |
| `POST` | `/api/v1/cloud-accounts` | `accounts:write` | Create Account - Register an account. Credentials are validated, Fernet-encrypted and never returned. |
| `GET` | `/api/v1/cloud-accounts/{account_id}` | `accounts:read` | Get Account |
| `PATCH` | `/api/v1/cloud-accounts/{account_id}` | `accounts:write` | Update Account |
| `DELETE` | `/api/v1/cloud-accounts/{account_id}` | `accounts:write` | Delete Account |
| `PUT` | `/api/v1/cloud-accounts/{account_id}/credentials` | `accounts:write` | Rotate Credentials |
| `POST` | `/api/v1/cloud-accounts/{account_id}/validate` | `accounts:write` | Validate Account |
| `POST` | `/api/v1/cloud-accounts/{account_id}/sync` | `resources:sync` | Trigger Sync - Queue an inventory + cost sync. Executes inline when Celery runs in eager mode. |
| `GET` | `/api/v1/cloud-accounts/{account_id}/sync-jobs` | `accounts:read` | List Sync Jobs |
| `GET` | `/api/v1/cloud-accounts/sync-jobs/{job_id}` | `accounts:read` | Get Sync Job |

## Resources

| Method | Path | Permission | Summary |
|---|---|---|---|
| `GET` | `/api/v1/resources` | `resources:read` | List Resources |
| `GET` | `/api/v1/resources/changes` | `resources:read` | All Changes - Resource change history across the whole estate. |
| `GET` | `/api/v1/resources/{resource_id}` | `resources:read` | Get Resource |
| `GET` | `/api/v1/resources/{resource_id}/changes` | `resources:read` | Resource Changes |
| `GET` | `/api/v1/resources/{resource_id}/metrics` | `resources:read` | Resource Metrics |

## Infrastructure (Terraform)

| Method | Path | Permission | Summary |
|---|---|---|---|
| `GET` | `/api/v1/infrastructure/terraform` | `infra:read` | Terraform Status |
| `GET` | `/api/v1/infrastructure/templates` | `infra:read` | List Templates |
| `GET` | `/api/v1/infrastructure/templates/{key}` | `infra:read` | Get Template Detail |
| `POST` | `/api/v1/infrastructure/templates/{key}/preview` | `infra:plan` | Preview Template - Render HCL without creating a request (no plan, nothing persisted). |
| `GET` | `/api/v1/infrastructure/provisioning` | `infra:read` | List Requests |
| `POST` | `/api/v1/infrastructure/provisioning` | `infra:plan` | Create Plan - Render HCL and run `terraform plan` (or a labelled mock plan). Never applies. |
| `POST` | `/api/v1/infrastructure/decommission` | `infra:plan` | Create Destroy Plan |
| `GET` | `/api/v1/infrastructure/provisioning/{request_id}` | `infra:read` | Get Request |
| `POST` | `/api/v1/infrastructure/provisioning/{request_id}/apply` | `infra:apply` | Apply Request - Apply a planned request after explicit confirmation (token + typed resource name). |
| `POST` | `/api/v1/infrastructure/provisioning/{request_id}/cancel` | `infra:plan` | Cancel Request |

## Monitoring

| Method | Path | Permission | Summary |
|---|---|---|---|
| `GET` | `/api/v1/dashboard/overview` | `resources:read` | Overview - Resource counts, status/provider distribution, usage metrics, alerts and recent activity. |
| `GET` | `/api/v1/alerts` | `resources:read` | List Alerts |
| `POST` | `/api/v1/alerts/{alert_id}/acknowledge` | `alerts:manage` | Acknowledge |
| `POST` | `/api/v1/alerts/{alert_id}/resolve` | `alerts:manage` | Resolve |

## Costs

| Method | Path | Permission | Summary |
|---|---|---|---|
| `GET` | `/api/v1/costs/summary` | `costs:read` | Summary |
| `GET` | `/api/v1/costs/trends` | `costs:read` | Trends |
| `GET` | `/api/v1/costs/by-service` | `costs:read` | By Service |
| `GET` | `/api/v1/costs/budgets` | `costs:read` | List Budgets |
| `POST` | `/api/v1/costs/budgets` | `budgets:write` | Create Budget |
| `PATCH` | `/api/v1/costs/budgets/{budget_id}` | `budgets:write` | Update Budget |
| `DELETE` | `/api/v1/costs/budgets/{budget_id}` | `budgets:write` | Delete Budget |
| `POST` | `/api/v1/costs/budgets/evaluate` | `budgets:write` | Evaluate - Evaluate all active budgets now; returns newly created cost alerts. |
| `GET` | `/api/v1/costs/alerts` | `costs:read` | Cost Alerts |

## Audit

| Method | Path | Permission | Summary |
|---|---|---|---|
| `GET` | `/api/v1/audit/logs` | `audit:read` | Audit Logs |
| `GET` | `/api/v1/audit/access-history` | authenticated | Access History - Login history. Admins may query any user; everyone else sees only their own. |

## System

| Method | Path | Permission | Summary |
|---|---|---|---|
| `GET` | `/api/v1/health/live` | public | Live |
| `GET` | `/api/v1/health` | public | Health |

## Example: provisioning with explicit confirmation

```bash
# 1. Plan (never applies). Returns a one-time confirmation_token.
curl -s -X POST localhost:8000/api/v1/infrastructure/provisioning -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"cloud_account_id":"<id>","template_key":"aws_s3_bucket",
  "parameters":{"name":"team-reports-bucket","region":"us-east-1","versioning":true}}'
# 2. Apply: token + the resource name typed exactly. Wrong token -> 403, wrong name/expired -> 422.
curl -s -X POST localhost:8000/api/v1/infrastructure/provisioning/<request_id>/apply -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"confirmation_token":"<token>","confirm_resource_name":"team-reports-bucket"}'
```
