from celery import Celery

from apps.api.core.settings import settings

celery_app = Celery(
    "misty",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "apps.api.modules.tools.tasks",
        "apps.api.modules.notifications.tasks",
        "apps.api.modules.codescan.tasks",
        "apps.api.modules.projects.tasks",
    ],
)

# Scans run on their own queue so a long-running one doesn't block
# tool-assessment/notification tasks - still one worker process listening
# to both queues for now. Celery's own default queue is literally named
# "celery" (not "default") - the worker must be started with
# `-Q celery,codescan` for both task families to be picked up by one
# process. Promoting codescan to its own dedicated worker process later
# needs no code change, same "don't scale before you need to" precedent
# ai_gateway's plan already set.
celery_app.conf.task_routes = {"codescan.*": {"queue": "codescan"}}
