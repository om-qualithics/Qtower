import pytest
from sqlalchemy import select

from apps.api.core.db import SessionLocal, org_scoped_session
from apps.api.modules.identity.models import Org
from apps.api.modules.notifications import service
from apps.api.modules.notifications.models import NotificationLog
from apps.api.modules.notifications.service import NotificationConfigError


def _make_org(name: str) -> Org:
    db = SessionLocal()
    try:
        org = Org(name=name)
        db.add(org)
        db.commit()
        db.refresh(org)
        return org
    finally:
        db.close()


def _delete_org(org: Org) -> None:
    with org_scoped_session(str(org.id)) as db:
        db.query(NotificationLog).filter(NotificationLog.org_id == org.id).delete(synchronize_session=False)
    db = SessionLocal()
    try:
        db.query(Org).filter(Org.id == org.id).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def test_send_email_mock_mode_logs_sent_with_no_network_call() -> None:
    org = _make_org("Notifications Mock Org")
    try:
        service.send_email(["someone@example.com"], "Test subject", "Test body", org_id=str(org.id))

        with org_scoped_session(str(org.id)) as db:
            rows = db.scalars(select(NotificationLog).where(NotificationLog.org_id == org.id)).all()
            assert len(rows) == 1
            assert rows[0].status == "sent"
            assert rows[0].to_emails == ["someone@example.com"]
    finally:
        _delete_org(org)


def test_send_email_live_mode_without_smtp_host_raises_clear_error(monkeypatch) -> None:
    monkeypatch.setattr("apps.api.modules.notifications.service.settings.notifications_provider", "live")
    monkeypatch.setattr("apps.api.modules.notifications.service.settings.smtp_host", "")
    org = _make_org("Notifications Config Error Org")
    try:
        with pytest.raises(NotificationConfigError):
            service.send_email(["someone@example.com"], "Test subject", "Test body", org_id=str(org.id))
    finally:
        _delete_org(org)
