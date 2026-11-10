# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2026-11-10

### Added

- FastAPI backend (52 REST operations) with layered architecture: API, services, repositories and cloud adapters.
- Auth and users: registration (first user becomes admin), JWT login, OAuth2 password flow, profile and password management, admin user management, and RBAC with `admin`/`operator`/`viewer` roles over 12 permissions.
- Cloud accounts for AWS, Azure and GCP with Fernet/MultiFernet-encrypted credentials, masked credential hints, rotation and connection validation.
- Provider-adapter layer: mock adapters (the default) plus optional boto3, Azure SDK and Google Cloud adapters, loaded lazily.
- Inventory sync with reconciliation (create/update/status/delete history), utilisation samples, and high-CPU and public-storage alerts.
- Terraform integration: 6 hardened templates, injection-safe HCL rendering, real `terraform plan` when available, otherwise a labelled mock plan, and apply gated by a one-time token plus the typed resource name.
- Cost analytics (summary, forecast, trends, by service), budgets with idempotent threshold alerts.
- Audit log, login access history and resource change history.
- Celery worker and beat schedules, with an eager in-process mode for development and tests.
- Alembic migration and a demo seed script (mock providers).
- React + TypeScript dark-first dashboard: overview, cloud accounts, inventory, infrastructure plan → confirm, cost analytics, monitoring, activity logs and settings.
- Tests: 88 backend (PostgreSQL, 91% coverage) and 46 frontend (Vitest + React Testing Library).
- Dockerfiles (multi-stage, non-root), Docker Compose stack, GitHub Actions CI, Dependabot, Makefile, and docs (architecture, API, deployment, cloud providers, testing).
