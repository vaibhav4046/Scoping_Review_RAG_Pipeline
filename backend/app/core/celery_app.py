"""Celery application configuration."""

from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "scoping_review",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    # Task routing
    task_routes={
        "app.tasks.search_tasks.*": {"queue": "search"},
        "app.tasks.screening_tasks.*": {"queue": "screening"},
        "app.tasks.extraction_tasks.*": {"queue": "extraction"},
        "app.tasks.validation_tasks.*": {"queue": "validation"},
    },

    # Reliability
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,

    # Limits
    task_time_limit=600,  # 10 min hard limit
    task_soft_time_limit=540,  # 9 min soft limit

    # Results
    result_expires=86400,  # 24 hours

    # Retry
    task_default_retry_delay=30,
    task_max_retries=3,

    # Beat schedule
    beat_schedule={},
)

# Auto-discover tasks
celery_app.autodiscover_tasks(["app.tasks"])
