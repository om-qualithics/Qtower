from fastapi import APIRouter, Cookie, File, Form, HTTPException, Query, UploadFile

from apps.api.core import storage
from apps.api.modules.authz import service as authz_service
from apps.api.modules.escalations import service as escalations_service
from apps.api.modules.escalations.schemas import EscalationDownloadOut, EscalationOut, EscalationUpdate
from apps.api.modules.escalations.service import EscalationValidationError
from apps.api.modules.identity import service as identity_service
from apps.api.modules.notifications.tasks import send_email_task

router = APIRouter(prefix="/escalations", tags=["escalations"])


def _require_user(session_token: str | None):
    user = identity_service.get_current_user(session_token)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def _to_escalation_out(org, escalation) -> EscalationOut:
    reporter = identity_service.get_user_by_id(org, escalation.reporter_id)
    return EscalationOut(
        id=str(escalation.id),
        category=escalation.category,
        description=escalation.description,
        related_tool_request_id=str(escalation.related_tool_request_id) if escalation.related_tool_request_id else None,
        related_policy_id=str(escalation.related_policy_id) if escalation.related_policy_id else None,
        status=escalation.status,
        reporter_id=str(escalation.reporter_id),
        reporter_email=reporter.email if reporter else None,
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

    attachment_bytes = await file.read() if file is not None else None
    attachment_filename = file.filename if file is not None else None

    try:
        escalation = escalations_service.create_escalation(
            org,
            user,
            category,
            description,
            attachment_filename=attachment_filename,
            attachment_bytes=attachment_bytes,
        )
    except EscalationValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    recipients = escalations_service.resolve_notification_recipients(org)
    if recipients:
        subject = f"[Q Tower] New escalation: {category.replace('_', ' ')}"
        message = f"{user.email} raised a new escalation.\n\nCategory: {category}\n\n{escalation.description}"
        send_email_task.delay(recipients, subject, message, str(org.id))

    return _to_escalation_out(org, escalation)


@router.get("/{escalation_id}/attachment", response_model=EscalationDownloadOut)
def get_escalation_attachment(escalation_id: str, misty_session: str | None = Cookie(default=None)):
    user = _require_user(misty_session)
    org = identity_service.get_org()
    escalation = escalations_service.get_escalation(org, escalation_id)
    if escalation is None:
        raise HTTPException(status_code=404, detail="Escalation not found")
    is_reporter = str(escalation.reporter_id) == str(user.id)
    if not is_reporter and not authz_service.can(user, "escalations.manage"):
        raise HTTPException(status_code=403, detail="Forbidden")
    if not escalation.attachment_key:
        raise HTTPException(status_code=404, detail="This escalation has no attachment")
    return EscalationDownloadOut(download_url=storage.presigned_url(escalation.attachment_key, expires_seconds=300))


@router.get("/", response_model=list[EscalationOut])
def list_escalations(mine: bool = Query(default=False), misty_session: str | None = Cookie(default=None)):
    user = _require_user(misty_session)
    org = identity_service.get_org()
    if mine:
        escalations = escalations_service.list_escalations(org, mine=user)
    else:
        if not authz_service.can(user, "escalations.manage"):
            raise HTTPException(status_code=403, detail="Forbidden")
        escalations = escalations_service.list_escalations(org)
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
