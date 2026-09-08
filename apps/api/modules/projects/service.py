import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from apps.api.core.db import org_scoped_session
from apps.api.modules.identity.models import Org, User
from apps.api.modules.policy import service as policy_service
from apps.api.modules.projects.constants import LIFECYCLE_STAGES
from apps.api.modules.projects.models import Project, ProjectRequest, ProjectToolLink, ProjectVendorLink
from apps.api.modules.tools import service as tools_service
from apps.api.modules.tools.constants import TIER_KEYS
from apps.api.modules.vendors import service as vendors_service

NO_ACTIVE_POLICY_EXPLANATION = "No active AI Policy yet - precheck skipped."


class ProjectValidationError(Exception):
    pass


class ProjectApprovalError(Exception):
    pass


def _validate_links(links: list[dict], *, valid_ids: set[str], kind: str) -> None:
    """Exactly one of {tool_id|vendor_id}/other_name must be set per link,
    and a reference to a real catalog entry must actually exist in this
    org's catalog - checked here so a stale/foreign id can't be linked
    silently. `kind` is "tool_id" or "vendor_id"."""
    for link in links:
        ref_id = link.get(kind)
        other_name = link.get("other_name")
        if bool(ref_id) == bool(other_name and other_name.strip()):
            raise ProjectValidationError(
                f"Each link must set exactly one of {kind!r} or 'other_name', not both or neither"
            )
        if ref_id is not None and ref_id not in valid_ids:
            raise ProjectValidationError(f"Unknown {kind}: {ref_id!r}")


def _create_links(db, *, org_id, owner_field: str, owner_id, links: list[dict], model, ref_field: str) -> None:
    for link in links:
        db.add(
            model(
                org_id=org_id,
                **{owner_field: owner_id},
                **{
                    ref_field: uuid.UUID(link[ref_field]) if link.get(ref_field) else None,
                },
                other_name=(link.get("other_name") or "").strip() or None,
            )
        )


def create_project_request(
    org: Org,
    user: User,
    name: str,
    description: str,
    business_justification: str,
    data_flow_description: str,
    human_in_loop: bool,
    tool_links: list[dict] | None = None,
    vendor_links: list[dict] | None = None,
    data_tiers: list[str] | None = None,
) -> ProjectRequest:
    if not name.strip():
        raise ProjectValidationError("Name is required")
    if not description.strip():
        raise ProjectValidationError("Description is required")
    if not business_justification.strip():
        raise ProjectValidationError("Business justification is required")
    if not data_flow_description.strip():
        raise ProjectValidationError("Data flow description is required")

    data_tiers = data_tiers or []
    invalid_tiers = [t for t in data_tiers if t not in TIER_KEYS]
    if invalid_tiers:
        raise ProjectValidationError(f"Unknown data tier(s): {invalid_tiers}")

    tool_links = tool_links or []
    vendor_links = vendor_links or []

    valid_tool_ids = {str(t.id) for t in tools_service.list_approved_tools(org)}
    valid_vendor_ids = {str(v.id) for v in vendors_service.list_vendors(org)}
    _validate_links(tool_links, valid_ids=valid_tool_ids, kind="tool_id")
    _validate_links(vendor_links, valid_ids=valid_vendor_ids, kind="vendor_id")

    # Linking is not a hard gate (build plan §"AI Project"), so this never
    # rejects for having zero links either.
    policy_is_live = policy_service.has_active_policy(org)

    with org_scoped_session(str(org.id)) as db:
        request = ProjectRequest(
            org_id=org.id,
            requested_by=user.id,
            name=name.strip(),
            description=description.strip(),
            business_justification=business_justification.strip(),
            data_flow_description=data_flow_description.strip(),
            data_tiers=data_tiers,
            human_in_loop=human_in_loop,
        )
        if not policy_is_live:
            # Mirrors tools/service.py::create_request() exactly - skip the
            # AI precheck entirely rather than enqueue a task with nothing
            # to compare the request to.
            request.project_assessment_status = "skipped"
            request.project_assessment_explanation = NO_ACTIVE_POLICY_EXPLANATION
        db.add(request)
        db.flush()

        _create_links(
            db,
            org_id=org.id,
            owner_field="request_id",
            owner_id=request.id,
            links=tool_links,
            model=ProjectToolLink,
            ref_field="tool_id",
        )
        _create_links(
            db,
            org_id=org.id,
            owner_field="request_id",
            owner_id=request.id,
            links=vendor_links,
            model=ProjectVendorLink,
            ref_field="vendor_id",
        )

        db.flush()
        db.refresh(request)
        db.expunge(request)
        return request


