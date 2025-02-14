import os

from celery import Celery


def create_celery():
    """Create and configure Celery instance."""
    broker_url = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    backend_url = broker_url  # For simplicity, use same Redis instance for backend

    celery_app = Celery(
        "csv_query_mvp",
        broker=broker_url,
        backend=backend_url,
        include=["app.tasks.ingestion_tasks"],  # Auto-discover tasks
    )

    celery_app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
        task_time_limit=3600,  # 1 hour max runtime
        broker_connection_retry_on_startup=True,  # Fix connection retry warning
    )

    return celery_app


# Create the celery instance
celery = create_celery()
