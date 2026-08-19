from celery import Celery

from apps.api.core.settings import settings

celery_app = Celery(
    "misty",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["apps.api.modules.tools.tasks", "apps.api.modules.notifications.tasks"],
)
