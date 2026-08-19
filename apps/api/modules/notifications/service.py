import smtplib
from email.mime.text import MIMEText

from apps.api.core.db import org_scoped_session
from apps.api.core.settings import settings
from apps.api.modules.notifications.models import NotificationLog


class NotificationConfigError(RuntimeError):
    pass


def _log(org_id: str | None, to_emails: list[str], subject: str, body: str, status: str, error_message: str | None) -> None:
    entry = NotificationLog(
        org_id=org_id, to_emails=to_emails, subject=subject, body=body, status=status, error_message=error_message
    )
    if org_id is not None:
        with org_scoped_session(org_id) as db:
            db.add(entry)
    else:
        # No current caller sends without an org, but the log schema
        # allows for it (see models.py) - fall back to an unscoped write
        # rather than pretending an org_id exists.
        from apps.api.core.db import SessionLocal

        db = SessionLocal()
        try:
            db.add(entry)
            db.commit()
        finally:
            db.close()


def _send_mock(to_emails: list[str], subject: str, body: str) -> None:
    # No external call - mirrors ai_gateway's MockProvider, so the whole
    # notification-triggering feature (escalation routing) is testable and
    # demoable with zero mail infra configured.
    pass


def _send_live(to_emails: list[str], subject: str, body: str) -> None:
    if not settings.smtp_host or not settings.smtp_from_address:
        raise NotificationConfigError(
            "NOTIFICATIONS_PROVIDER=live but SMTP_HOST/SMTP_FROM_ADDRESS are not set - refusing to "
            "silently fall back to mock delivery"
        )
    message = MIMEText(body)
    message["Subject"] = subject
    message["From"] = settings.smtp_from_address
    message["To"] = ", ".join(to_emails)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:
        smtp.starttls()
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.sendmail(settings.smtp_from_address, to_emails, message.as_string())


def send_email(to_emails: list[str], subject: str, body: str, org_id: str | None = None) -> None:
    """The one function notification-triggering feature code should call
    (mirrors ai_gateway.complete()) - resolves mock/live from
    settings.notifications_provider, and always leaves a NotificationLog
    row behind regardless of outcome.

    This is a plain blocking function (SMTP is a real network call in live
    mode) - callers must invoke it from a Celery task
    (notifications/tasks.py), never synchronously from a route handler,
    same rule ai_gateway.complete() follows.
    """
    if settings.notifications_provider not in ("mock", "live"):
        raise NotificationConfigError(f"Unknown NOTIFICATIONS_PROVIDER: {settings.notifications_provider!r}")

    try:
        if settings.notifications_provider == "mock":
            _send_mock(to_emails, subject, body)
        else:
            _send_live(to_emails, subject, body)
    except NotificationConfigError:
        raise
    except Exception as exc:
        _log(org_id, to_emails, subject, body, status="failed", error_message=str(exc)[:500])
        return

    _log(org_id, to_emails, subject, body, status="sent", error_message=None)
