# CloudOrbit: project summary (case study)

**CloudOrbit: Multi-Cloud Management Platform (AWS · Azure · GCP)**, a full-stack web application for managing and monitoring cloud resources across three providers from one dashboard.
Repository: https://github.com/vks-eng/multi-cloud-management-platform

## Problem

Organisations running on AWS, Azure and GCP juggle three consoles, three IAM models and three billing views. Nobody has a single answer to "what do we run, what does it cost, who changed it". Ad-hoc provisioning scripts get applied without review, and cloud credentials get scattered across laptops and CI variables.

## Solution

A single FastAPI + React platform that:

- registers AWS accounts, Azure subscriptions and GCP projects with **encrypted credentials**,
- **syncs a normalised inventory** (compute + storage) with full change history,
- **provisions through Terraform** templates, where nothing is applied until a human reviews the plan and confirms it with a one-time token and the typed resource name,
- shows **monitoring** (status, distribution, usage, alerts) and **cost analytics** (trends, provider comparison, budgets with threshold alerts),
- records every security-relevant action in an **audit log**, under **role-based access control**.

It runs completely offline with deterministic **mock cloud adapters**. Switching to real clouds is a configuration change plus optional SDK extras.

## Key features

- JWT authentication, admin/operator/viewer roles over 12 permissions, profile and user administration
- Fernet (MultiFernet) credential encryption at rest with key rotation; credentials never returned or logged
- Provider-adapter layer: AWS (boto3), Azure SDK and GCP clients behind one interface, plus mock implementations
- Inventory reconciliation: create, update, status-change and delete events, metrics samples, high-CPU and public-storage alerts
- 6 hardened Terraform templates, injection-safe HCL rendering, real `terraform plan` when available, otherwise a labelled mock plan
- Cost summary, forecast, 6-month trends, cost by service, budgets and idempotent cost alerts
- Celery background sync with a beat schedule, plus an eager mode for Redis-less development
- Enterprise dashboard UI: sidebar navigation, protected routes, React Query, Recharts

## Stack

Python 3.12+ · FastAPI · Pydantic v2 · SQLAlchemy 2.0 · Alembic · PostgreSQL 16 · Redis · Celery · Jinja2/HCL · Terraform · React 18 · TypeScript · Vite · Tailwind CSS · TanStack Query · Recharts · Pytest · Vitest · React Testing Library · Docker · GitHub Actions

## Engineering practices

- Layered architecture (API, services, repositories, adapters) with dependency injection and a single error envelope
- Security by default: secrets encrypted, redacted logs, timing-safe login, production config guards, security headers, least-privilege IAM docs
- Real-database testing: the pytest suite runs against PostgreSQL and applies the Alembic migration at startup
- CI: Ruff lint + format check, pytest with a Postgres service, frontend lint, typecheck, Vitest and build; Dependabot; least-privilege workflow permissions (`contents: read`)
- Reproducibility: pinned requirements exported from `pyproject.toml`, `package-lock.json`, Docker Compose, Makefile

## Facts (measured)

| Metric | Value |
|---|---|
| REST operations | 52 (across 9 API modules) |
| Database tables | 13 (+ `alembic_version`) |
| Terraform templates | 6 |
| Frontend pages | 10 (login, register, overview, accounts, inventory, infrastructure, costs, monitoring, activity, settings) |
| Backend tests | 88 passed (50 API integration, 22 RBAC, 16 unit) against real PostgreSQL |
| Backend coverage | 91% lines (`pytest --cov=app`) |
| Frontend tests | 46 passed (Vitest + React Testing Library), 77% statements |

## What this demonstrates for a client

- I can design and ship a **secure, multi-tenant-ready backend** that integrates with third-party cloud APIs without leaking credentials.
- I build **safe automation**: infrastructure changes are planned, reviewed, explicitly confirmed and audited.
- I deliver **complete products**, not mockups: database migrations, background jobs, tests, CI, Docker and documentation.
- I write **maintainable code** that a team can extend. A new cloud provider or resource type is one adapter or template.

## Upwork-ready blurb

> I built CloudOrbit, a full-stack multi-cloud management platform (FastAPI, PostgreSQL, Celery, React/TypeScript) that inventories AWS, Azure and GCP resources, tracks costs against budgets, and provisions infrastructure through Terraform with a review-and-confirm workflow and full audit trail. Credentials are encrypted at rest, access is role-based, and the project ships with tests against real PostgreSQL, Docker Compose and GitHub Actions CI. I can bring the same engineering discipline to your cloud, DevOps or internal-platform project.

## GitHub repo settings

**Suggested description** (under 350 characters):

> CloudOrbit: manage AWS, Azure & GCP from one dashboard. FastAPI + PostgreSQL + Celery backend, React/TypeScript UI, encrypted cloud credentials, RBAC, resource inventory sync, cost analytics & budgets, Terraform plan → confirm → apply with audit trail. Runs offline with mock cloud adapters.

**Suggested topics:** `multi-cloud`, `cloud-management`, `fastapi`, `react`, `typescript`, `postgresql`, `terraform`, `aws`, `azure`, `gcp`, `celery`, `finops`
