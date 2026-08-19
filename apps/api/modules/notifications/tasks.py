from apps.api.core.celery_app import celery_app
from apps.api.modules.notifications import service as notifications_service


@celery_app.task(name="notifications.send_email")
def send_email_task(to_emails: list[str], subject: str, body: str, org_id: str | None = None) -> None:
    """The actual blocking send (mock or live SMTP) - always invoked via
    .delay(), never synchronously from a route, matching tools/tasks.py's
    assess_tool_request and the Celery-task-only rule from Milestone 4."""
    notifications_service.send_email(to_emails, subject, body, org_id=org_id)