def get_request_tool_links(org: Org, request_id: str) -> list[ProjectToolLink]:
    with org_scoped_session(str(org.id)) as db:
        links = db.scalars(
            select(ProjectToolLink).where(
                ProjectToolLink.org_id == org.id, ProjectToolLink.request_id == uuid.UUID(request_id)
            )
        ).all()
        for link in links:
            db.expunge(link)
        return list(links)


def get_request_vendor_links(org: Org, request_id: str) -> list[ProjectVendorLink]:
    with org_scoped_session(str(org.id)) as db:
        links = db.scalars(
            select(ProjectVendorLink).where(
                ProjectVendorLink.org_id == org.id, ProjectVendorLink.request_id == uuid.UUID(request_id)
            )
        ).all()
        for link in links:
            db.expunge(link)
        return list(links)


def get_project_tool_links(org: Org, project_id: str) -> list[ProjectToolLink]:
    with org_scoped_session(str(org.id)) as db:
        links = db.scalars(
            select(ProjectToolLink).where(
                ProjectToolLink.org_id == org.id, ProjectToolLink.project_id == uuid.UUID(project_id)
            )
        ).all()
        for link in links:
            db.expunge(link)
        return list(links)


def get_project_vendor_links(org: Org, project_id: str) -> list[ProjectVendorLink]:
    with org_scoped_session(str(org.id)) as db:
        links = db.scalars(
            select(ProjectVendorLink).where(
                ProjectVendorLink.org_id == org.id, ProjectVendorLink.project_id == uuid.UUID(project_id)
            )
        ).all()
        for link in links:
            db.expunge(link)
        return list(links)


def list_project_requests(org: Org, *, mine: User | None = None, pending_only: bool = False) -> list[ProjectRequest]:
    with org_scoped_session(str(org.id)) as db:
        query = select(ProjectRequest).where(ProjectRequest.org_id == org.id)
        if mine is not None:
            query = query.where(ProjectRequest.requested_by == mine.id)
        if pending_only:
            query = query.where(ProjectRequest.status == "pending")
        requests = db.scalars(query.order_by(ProjectRequest.created_at.desc())).all()
        for request in requests:
            db.expunge(request)
        return list(requests)


def get_project_request(org: Org, request_id: str) -> ProjectRequest | None:
    with org_scoped_session(str(org.id)) as db:
        request = db.get(ProjectRequest, uuid.UUID(request_id))
        if request is None or str(request.org_id) != str(org.id):
            return None
        db.expunge(request)
        return request


def list_projects(org: Org) -> list[Project]:
    with org_scoped_session(str(org.id)) as db:
        projects = db.scalars(select(Project).where(Project.org_id == org.id).order_by(Project.name)).all()
        for project in projects:
            db.expunge(project)
        return list(projects)


def get_project(org: Org, project_id: str) -> Project | None:
    with org_scoped_session(str(org.id)) as db:
        project = db.get(Project, uuid.UUID(project_id))
        if project is None or str(project.org_id) != str(org.id):
            return None
        db.expunge(project)
        return project


