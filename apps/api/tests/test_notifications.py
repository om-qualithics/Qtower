import pytest
from sqlalchemy import select

from apps.api.core.db import SessionLocal, org_scoped_session
from apps.api.modules.branding import service as branding_service
from apps.api.modules.branding.models import DeploymentConfig
from apps.api.modules.identity.models import Org
from apps.api.modules.notifications import service
from apps.api.modules.notifications.models import NotificationLog
from apps.api.modules.notifications.service import NotificationConfigError
from apps.api.modules.notifications.templates import render_template


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
        db.query(DeploymentConfig).filter(DeploymentConfig.org_id == org.id).delete(synchronize_session=False)
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


def test_render_template_falls_back_to_default_when_no_override_set() -> None:
    org = _make_org("Templates Default Org")
    try:
        subject, body = render_template(
            org, "escalation_raised", {"reporter_email": "a@example.com", "category": "other", "description": "d"}
        )
        assert subject == "[Q Tower] New escalation: other"
        assert "a@example.com raised a new escalation." in body
        assert "d" in body
    finally:
        _delete_org(org)


def test_render_template_uses_org_override_when_set() -> None:
    org = _make_org("Templates Override Org")
    try:
        branding_service.update_config(
            org,
            {
                "email_templates": {
                    "escalation_raised": {
                        "subject": "Custom: {{category}}",
                        "body": "From {{reporter_email}}: {{description}}",
                    }
                }
            },
        )
        subject, body = render_template(
            org, "escalation_raised", {"reporter_email": "a@example.com", "category": "other", "description": "d"}
        )
        assert subject == "Custom: other"
        assert body == "From a@example.com: d"
    finally:
        _delete_org(org)


def test_render_template_survives_stray_literal_brace_in_custom_template() -> None:
    org = _make_org("Templates Brace Org")
    try:
        branding_service.update_config(
            org,
            {"email_templates": {"escalation_raised": {"subject": "team{s}: {{category}}", "body": "{{description}}"}}},
        )
        subject, body = render_template(
            org, "escalation_raised", {"reporter_email": "a@example.com", "category": "other", "description": "d"}
        )
        assert subject == "team{s}: other"
        assert body == "d"
    finally:
        _delete_org(org)
