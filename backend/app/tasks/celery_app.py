"""Celery application configuration with reliability settings from §10."""

from celery import Celery
from app.config import settings

celery_app = Celery(
    "website_intelligence",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks.crawl_tasks"],
)

# Apply settings from §10
celery_app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    timezone="UTC",
    enable_utc=True,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    beat_schedule={
        "schedule-due-pages-every-minute": {
            "task": "app.tasks.crawl_tasks.schedule_due_pages_task",
            "schedule": 60.0,
        },
        "recover-stale-runs-every-5-minutes": {
            "task": "app.tasks.crawl_tasks.recover_stale_runs_task",
            "schedule": 300.0,
        },
    },
)
