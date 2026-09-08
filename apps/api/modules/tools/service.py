import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from apps.api.core import storage
from apps.api.core.db import org_scoped_session
from apps.api.core.media import logo_storage_key
from apps.api.modules.identity.models import Org, User
from apps.api.modules.policy import service as policy_service
from apps.api.modules.tools.constants import MIN_USE_CASE_WORDS, TIER_KEYS
from apps.api.modules.tools.models import ApprovedTool, ToolRequest

NO_ACTIVE_POLICY_EXPLANATION = "No active AI Policy yet - precheck skipped."

REQUEST_TYPES = ("tool", "feature", "webextension")


class ToolRequestValidationError(Exception):
    pass


class ToolRequestDuplicateError(Exception):
    def __init__(self, existing_tool: ApprovedTool) -> None:
        self.existing_tool = existing_tool
        super().__init__(f"'{existing_tool.name}' is already an approved tool/feature/webextension")


class ToolApprovalError(Exception):
    pass


def _normalize_name(name: str) -> str:
    return name.strip().lower()


def list_approved_tools(org: Org) -> list[ApprovedTool]:
    with org_scoped_session(str(org.id)) as db:
        tools = db.scalars(
            select(ApprovedTool).where(ApprovedTool.org_id == org.id).order_by(ApprovedTool.name)
        ).all()
        for tool in tools:
            db.expunge(tool)
        return list(tools)


def create_request(
    org: Org,
    user: User,
    request_type: str,
    name: str,
    link: str,
    use_case: str,
    data_tiers: list[str] | None = None,
    requires_enterprise_account: bool = False,
) -> ToolRequest:
    if request_type not in REQUEST_TYPES:
        raise ToolRequestValidationError(f"Unknown request type: {request_type!r}")
    if not name.strip():
        raise ToolRequestValidationError("Name is required")
    if not link.strip():
        raise ToolRequestValidationError("Link is required")
    # Enforced client-side too (a live word counter on the request wizard's
    # "Use case" step) - checked again here since the server is the real
    # boundary, same split every other required-field check in this app
    # follows.
    if len(use_case.split()) < MIN_USE_CASE_WORDS:
        raise ToolRequestValidationError(f"Intended use case must be at least {MIN_USE_CASE_WORDS} words")

    data_tiers = data_tiers or []
    invalid_tiers = [t for t in data_tiers if t not in TIER_KEYS]
    if invalid_tiers:
        raise ToolRequestValidationError(f"Unknown data tier(s): {invalid_tiers}")

    normalized = _normalize_name(name)
    # Checked before opening the insert's own session/transaction below -
    # has_active_policy() runs its own org_scoped_session, and a broken
    # request/response race here is harmless either way (fail-open: worst
    # case a request lands "skipped" moments before a policy goes active,
    # fixable by re-submitting).
    policy_is_live = policy_service.has_active_policy(org)

    with org_scoped_session(str(org.id)) as db:
        existing_tools = db.scalars(select(ApprovedTool).where(ApprovedTool.org_id == org.id)).all()
        for tool in existing_tools:
            if _normalize_name(tool.name) == normalized:
                db.expunge(tool)
                raise ToolRequestDuplicateError(tool)

        request = ToolRequest(
            org_id=org.id,
            request_type=request_type,
            name=name.strip(),
            link=link.strip(),
            intended_use_case=use_case.strip(),
            data_tiers=data_tiers,
            requires_enterprise_account=requires_enterprise_account,
            requested_by=user.id,
        )
        if not policy_is_live:
            # No policy to assess against - skip the AI precheck entirely
            # rather than enqueue a task that would have nothing to
            # compare the request to. The router checks this same status
            # to decide whether to fire the Celery task at all.
            request.ai_assessment_status = "skipped"
            request.ai_assessment_explanation = NO_ACTIVE_POLICY_EXPLANATION
        db.add(request)
        db.flush()
        db.refresh(request)
        db.expunge(request)
        return request


def list_requests(org: Org, *, mine: User | None = None, pending_only: bool = False) -> list[ToolRequest]:
    with org_scoped_session(str(org.id)) as db:
        query = select(ToolRequest).where(ToolRequest.org_id == org.id)
        if mine is not None:
            query = query.where(ToolRequest.requested_by == mine.id)
        if pending_only:
            query = query.where(ToolRequest.status == "pending")
        requests = db.scalars(query.order_by(ToolRequest.created_at.desc())).all()
        for request in requests:
            db.expunge(request)
        return list(requests)


def get_approved_tool(org: Org, tool_id: str) -> ApprovedTool | None:
    with org_scoped_session(str(org.id)) as db:
        tool = db.get(ApprovedTool, uuid.UUID(tool_id))
        if tool is None or str(tool.org_id) != str(org.id):
            return None
        db.expunge(tool)
        return tool


