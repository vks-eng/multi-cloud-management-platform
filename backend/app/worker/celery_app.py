"""Celery application.

In Docker Compose a dedicated worker (+ beat) consumes tasks from Redis. For tests and local
development without Redis, CELERY_TASK_ALWAYS_EAGER=true runs tasks in-process.
"""

from __future__ import annotations

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "mcmp",
    broker=settings.broker_url,
    backend=None if settings.celery_task_always_eager else settings.result_backend,
    include=["app.worker.tasks"],
)
celery_app.conf.update(
    task_always_eager=settings.celery_task_always_eager,
    task_eager_propagates=False,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    timezone="UTC",
    beat_schedule={
        "sync-all-accounts": {
            "task": "mcmp.sync_all_accounts",
            "schedule": settings.sync_interval_minutes * 60.0,
        },
        "evaluate-budgets": {
            "task": "mcmp.evaluate_budgets",
            "schedule": 3600.0,
        },
    },
)
