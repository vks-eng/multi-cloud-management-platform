"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    accounts,
    audit,
    auth,
    costs,
    infrastructure,
    monitoring,
    resources,
    system,
    users,
)
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging

APP_TITLE = "CloudOrbit: Multi-Cloud Management Platform (AWS · Azure · GCP)"
APP_DESCRIPTION = """
Manage and monitor AWS, Azure and GCP resources from one API.

* **Auth & RBAC** - JWT bearer tokens, roles `admin` / `operator` / `viewer`.
* **Cloud accounts** - Fernet-encrypted credentials, connection validation.
* **Inventory** - EC2, S3, Azure VMs & storage accounts, GCE instances, GCS buckets.
* **Infrastructure** - Terraform templates, plan, explicit confirmation, audited apply.
* **Monitoring, costs, budgets, audit logs.**

Use `POST /api/v1/auth/token` (the *Authorize* button) to authenticate.
"""


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    app = FastAPI(
        title=APP_TITLE,
        description=APP_DESCRIPTION,
        version="1.0.0",
        openapi_url=f"{settings.api_prefix}/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
        license_info={"name": "MIT"},
        contact={"name": "vks-eng", "url": "https://github.com/vks-eng"},
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.middleware("http")
    async def security_headers(request, call_next):  # type: ignore[no-untyped-def]
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        return response

    register_exception_handlers(app)
    for module in (
        auth,
        users,
        accounts,
        resources,
        infrastructure,
        monitoring,
        costs,
        audit,
        system,
    ):
        app.include_router(module.router, prefix=settings.api_prefix)
    return app


app = create_app()
