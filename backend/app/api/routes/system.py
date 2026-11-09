from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.deps import DbSession
from app.core.config import get_settings

router = APIRouter(tags=["System"])


@router.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health")
def health(db: DbSession) -> JSONResponse:
    settings = get_settings()
    try:
        db.execute(text("SELECT 1"))
        database = "ok"
    except Exception:
        database = "unavailable"
    body = {
        "status": "ok" if database == "ok" else "degraded",
        "database": database,
        "cloud_provider_mode": settings.cloud_provider_mode,
        "task_mode": "eager" if settings.celery_task_always_eager else "celery",
        "environment": settings.environment,
    }
    return JSONResponse(status_code=200 if database == "ok" else 503, content=body)
