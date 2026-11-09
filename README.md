# CloudOrbit: Multi-Cloud Management Platform (AWS · Azure · GCP)

**One dashboard to inventory, provision, monitor and cost-control AWS, Azure and GCP: role-based access, encrypted credentials, Terraform with an explicit confirmation step, and a full audit trail.**

[![CI](https://github.com/vks-eng/multi-cloud-management-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/vks-eng/multi-cloud-management-platform/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)
![TypeScript](https://img.shields.io/badge/TypeScript-5.6-3178C6?logo=typescript&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)
![Terraform](https://img.shields.io/badge/Terraform-HCL%20templates-7B42BC?logo=terraform&logoColor=white)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> Runs fully offline by default. **Mock cloud adapters** simulate AWS, Azure and GCP, so you can explore every feature without a cloud account. To use real clouds, install the optional SDK extras and set `CLOUD_PROVIDER_MODE=real` (see [Enabling real clouds](#enabling-real-aws--azure--gcp)).

## Why this project

Teams running workloads on more than one cloud usually end up with three consoles, three billing views and no shared audit trail. CloudOrbit puts them behind one API and one UI. It gives you a normalised resource inventory, per-provider cost comparison with budget alerts, and Terraform provisioning where nothing changes until a human has reviewed the plan and typed the resource name to confirm. Every action is recorded. The codebase is meant as a reference for building this kind of internal platform properly: layered architecture, provider adapters behind one interface, credentials encrypted at rest, and tests that run against real PostgreSQL.

## Highlights

- **Unified inventory**: EC2, S3, Azure VMs, Azure storage accounts, GCE instances and GCS buckets, with status, metadata, tags, cost estimate and full change history.
- **Provider-adapter architecture**: AWS, Azure and GCP adapters sit behind one interface, plus deterministic mock adapters. Configuration picks which one runs.
- **Safe Terraform workflow**: templates render to real HCL, then `terraform plan` (or a clearly labelled mock plan) runs. Apply needs a one-time token and the typed resource name, and is audited. Nothing is applied automatically.
- **Secure secrets**: cloud credentials are Fernet-encrypted at rest (key rotation via MultiFernet), never returned by the API, and redacted from logs.
- **RBAC**: `admin`, `operator` and `viewer` roles over 12 fine-grained permissions, enforced on every endpoint.
- **Cost management**: month-to-date spend, forecast, provider comparison, 6-month trends, cost by service, budgets with threshold alerts.
- **Monitoring**: resource counts, status and provider distribution, CPU/memory/network usage series, operational alerts with de-duplication.
- **Audit & security**: activity log, login/access history, resource change history, role permission matrix.
- **Production-minded DevOps**: Docker Compose (Postgres, Redis, API, Celery worker + beat, frontend), GitHub Actions CI, Alembic migrations, seed script.

## Table of contents

- [Why this project](#why-this-project)
- [Skills demonstrated](#skills-demonstrated)
- [Architecture](#architecture)
- [Features by module](#features-by-module)
- [Screenshots](#screenshots)
- [Tech stack](#tech-stack)
- [Quick start](#quick-start)
- [Configuration](#configuration)
- [API overview](#api-overview)
- [Terraform workflow](#terraform-workflow)
- [Enabling real AWS / Azure / GCP](#enabling-real-aws--azure--gcp)
- [Mock vs real](#mock-vs-real)
- [Testing](#testing)
- [Deployment](#deployment)
- [Project structure](#project-structure)
- [Roadmap](#roadmap)
- [License](#license) · [Author](#author)

## Skills demonstrated

- Backend API design with **FastAPI + Pydantic v2**: typed request/response schemas, a consistent error envelope, OpenAPI docs
- **Clean layered architecture**: API, service, repository and adapter layers, with dependency injection
- **SQLAlchemy 2.0 + PostgreSQL + Alembic**: JSONB, constraints, aggregate queries, migrations tested up and down
- **Security engineering**: JWT, bcrypt, RBAC, Fernet encryption at rest, log redaction, audit trail, login-enumeration resistance
- **Cloud integration**: boto3, Azure SDK and Google Cloud client adapters behind a common interface
- **Infrastructure as Code**: Jinja2 to HCL rendering with injection-safe escaping, a Terraform plan/apply runner, a confirmation gate
- **Background processing**: Celery tasks and a beat schedule with Redis, plus an eager in-process mode for development and tests
- **Frontend engineering**: React 18, TypeScript, React Query, React Router protected routes, Tailwind design system, Recharts dashboards
- **Testing**: Pytest against real PostgreSQL, Vitest + React Testing Library
- **DevOps**: Dockerfiles, Docker Compose, GitHub Actions CI with a Postgres service, CodeQL, Dependabot, pre-commit, Makefile

## Architecture

```mermaid
flowchart LR
  subgraph Client
    UI["React + TypeScript SPA<br/>React Query · Tailwind · Recharts"]
  end
  subgraph Backend["FastAPI backend"]
    API["API layer<br/>routers · auth · RBAC deps"]
    SVC["Service layer<br/>accounts · inventory · provisioning<br/>costs · alerts · audit"]
    REPO["Repository layer<br/>SQLAlchemy 2.0"]
    ADP["Cloud adapter layer<br/>AWS · Azure · GCP · Mock"]
    TF["Terraform module<br/>catalog · renderer · runner"]
  end
  subgraph Workers
    W["Celery worker + beat<br/>scheduled sync · budgets"]
  end
  DB[(PostgreSQL)]
  R[(Redis)]
  CLOUD{{"AWS / Azure / GCP APIs"}}
  TFBIN[["terraform CLI (optional)"]]

  UI -- "JWT / REST /api/v1" --> API
  API --> SVC --> REPO --> DB
  SVC --> ADP --> CLOUD
  SVC --> TF --> TFBIN
  API -- enqueue --> R --> W
  W --> SVC
```

See **[ARCHITECTURE.md](ARCHITECTURE.md)** for container and sequence diagrams, the ER model and design decisions.

## Features by module

| Module | What you get |
|---|---|
| **Auth & users** | Registration (the first user becomes admin), login with JWT, OAuth2 password flow for Swagger, profile editing, password change, admin user management (create, change role, deactivate), role/permission matrix |
| **Cloud accounts** | AWS account / Azure subscription / GCP project registration with provider-specific validation, Fernet-encrypted credentials, credential rotation, non-secret credential hint, connection validation, per-account sync jobs |
| **Resource inventory** | Sync job reconciles discovered resources: create, update, status change, delete, each with history. Filter, search, sort and paginate. Resource detail with metrics and change log |
| **Infrastructure** | 6 Terraform templates (EC2, S3, Azure VM, Azure Storage, GCE, GCS) with typed parameters, HCL preview, plan, confirm with token and typed name, apply, cancel, decommission (destroy plan), provisioning history, lifecycle tracking |
| **Monitoring** | Totals, running/stopped compute, provider/status/type/region distribution, CPU/memory/network series, high-CPU and public-storage alerts, account health, recent activity |
| **Cost management** | MTD spend, forecast, change vs last month, provider comparison, monthly trends, cost by service, budgets scoped to all/provider/account with threshold + 100% alerts |
| **Audit & security** | Append-only audit log (redacted details), login access history, resource change history, RBAC matrix, encrypted secret storage |

## Screenshots

> Placeholders: capture these from the seeded demo (see [docs/screenshots/README.md](docs/screenshots/README.md)).

| Overview | Resource inventory |
|---|---|
| ![Overview dashboard](docs/screenshots/overview.png) | ![Resource inventory](docs/screenshots/resources.png) |
| **Terraform plan & confirm** | **Cost analytics** |
| ![Provisioning](docs/screenshots/infrastructure.png) | ![Costs](docs/screenshots/costs.png) |
| **Cloud accounts** | **Activity logs** |
| ![Accounts](docs/screenshots/accounts.png) | ![Activity](docs/screenshots/activity.png) |

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic, psycopg 3 |
| Database / queue | PostgreSQL 16 (only supported DB), Redis 7, Celery 5 |
| Security | PyJWT (HS256), bcrypt, cryptography (Fernet/MultiFernet) |
| Cloud | boto3, Azure SDK (identity, mgmt-compute/storage/resource), google-cloud-compute/storage (all optional extras) |
| IaC | Terraform (HCL generated from Jinja2 templates) |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, TanStack React Query, React Router, Recharts, lucide-react |
| Testing | Pytest, pytest-cov, Vitest, React Testing Library, jsdom |
| DevOps | Docker, Docker Compose, GitHub Actions, CodeQL, Dependabot, pre-commit, Ruff, ESLint |

## Quick start

### Option A: Docker Compose (recommended)

```bash
cp .env.example .env            # then set JWT_SECRET_KEY and CREDENTIALS_ENCRYPTION_KEYS
docker compose up -d --build    # postgres, redis, api, worker, beat, frontend
docker compose exec api python -m app.seed   # optional demo data (mock providers)
```

- Frontend: http://localhost:5173
- API docs (Swagger UI): http://localhost:8000/docs · ReDoc: http://localhost:8000/redoc

The API container runs `alembic upgrade head` on start.

### Option B: Local development

Prerequisites: Python 3.12+, Node 20+, and a PostgreSQL 14+ server. Redis is **not** required locally: with `CELERY_TASK_ALWAYS_EAGER=true`, sync jobs run in-process.

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
export DATABASE_URL=postgresql+psycopg://mcmp:mcmp@localhost:5432/mcmp
alembic upgrade head
python -m app.seed                 # demo data
uvicorn app.main:app --reload      # http://localhost:8000/docs

# Frontend (second terminal)
cd frontend
npm install
npm run dev                        # http://localhost:5173 (proxies /api to :8000)
```

### Make targets

`make install`, `make dev-backend`, `make dev-frontend`, `make lint`, `make format`, `make test`, `make test-backend`, `make test-frontend`, `make migrate`, `make seed`, `make up`, `make down`, `make logs`, `make build`, `make clean`. Run `make help` for descriptions.

### Demo login (LOCAL DEVELOPMENT ONLY)

Created by `python -m app.seed`. Never seed a shared or internet-facing environment.

| Role | E-mail | Password |
|---|---|---|
| admin | `admin@cloudorbit.dev` | `CloudOrbit!2026` |
| operator | `operator@cloudorbit.dev` | `CloudOrbit!2026` |
| viewer | `viewer@cloudorbit.dev` | `CloudOrbit!2026` |

## Configuration

All settings are environment variables (see [`.env.example`](.env.example)).

| Variable | Default | Description |
|---|---|---|
| `ENVIRONMENT` | `development` | `development` / `test` / `production`. Production refuses insecure secrets. |
| `DATABASE_URL` | `postgresql+psycopg://mcmp:mcmp@localhost:5432/mcmp` | PostgreSQL URL (non-Postgres URLs are rejected) |
| `LOG_LEVEL` | `INFO` | Python log level |
| `API_PREFIX` | `/api/v1` | API route prefix |
| `JWT_SECRET_KEY` | insecure dev value | HMAC key for JWTs (at least 32 chars in production) |
| `JWT_ALGORITHM` | `HS256` | JWT signing algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | Access-token lifetime |
| `ALLOW_SELF_REGISTRATION` | `true` | Allow public sign-up (the first user always becomes admin) |
| `CREDENTIALS_ENCRYPTION_KEYS` | *(empty: dev-derived key)* | Comma-separated Fernet keys; the first encrypts, all decrypt. **Required in production.** |
| `CLOUD_PROVIDER_MODE` | `mock` | `mock` (simulated) or `real` (cloud SDKs) |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis URL (default broker/result backend) |
| `CELERY_BROKER_URL` | *(REDIS_URL)* | Override broker |
| `CELERY_RESULT_BACKEND` | *(REDIS_URL)* | Override result backend |
| `CELERY_TASK_ALWAYS_EAGER` | `true` | Run tasks in-process (no Redis/worker needed) |
| `SYNC_INTERVAL_MINUTES` | `60` | Celery beat interval for scheduled syncs |
| `TERRAFORM_BINARY` | `terraform` | Terraform executable name/path |
| `TERRAFORM_WORKDIR` | `.terraform-runs` | Working directory for plan files |
| `TERRAFORM_MODE` | `auto` | `auto`: real terraform when the binary exists **and** `CLOUD_PROVIDER_MODE=real`; `mock`: always mock |
| `TERRAFORM_APPLY_ENABLED` | `false` | Must be `true` before a real `terraform apply` can run (confirmation is still required) |
| `PROVISIONING_CONFIRMATION_TTL_MINUTES` | `30` | Lifetime of the plan confirmation token |
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Allowed browser origins |
| `VITE_API_BASE_URL` *(frontend)* | `/api/v1` | API base URL baked into the frontend build |

Generate a Fernet key with:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## API overview

Interactive docs: **`/docs`** (Swagger UI) and **`/redoc`**. Full reference with examples and error codes: **[docs/API.md](docs/API.md)**. Postman: **[postman_collection.json](postman_collection.json)**.

All routes are prefixed with `/api/v1`. Errors use one envelope: `{"error": {"code", "message", "details"}}`.

| Module | Endpoints | Permission |
|---|---|---|
| Auth | `POST /auth/register`, `POST /auth/login`, `POST /auth/token`, `GET/PATCH /auth/me`, `POST /auth/me/password` | public / authenticated |
| Users | `GET /users/roles`, `GET/POST /users`, `PATCH /users/{id}` | `users:manage` (roles: any user) |
| Cloud accounts | `GET/POST /cloud-accounts`, `GET/PATCH/DELETE /cloud-accounts/{id}`, `PUT /cloud-accounts/{id}/credentials`, `POST /cloud-accounts/{id}/validate`, `POST /cloud-accounts/{id}/sync`, `GET /cloud-accounts/{id}/sync-jobs`, `GET /cloud-accounts/sync-jobs/{job_id}` | `accounts:read` / `accounts:write` / `resources:sync` |
| Resources | `GET /resources`, `GET /resources/changes`, `GET /resources/{id}`, `GET /resources/{id}/changes`, `GET /resources/{id}/metrics` | `resources:read` |
| Infrastructure | `GET /infrastructure/terraform`, `GET /infrastructure/templates[/{key}]`, `POST /infrastructure/templates/{key}/preview`, `GET/POST /infrastructure/provisioning`, `GET /infrastructure/provisioning/{id}`, `POST /infrastructure/provisioning/{id}/apply`, `POST /infrastructure/provisioning/{id}/cancel`, `POST /infrastructure/decommission` | `infra:read` / `infra:plan` / `infra:apply` |
| Monitoring | `GET /dashboard/overview`, `GET /alerts`, `POST /alerts/{id}/acknowledge`, `POST /alerts/{id}/resolve` | `resources:read` / `alerts:manage` |
| Costs | `GET /costs/summary`, `GET /costs/trends`, `GET /costs/by-service`, `GET/POST /costs/budgets`, `PATCH/DELETE /costs/budgets/{id}`, `POST /costs/budgets/evaluate`, `GET /costs/alerts` | `costs:read` / `budgets:write` |
| Audit | `GET /audit/logs`, `GET /audit/access-history` | `audit:read` (access history: own entries for non-admins) |
| System | `GET /health`, `GET /health/live` | public |

## Terraform workflow

```text
choose template ─► fill typed parameters ─► preview HCL ─► PLAN ─► review plan ─► CONFIRM (token + typed name) ─► APPLY ─► inventory + history
```

1. **Templates** (`backend/app/infrastructure/templates/*.tf.j2`) produce hardened HCL: IMDSv2, encrypted volumes, blocked public access, TLS 1.2, Shielded VM, no external IPs.
2. **Validation**: parameters are type-, enum- and regex-checked, and every value is emitted as an escaped HCL string literal (with `${`/`%{` interpolation neutralised), so user input cannot inject HCL.
3. **Plan**: `TerraformRunner` runs `terraform init` + `terraform plan -out=tfplan` in an isolated working directory when the binary is on `PATH`, `TERRAFORM_MODE=auto` and `CLOUD_PROVIDER_MODE=real`. Otherwise it returns a **mock plan** headed `[MOCK PLAN] Terraform was NOT executed…`, and `plan_is_mock=true` is stored.
4. **Confirm**: the plan response includes a one-time `confirmation_token`. Only its SHA-256 hash is stored, and it expires after 30 minutes. `POST …/apply` requires the token **and** `confirm_resource_name` typed exactly, plus the `infra:apply` permission. Failed attempts are audited.
5. **Apply**: mock plans are applied through the mock adapter (the resource appears in inventory with a `provisioning` change record). Real plans run `terraform apply tfplan` **only** if `TERRAFORM_APPLY_ENABLED=true`. There is never an auto-apply, and destroy is only offered for mock-managed resources.

## Enabling real AWS / Azure / GCP

```bash
pip install -e ".[aws]"      # boto3
pip install -e ".[azure]"    # azure-identity, azure-mgmt-*
pip install -e ".[gcp]"      # google-cloud-compute, google-cloud-storage
# or: pip install -r requirements-cloud.txt   (pinned optional SDKs: backend/requirements-cloud.txt)
export CLOUD_PROVIDER_MODE=real
```

Use **read-only principals** for inventory. Grant write access only to the identity that runs Terraform, and only if you enable `TERRAFORM_APPLY_ENABLED`.

| Provider | Credentials (API payload) | Least-privilege permissions |
|---|---|---|
| AWS | `access_key_id`, `secret_access_key`, optional `session_token` (prefer short-lived STS credentials) | `sts:GetCallerIdentity`, `ec2:DescribeInstances`, `s3:ListAllMyBuckets`, `s3:GetBucketLocation`, `ce:GetCostAndUsage` |
| Azure | service principal `tenant_id`, `client_id`, `client_secret` | Built-in **Reader** on the subscription (+ **Cost Management Reader** for costs) |
| GCP | `service_account_json` (key file contents) | `roles/compute.viewer`, plus `storage.buckets.list` (e.g. `roles/storage.objectViewer` or a custom role) |

Pinned optional SDKs: [`backend/requirements-cloud.txt`](backend/requirements-cloud.txt). Full policies and Terraform-runner guidance: **[docs/cloud-providers.md](docs/cloud-providers.md)**.

## Mock vs real

| Capability | Mock mode (default) | Real mode |
|---|---|---|
| Connection validation | Simulated; credentials containing `invalid` fail | STS / Subscription API / GCS API call |
| Inventory sync | Deterministic per-account estate with hourly drift (status flips, CPU) | boto3 / Azure SDK / GCP client calls (**implemented, not exercised in CI**) |
| Usage metrics | Simulated CPU / memory / network | Not collected yet (CloudWatch / Azure Monitor / Cloud Monitoring is on the roadmap) |
| Costs | Simulated 6-month history per service | AWS Cost Explorer. Azure and GCP return no data yet (they need Cost Management / BigQuery billing export) |
| Terraform plan | Labelled mock plan from the rendered HCL | Real `terraform plan` when the binary is installed |
| Terraform apply | Simulated via the mock adapter | `terraform apply tfplan`, only with `TERRAFORM_APPLY_ENABLED=true` |
| Credential encryption, RBAC, audit, alerts, budgets | **Real** in both modes | **Real** in both modes |

## Testing

```bash
make test               # backend + frontend
cd backend && pytest --cov=app        # needs PostgreSQL (see below)
cd frontend && npm test && npm run typecheck && npm run lint && npm run build
```

The backend suite runs **only against PostgreSQL**. The fixtures pick a database in this order:

1. `TEST_DATABASE_URL` if set (CI uses a `postgres:16` service container),
2. an embedded throwaway server from the `pgserver` package (Python ≤ 3.12),
3. a throwaway cluster created with `initdb`/`pg_ctl` from `PG_BIN_DIR`.

Migrations are applied with `alembic upgrade head` at session start, so tests also exercise the migration.

| Suite | Result |
|---|---|
| Backend (pytest) | TBD |
| Backend coverage | TBD |
| Frontend (Vitest + RTL) | TBD |

## Deployment

- **Docker Compose on a VM**: see [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md). Put TLS termination (Caddy/Nginx) in front and set strong secrets.
- **AWS reference**: ECS Fargate (api, worker, beat), RDS PostgreSQL, ElastiCache Redis, S3 + CloudFront for the SPA, secrets in AWS Secrets Manager.
- Production checklist: `ENVIRONMENT=production`, unique `JWT_SECRET_KEY`, `CREDENTIALS_ENCRYPTION_KEYS` from a secret manager, `ALLOW_SELF_REGISTRATION=false`, `CELERY_TASK_ALWAYS_EAGER=false`, restricted `CORS_ORIGINS`, and no seed data.

## Project structure

```text
multi-cloud-management-platform/
├── backend/
│   ├── app/
│   │   ├── api/              # FastAPI routers + dependencies (auth, RBAC)
│   │   ├── core/             # config, security, crypto, errors, logging, permissions
│   │   ├── db/               # declarative base, engine/session
│   │   ├── infrastructure/   # Terraform catalog, renderer, runner, *.tf.j2 templates
│   │   ├── models/           # SQLAlchemy models
│   │   ├── providers/        # adapter interface, mock, AWS, Azure, GCP, factory
│   │   ├── repositories/     # persistence queries
│   │   ├── schemas/          # Pydantic v2 schemas
│   │   ├── services/         # business logic
│   │   ├── worker/           # Celery app + tasks
│   │   ├── main.py           # app factory
│   │   └── seed.py           # demo data
│   ├── alembic/              # migrations (source of truth for the schema)
│   ├── tests/                # pytest suite (PostgreSQL)
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── api/              # typed API client + React Query hooks
│   │   ├── components/       # design-system components + layout
│   │   ├── pages/            # route pages
│   │   └── test/             # Vitest + RTL tests
│   └── Dockerfile
├── docs/                     # API, deployment, cloud providers, screenshots
├── .github/                  # CI, CodeQL, Dependabot, templates
├── docker-compose.yml
├── database_schema.sql       # generated reference DDL
├── postman_collection.json
└── Makefile
```

## Roadmap

- Real usage metrics from CloudWatch, Azure Monitor and Cloud Monitoring
- Azure Cost Management and GCP BigQuery billing-export cost adapters
- Remote Terraform state backends (S3/Azure Blob/GCS) and real destroy workflow
- Refresh tokens, SSO (OIDC) and MFA
- Login rate limiting / account lockout
- More resource types (RDS, AKS, GKE, load balancers) and tag-based cost allocation
- Notification channels (e-mail, Slack, webhooks) for alerts

## License

[MIT](LICENSE) © 2026 vks-eng

## Author

Built by **vks-eng** · GitHub: https://github.com/vks-eng
