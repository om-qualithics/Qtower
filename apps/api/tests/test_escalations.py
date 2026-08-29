import pytest

from apps.api.core.db import SessionLocal, org_scoped_session
from apps.api.modules.branding import service as branding_service
from apps.api.modules.branding.models import DeploymentConfig
from apps.api.modules.escalations import service
from apps.api.modules.escalations.models import Escalation
from apps.api.modules.escalations.service import EscalationValidationError
from apps.api.modules.identity.models import Org, User


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


def _make_user(org: Org, email: str, business_role: str = "operator") -> User:
    with org_scoped_session(str(org.id)) as db:
        user = User(org_id=org.id, email=email, business_role=business_role)
        db.add(user)
        db.flush()
        db.refresh(user)
        db.expunge(user)
        return user


def _delete_org(org: Org) -> None:
    with org_scoped_session(str(org.id)) as db:
        db.query(Escalation).filter(Escalation.org_id == org.id).delete(synchronize_session=False)
        db.query(DeploymentConfig).filter(DeploymentConfig.org_id == org.id).delete(synchronize_session=False)
        db.query(User).filter(User.org_id == org.id).delete(synchronize_session=False)
    db = SessionLocal()
    try:
        db.query(Org).filter(Org.id == org.id).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def test_create_escalation_rejects_unknown_category() -> None:
    org = _make_org("Escalation Category Org")
    try:
        with pytest.raises(EscalationValidationError):
            service.create_escalation(org, "not_a_real_category", "something happened")
    finally:
        _delete_org(org)


def test_create_escalation_rejects_empty_description() -> None:
    org = _make_org("Escalation Empty Org")
    try:
        with pytest.raises(EscalationValidationError):
            service.create_escalation(org, "other", "   ")
    finally:
        _delete_org(org)


def test_create_escalation_never_stores_a_reporter() -> None:
    """Anonymity is the whole point - the model has no reporter_id column
    at all (migration 0013), so this is really just proving the row has no
    such attribute rather than asserting a value is null."""
    org = _make_org("Escalation Anonymous Org")
    try:
        escalation = service.create_escalation(org, "other", "no one should know who wrote this")
        assert not hasattr(escalation, "reporter_id")
    finally:
        _delete_org(org)


def test_resolve_notification_recipients_defaults_to_govern_and_assure() -> None:
    org = _make_org("Escalation Recipients Default Org")
    try:
        _make_user(org, "operator@example.com", "operator")
        _make_user(org, "govern1@example.com", "govern")
        _make_user(org, "assure1@example.com", "assure")

        recipients = service.resolve_notification_recipients(org)
        assert set(recipients) == {"govern1@example.com", "assure1@example.com"}
    finally:
        _delete_org(org)


def test_resolve_notification_recipients_uses_override_when_configured() -> None:
    org = _make_org("Escalation Recipients Override Org")
    try:
        _make_user(org, "govern2@example.com", "govern")
        branding_service.update_config(org, {"escalation_notify_override_email": "compliance@example.com"})

        recipients = service.resolve_notification_recipients(org)
        assert recipients == ["compliance@example.com"]
    finally:
        _delete_org(org)


def test_update_escalation_status_transitions_and_rejects_unknown_status() -> None:
    org = _make_org("Escalation Update Org")
    try:
        manager = _make_user(org, "govern3@example.com", "govern")
        escalation = service.create_escalation(org, "other", "needs review")

        updated = service.update_escalation(
            org, str(escalation.id), status="in_review", assigned_to=str(manager.id)
        )
        assert updated is not None
        assert updated.status == "in_review"
        assert updated.assigned_to == manager.id

        with pytest.raises(EscalationValidationError):
            service.update_escalation(org, str(escalation.id), status="not_a_status")
    finally:
        _delete_org(org)


def test_list_escalations_splits_current_and_resolved() -> None:
    org = _make_org("Escalation List Org")
    try:
        a = service.create_escalation(org, "other", "from A")
        service.create_escalation(org, "other", "from B")
        service.update_escalation(org, str(a.id), status="resolved", resolution_note="Handled.")

        current = service.list_escalations(org, resolved=False)
        assert len(current) == 1
        assert current[0].description == "from B"

        resolved = service.list_escalations(org, resolved=True)
        assert len(resolved) == 1
        assert resolved[0].description == "from A"

        everyone = service.list_escalations(org)
        assert len(everyone) == 2
    finally:
        _delete_org(org)


def test_update_escalation_resolved_requires_a_resolution_note() -> None:
    org = _make_org("Escalation Resolve Note Org")
    try:
        escalation = service.create_escalation(org, "other", "needs review")

        with pytest.raises(EscalationValidationError):
            service.update_escalation(org, str(escalation.id), status="resolved")

        with pytest.raises(EscalationValidationError):
            service.update_escalation(org, str(escalation.id), status="resolved", resolution_note="   ")

        resolved = service.update_escalation(
            org, str(escalation.id), status="resolved", resolution_note="Confirmed and retrained the user."
        )
        assert resolved is not None
        assert resolved.status == "resolved"
        assert resolved.resolution_note == "Confirmed and retrained the user."

        # in_review never requires a note.
        service.update_escalation(org, str(escalation.id), status="in_review")
    finally:
        _delete_org(org)


def test_create_escalation_with_attachment_round_trips_through_storage() -> None:
    org = _make_org("Escalation Attachment Org")
    try:
        escalation = service.create_escalation(
            org,
            "other",
            "see attached screenshot",
            attachment_filename="evidence.png",
            attachment_bytes=b"fake png bytes",
        )
        assert escalation.attachment_key is not None
        assert escalation.attachment_filename == "evidence.png"

        from apps.api.core import storage

        assert storage.download_bytes(escalation.attachment_key) == b"fake png bytes"
    finally:
        _delete_org(org)


def test_create_escalation_rejects_unsupported_attachment_type() -> None:
    org = _make_org("Escalation Bad Attachment Org")
    try:
        with pytest.raises(EscalationValidationError):
            service.create_escalation(
                org,
                "other",
                "see attached script",
                attachment_filename="script.exe",
                attachment_bytes=b"not allowed",
            )
    finally:
        _delete_org(org)


def test_create_escalation_rejects_oversized_attachment() -> None:
    org = _make_org("Escalation Oversized Attachment Org")
    try:
        oversized = b"x" * (20 * 1024 * 1024 + 1)
        with pytest.raises(EscalationValidationError):
            service.create_escalation(
                org, "other", "big file", attachment_filename="big.pdf", attachment_bytes=oversized
            )
    finally:
        _delete_org(org)