def update_approved_tool(
    org: Org,
    tool_id: str,
    *,
    name: str,
    description: str,
    access_url: str,
    allowed_tiers: list[str],
    logo_url: str | None = None,
) -> ApprovedTool | None:
    """Direct catalog curation outside the request flow (tools.manage) -
    e.g. fixing a typo or adjusting which data tiers a tool is cleared
    for, without going through a new request. logo_url here is the
    paste-a-URL-directly path (Milestone 17) - see upload_tool_logo() for
    the alternative upload-to-MinIO path."""
    invalid_tiers = [t for t in allowed_tiers if t not in TIER_KEYS]
    if invalid_tiers:
        raise ToolApprovalError(f"Unknown data tier(s): {invalid_tiers}")

    with org_scoped_session(str(org.id)) as db:
        tool = db.get(ApprovedTool, uuid.UUID(tool_id))
        if tool is None or str(tool.org_id) != str(org.id):
            return None
        tool.name = name.strip()
        tool.description = description.strip()
        tool.access_url = access_url.strip()
        tool.allowed_tiers = allowed_tiers
        tool.logo_url = logo_url.strip() if logo_url and logo_url.strip() else None
        db.flush()
        db.refresh(tool)
        db.expunge(tool)
        return tool


def upload_tool_logo(org: Org, tool_id: str, content_type: str, data: bytes) -> ApprovedTool | None:
    """The upload-to-MinIO path (Milestone 17) - stores at a fixed,
    per-tool key (overwrites any previous logo) and points logo_url at
    this app's own streaming route rather than a MinIO/S3 URL directly,
    since the bucket isn't public and a presigned URL would eventually
    expire out from under a catalog card that renders it indefinitely."""
    with org_scoped_session(str(org.id)) as db:
        tool = db.get(ApprovedTool, uuid.UUID(tool_id))
        if tool is None or str(tool.org_id) != str(org.id):
            return None
        key = logo_storage_key("tool", str(org.id), tool_id)
        storage.upload_bytes(key, data, content_type)
        tool.logo_url = f"/tools/approved/{tool_id}/logo-file"
        db.flush()
        db.refresh(tool)
        db.expunge(tool)
        return tool


def get_tool_logo_bytes(org: Org, tool_id: str) -> tuple[bytes, str] | None:
    with org_scoped_session(str(org.id)) as db:
        tool = db.get(ApprovedTool, uuid.UUID(tool_id))
        if tool is None or str(tool.org_id) != str(org.id):
            return None
    key = logo_storage_key("tool", str(org.id), tool_id)
    return storage.download_bytes_with_content_type(key)


def delete_approved_tool(org: Org, tool_id: str) -> bool:
    with org_scoped_session(str(org.id)) as db:
        tool = db.get(ApprovedTool, uuid.UUID(tool_id))
        if tool is None or str(tool.org_id) != str(org.id):
            return False
        # Both sides of the circular FK (see the migration's note) must be
        # cleared before the row can be deleted.
        tool.created_from_request_id = None
        db.flush()
        referencing_requests = db.scalars(
            select(ToolRequest).where(ToolRequest.resulting_tool_id == tool.id)
        ).all()
        for request in referencing_requests:
            request.resulting_tool_id = None
        db.flush()
        db.delete(tool)
        return True


def get_request(org: Org, request_id: str) -> ToolRequest | None:
    with org_scoped_session(str(org.id)) as db:
        request = db.get(ToolRequest, uuid.UUID(request_id))
        if request is None or str(request.org_id) != str(org.id):
            return None
        db.expunge(request)
        return request


def approve_request(
    org: Org, request_id: str, approver: User, *, description: str, allowed_tiers: list[str]
) -> ToolRequest:
    request = get_request(org, request_id)
    if request is None:
        raise ToolApprovalError("Request not found")
    if request.status != "pending":
        raise ToolApprovalError(f"Only a pending request can be approved (current status: {request.status})")
    if request.requested_by == approver.id:
        raise ToolApprovalError("You cannot approve your own request")

    invalid_tiers = [t for t in allowed_tiers if t not in TIER_KEYS]
    if invalid_tiers:
        raise ToolApprovalError(f"Unknown data tier(s): {invalid_tiers}")

    with org_scoped_session(str(org.id)) as db:
        target = db.get(ToolRequest, uuid.UUID(request_id))
        assert target is not None

        tool = ApprovedTool(
            org_id=org.id,
            name=target.name,
            description=description.strip(),
            source_type=target.request_type,
            access_url=target.link,
            allowed_tiers=allowed_tiers,
            created_from_request_id=target.id,
            created_by=approver.id,
        )
        db.add(tool)
        db.flush()

        target.status = "approved"
        target.decided_by = approver.id
        target.decided_at = datetime.now(timezone.utc)
        target.resulting_tool_id = tool.id

        db.flush()
        db.refresh(target)
        db.expunge(target)
        return target


def reject_request(org: Org, request_id: str, approver: User, reason: str | None = None) -> ToolRequest:
    request = get_request(org, request_id)
    if request is None:
        raise ToolApprovalError("Request not found")
    if request.status != "pending":
        raise ToolApprovalError(f"Only a pending request can be rejected (current status: {request.status})")
    if request.requested_by == approver.id:
        raise ToolApprovalError("You cannot reject your own request")

    with org_scoped_session(str(org.id)) as db:
        target = db.get(ToolRequest, uuid.UUID(request_id))
        assert target is not None
        target.status = "rejected"
        target.decided_by = approver.id
        target.decided_at = datetime.now(timezone.utc)
        target.decision_note = reason
        db.flush()
        db.refresh(target)
        db.expunge(target)
        return target