def update_project(
    org: Org, project_id: str, *, name: str | None, description: str | None, lifecycle_stage: str | None
) -> Project | None:
    if lifecycle_stage is not None and lifecycle_stage not in LIFECYCLE_STAGES:
        raise ProjectValidationError(f"Unknown lifecycle stage: {lifecycle_stage!r}")

    with org_scoped_session(str(org.id)) as db:
        project = db.get(Project, uuid.UUID(project_id))
        if project is None or str(project.org_id) != str(org.id):
            return None
        if name is not None:
            project.name = name.strip()
        if description is not None:
            project.description = description.strip()
        if lifecycle_stage is not None:
            project.lifecycle_stage = lifecycle_stage
        db.flush()
        db.refresh(project)
        db.expunge(project)
        return project


def delete_project(org: Org, project_id: str) -> bool:
    with org_scoped_session(str(org.id)) as db:
        project = db.get(Project, uuid.UUID(project_id))
        if project is None or str(project.org_id) != str(org.id):
            return False
        # Both sides of the circular FK (see the migration's note) must be
        # cleared before the row can be deleted - identical pattern to
        # tools/service.py::delete_approved_tool()/vendors/service.py::delete_vendor().
        project.created_from_request_id = None
        db.flush()
        referencing_requests = db.scalars(
            select(ProjectRequest).where(ProjectRequest.resulting_project_id == project.id)
        ).all()
        for request in referencing_requests:
            request.resulting_project_id = None
        db.flush()
        for link in db.scalars(select(ProjectToolLink).where(ProjectToolLink.project_id == project.id)).all():
            db.delete(link)
        for link in db.scalars(select(ProjectVendorLink).where(ProjectVendorLink.project_id == project.id)).all():
            db.delete(link)
        db.flush()
        db.delete(project)
        return True


def approve_project_request(org: Org, request_id: str, approver: User) -> ProjectRequest:
    request = get_project_request(org, request_id)
    if request is None:
        raise ProjectApprovalError("Request not found")
    if request.status != "pending":
        raise ProjectApprovalError(f"Only a pending request can be approved (current status: {request.status})")
    if request.requested_by == approver.id:
        raise ProjectApprovalError("You cannot approve your own request")

    tool_links = get_request_tool_links(org, request_id)
    vendor_links = get_request_vendor_links(org, request_id)

    with org_scoped_session(str(org.id)) as db:
        target = db.get(ProjectRequest, uuid.UUID(request_id))
        assert target is not None

        project = Project(
            org_id=org.id,
            name=target.name,
            description=target.description,
            owner_user_id=target.requested_by,
            created_from_request_id=target.id,
            created_by=approver.id,
        )
        db.add(project)
        db.flush()

        # Copied (not moved) from the request's own link rows, which stay
        # in place as a record of what was originally submitted - same
        # copy-on-approve pattern as vendors/service.py::approve_vendor_request().
        for link in tool_links:
            db.add(
                ProjectToolLink(
                    org_id=org.id, project_id=project.id, tool_id=link.tool_id, other_name=link.other_name
                )
            )
        for link in vendor_links:
            db.add(
                ProjectVendorLink(
                    org_id=org.id, project_id=project.id, vendor_id=link.vendor_id, other_name=link.other_name
                )
            )

        target.status = "approved"
        target.decided_by = approver.id
        target.decided_at = datetime.now(timezone.utc)
        target.resulting_project_id = project.id

        db.flush()
        db.refresh(target)
        db.expunge(target)
        return target


def reject_project_request(org: Org, request_id: str, approver: User) -> ProjectRequest:
    request = get_project_request(org, request_id)
    if request is None:
        raise ProjectApprovalError("Request not found")
    if request.status != "pending":
        raise ProjectApprovalError(f"Only a pending request can be rejected (current status: {request.status})")
    if request.requested_by == approver.id:
        raise ProjectApprovalError("You cannot reject your own request")

    with org_scoped_session(str(org.id)) as db:
        target = db.get(ProjectRequest, uuid.UUID(request_id))
        assert target is not None
        target.status = "rejected"
        target.decided_by = approver.id
        target.decided_at = datetime.now(timezone.utc)
        db.flush()
        db.refresh(target)
        db.expunge(target)
        return target
