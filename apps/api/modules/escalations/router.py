from fastapi import APIRouter, Cookie, Depends, File, Form, HTTPException, Query, UploadFile

from apps.api.core import storage
from apps.api.core.uploads import UploadTooLargeError, read_limited
from apps.api.modules.authz import service as authz_service
from apps.api.modules.escalations import service as escalations_service
from apps.api.modules.escalations.schemas import EscalationDownloadOut, EscalationOut, EscalationUpdate
from apps.api.modules.escalations.service import EscalationValidationError
from apps.api.modules.identity import service as identity_service
from apps.api.modules.licensing.service import require_valid_license
from apps.api.modules.notifications.tasks import send_email_task
from apps.api.modules.notifications.templates import render_template
from apps.api.modules.policy.constants import MAX_UPLOAD_SIZE_BYTES

router = APIRouter(prefix="/escalations", tags=["escalations"], dependencies=[Depends(require_valid_license)])


def _require_user(session_token: str | None):
    user = identity_service.get_current_user(session_token)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def _to_escalation_out(org, escalation) -> EscalationOut:
    return EscalationOut(
        id=str(escalation.id),
        category=escalation.category,
        description=escalation.description,
        related_tool_request_id=str(escalation.related_tool_request_id) if escalation.related_tool_request_id else None,
        related_policy_id=str(escalation.related_policy_id) if escalation.related_policy_id else None,
        status=escalation.status,
        assigned_to=str(escalation.assigned_to) if escalation.assigned_to else None,
        resolution_note=escalation.resolution_note,
        has_attachment=escalation.attachment_key is not None,
        attachment_filename=escalation.attachment_filename,
        created_at=escalation.created_at,
        updated_at=escalation.updated_at,
    )


@router.post("/", response_model=EscalationOut)
async def create_escalation(
    category: str = Form(...),
    description: str = Form(...),
    file: UploadFile | None = File(default=None),
    misty_session: str | None = Cookie(default=None),
):
    user = _require_user(misty_session)
    if not authz_service.can(user, "escalations.create"):
        raise HTTPException(status_code=403, detail="Forbidden")
    org = identity_service.get_org()

    try:
        attachment_bytes = await read_limited(file, MAX_UPLOAD_SIZE_BYTES) if file is not None else None
    except UploadTooLargeError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    attachment_filename = file.filename if file is not None else None

    # user is required to be authenticated to raise an alert (escalations.
    # create, checked above), but is deliberately never passed into
    # create_escalation() or into the notification below - anonymity means
    # not persisting or emailing who raised it, not just hiding it in the UI.
    try:
        escalation = escalations_service.create_escalation(
            org,
            category,
            description,
            attachment_filename=attachment_filename,
            attachment_bytes=attachment_bytes,
        )
    except EscalationValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    recipients = escalations_service.resolve_notification_recipients(org)
    if recipients:
        subject, message = render_template(
            org,
            "escalation_raised",
            {"category": category.replace("_", " "), "description": escalation.description},
        )
        send_email_task.delay(recipients, subject, message, str(org.id))

    return _to_escalation_out(org, escalation)


@router.get("/{escalation_id}/attachment", response_model=EscalationDownloadOut)
def get_escalation_attachment(escalation_id: str, misty_session: str | None = Cookie(default=None)):
    user = _require_user(misty_session)
    # No reporter-self-access branch - there is no reporter identity to
    # check against. Only escalations.manage may download evidence.
    if not authz_service.can(user, "escalations.manage"):
        raise HTTPException(status_code=403, detail="Forbidden")
    org = identity_service.get_org()
    escalation = escalations_service.get_escalation(org, escalation_id)
    if escalation is None:
        raise HTTPException(status_code=404, detail="Escalation not found")
    if not escalation.attachment_key:
        raise HTTPException(status_code=404, detail="This escalation has no attachment")
    return EscalationDownloadOut(download_url=storage.presigned_url(escalation.attachment_key, expires_seconds=300))


@router.get("/", response_model=list[EscalationOut])
def list_escalations(resolved: bool | None = Query(default=None), misty_session: str | None = Cookie(default=None)):
    # Visible to every authenticated user, deliberately - Current and
    # Resolved Escalations are both shared, org-wide lists (no "mine"),
    # since hiding a per-user view would be the only way anonymity could
    # ever leak. Only *acting* on one (PATCH, below) stays manage-gated.
    user = _require_user(misty_session)
    if not authz_service.can(user, "escalations.view"):
        raise HTTPException(status_code=403, detail="Forbidden")
    org = identity_service.get_org()
    escalations = escalations_service.list_escalations(org, resolved=resolved)
    return [_to_escalation_out(org, e) for e in escalations]


@router.patch("/{escalation_id}", response_model=EscalationOut)
def update_escalation(escalation_id: str, body: EscalationUpdate, misty_session: str | None = Cookie(default=None)):
    user = _require_user(misty_session)
    if not authz_service.can(user, "escalations.manage"):
        raise HTTPException(status_code=403, detail="Forbidden")
    org = identity_service.get_org()
    try:
        escalation = escalations_service.update_escalation(
            org,
            escalation_id,
            status=body.status,
            assigned_to=body.assigned_to,
            resolution_note=body.resolution_note,
        )
    except EscalationValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if escalation is None:
        raise HTTPException(status_code=404, detail="Escalation not found")
    return _to_escalation_out(org, escalation)
