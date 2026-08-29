import mimetypes
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from apps.api.core import storage
from apps.api.core.db import org_scoped_session
from apps.api.modules.branding import service as branding_service
from apps.api.modules.escalations.constants import ALLOWED_ATTACHMENT_EXTENSIONS, CATEGORIES, escalation_attachment_key
from apps.api.modules.escalations.models import Escalation
from apps.api.modules.identity import service as identity_service
from apps.api.modules.identity.models import Org
from apps.api.modules.policy.constants import MAX_UPLOAD_SIZE_BYTES

STATUSES = ("open", "in_review", "resolved")


class EscalationValidationError(Exception):
    pass


def resolve_notification_recipients(org: Org) -> list[str]:
    """Who gets emailed about a new escalation - the org's govern/assure
    users, or a single override address if deployment_config has one set.
    Public (not the Celery enqueue itself) so the router can call it after
    create_escalation() - keeps this module Celery-free and its tests
    deterministic, same split tools/service.py + tools/router.py use for
    assess_tool_request.delay()."""
    config = branding_service.get_config(org)
    if config and config.escalation_notify_override_email:
        return [config.escalation_notify_override_email]
    return identity_service.list_user_emails_by_business_role(org, {"govern", "assure"})


def create_escalation(
    org: Org,
    category: str,
    description: str,
    related_tool_request_id: str | None = None,
    related_policy_id: str | None = None,
    attachment_filename: str | None = None,
    attachment_bytes: bytes | None = None,
) -> Escalation:
    """No `user`/reporter parameter, deliberately - anonymity is the point
    of this feature (see escalations/models.py's docstring). The router
    still requires the caller to be authenticated (escalations.create),
    but that identity is never passed in here, so it's never persisted,
    logged, or emailed anywhere downstream."""
    if category not in CATEGORIES:
        raise EscalationValidationError(f"Unknown category: {category!r}")
    if not description.strip():
        raise EscalationValidationError("Description is required")
    if attachment_bytes is not None:
        if not attachment_filename or not attachment_filename.lower().endswith(ALLOWED_ATTACHMENT_EXTENSIONS):
            raise EscalationValidationError(
                f"Unsupported attachment type - allowed: {', '.join(ALLOWED_ATTACHMENT_EXTENSIONS)}"
            )
        if len(attachment_bytes) > MAX_UPLOAD_SIZE_BYTES:
            raise EscalationValidationError("Attachment is too large (20MB limit)")

    with org_scoped_session(str(org.id)) as db:
        escalation = Escalation(
            org_id=org.id,
            category=category,
            description=description.strip(),
            related_tool_request_id=uuid.UUID(related_tool_request_id) if related_tool_request_id else None,
            related_policy_id=uuid.UUID(related_policy_id) if related_policy_id else None,
        )
        db.add(escalation)
        db.flush()
        escalation_id = escalation.id

    if attachment_bytes is None:
        return get_escalation(org, str(escalation_id))  # type: ignore[return-value]

    assert attachment_filename is not None  # validated above whenever attachment_bytes is set
    key = escalation_attachment_key(str(org.id), str(escalation_id), attachment_filename)
    content_type = mimetypes.guess_type(attachment_filename)[0] or "application/octet-stream"
    storage.upload_bytes(key, attachment_bytes, content_type=content_type)

    with org_scoped_session(str(org.id)) as db:
        target = db.get(Escalation, escalation_id)
        assert target is not None
        target.attachment_key = key
        target.attachment_filename = attachment_filename
        db.flush()
        db.refresh(target)
        db.expunge(target)
        return target


def list_escalations(org: Org, *, resolved: bool | None = None) -> list[Escalation]:
    """No per-reporter `mine` filter - there is no reporter to filter by.
    `resolved` splits the two visible-to-everyone sections the frontend
    shows: Current Escalations (open/in_review) and Resolved Escalations."""
    with org_scoped_session(str(org.id)) as db:
        query = select(Escalation).where(Escalation.org_id == org.id)
        if resolved is True:
            query = query.where(Escalation.status == "resolved")
        elif resolved is False:
            query = query.where(Escalation.status != "resolved")
        escalations = db.scalars(query.order_by(Escalation.created_at.desc())).all()
        for escalation in escalations:
            db.expunge(escalation)
        return list(escalations)


def get_escalation(org: Org, escalation_id: str) -> Escalation | None:
    with org_scoped_session(str(org.id)) as db:
        escalation = db.get(Escalation, uuid.UUID(escalation_id))
        if escalation is None or str(escalation.org_id) != str(org.id):
            return None
        db.expunge(escalation)
        return escalation


def update_escalation(
    org: Org,
    escalation_id: str,
    *,
    status: str | None = None,
    assigned_to: str | None = None,
    resolution_note: str | None = None,
) -> Escalation | None:
    if status is not None and status not in STATUSES:
        raise EscalationValidationError(f"Unknown status: {status!r}")
    if status == "resolved" and not (resolution_note and resolution_note.strip()):
        raise EscalationValidationError(
            "A resolution note is required when marking an escalation resolved - explain how it was addressed"
        )

    with org_scoped_session(str(org.id)) as db:
        escalation = db.get(Escalation, uuid.UUID(escalation_id))
        if escalation is None or str(escalation.org_id) != str(org.id):
            return None

        if status is not None:
            escalation.status = status
        if assigned_to is not None:
            escalation.assigned_to = uuid.UUID(assigned_to)
        if resolution_note is not None:
            escalation.resolution_note = resolution_note
        escalation.updated_at = datetime.now(timezone.utc)

        db.flush()
        db.refresh(escalation)
        db.expunge(escalation)
        return escalation
