from celery import Celery

from core.config import settings

celery_app = Celery(
    "deallens",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    result_expires=3600,  # keep results in Redis for 1 hour so frontend can poll
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "fetch-news-every-6-hours": {
            "task": "workers.tasks.fetch_and_classify_news",
            "schedule": 21600.0,  # 6 hours in seconds
        },
    },
)
