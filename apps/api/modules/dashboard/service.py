from apps.api.modules.codescan import service as codescan_service
from apps.api.modules.codescan.schemas import ScanRunOut
from apps.api.modules.dashboard.schemas import DashboardSummaryOut
from apps.api.modules.escalations import service as escalations_service
from apps.api.modules.escalations.schemas import EscalationOut
from apps.api.modules.identity import service as identity_service
from apps.api.modules.identity.models import Org, User
from apps.api.modules.policy import service as policy_service
from apps.api.modules.policy.schemas import PolicyListItemOut
from apps.api.modules.tools import service as tools_service
from apps.api.modules.tools.schemas import ToolRequestOut
from apps.api.modules.training import service as training_service
from apps.api.modules.training.schemas import TrainingModuleOut, TrainingModuleSummary, TrainingSummaryOut

ESCALATION_STATUSES = ("open", "in_review", "resolved")
TOOL_REQUEST_STATUSES = ("pending", "approved", "rejected")


def _is_govern(user: User) -> bool:
    return user.business_role == "govern" or user.system_role in ("admin", "super_admin")


def _is_assure(user: User) -> bool:
    return user.business_role == "assure"


def _can_approve_tools(user: User) -> bool:
    return user.business_role in ("govern", "assure") or user.system_role in ("admin", "super_admin")


def _resolve_email(org: Org, user_id) -> str | None:
    if not user_id:
        return None
    user = identity_service.get_user_by_id(org, user_id)
    return user.email if user else None


def _to_policy_out(org: Org, policy) -> PolicyListItemOut:
    return PolicyListItemOut(
        id=str(policy.id),
        status=policy.status,
        source=policy.source,
        has_document=policy.storage_key is not None,
        current_step=policy.current_step,
        version=policy.version,
        policy_owner_name=policy.policy_owner_name,
        created_by=str(policy.created_by) if policy.created_by else None,
        created_by_email=_resolve_email(org, policy.created_by),
        approved_by_email=_resolve_email(org, policy.approved_by),
        generated_at=policy.generated_at,
        approved_at=policy.approved_at,
        created_at=policy.created_at,
        updated_at=policy.updated_at,
    )


def _to_tool_request_out(org: Org, request) -> ToolRequestOut:
    requester = identity_service.get_user_by_id(org, request.requested_by)
    return ToolRequestOut(
        id=str(request.id),
        request_type=request.request_type,
        name=request.name,
        link=request.link,
        intended_use_case=request.intended_use_case,
        data_tiers=request.data_tiers,
        requires_enterprise_account=request.requires_enterprise_account,
        status=request.status,
        ai_assessment_status=request.ai_assessment_status,
        ai_assessment_result=request.ai_assessment_result,
        ai_assessment_explanation=request.ai_assessment_explanation,
        requested_by=str(request.requested_by),
        requested_by_email=requester.email if requester else None,
        decided_by=str(request.decided_by) if request.decided_by else None,
        decided_at=request.decided_at,
        decision_note=request.decision_note,
        resulting_tool_id=str(request.resulting_tool_id) if request.resulting_tool_id else None,
        created_at=request.created_at,
        updated_at=request.updated_at,
    )


def _to_escalation_out(org: Org, escalation) -> EscalationOut:
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


def _to_module_out(view) -> TrainingModuleOut:
    m = view.module
    return TrainingModuleOut(
        id=str(m.id),
        order_index=m.order_index,
        key=m.key,
        title=m.title,
        description=m.description,
        body_text=m.body_text,
        video_type=m.video_type,
        video_url=m.video_url,
        questions=m.questions,
        completion_status=view.completion_status,
        answers=view.answers,
        is_locked=view.is_locked,
    )


def _training_summary(org: Org) -> TrainingSummaryOut:
    modules, counts, total_users = training_service.get_completion_summary(org)
    module_summaries = []
    total_pairs = 0
    total_completed = 0
    for m in modules:
        completed = counts.get(m.id, 0)
        pct = (completed / total_users * 100) if total_users else 0.0
        module_summaries.append(
            TrainingModuleSummary(
                module_id=str(m.id), title=m.title, total_users=total_users, completed_count=completed,
                completion_pct=round(pct, 1),
            )
        )
        total_pairs += total_users
        total_completed += completed
    org_pct = (total_completed / total_pairs * 100) if total_pairs else 0.0
    return TrainingSummaryOut(modules=module_summaries, org_completion_pct=round(org_pct, 1))


def _to_scan_out(org: Org, scan) -> ScanRunOut:
    requester = identity_service.get_user_by_id(org, scan.triggered_by)
    return ScanRunOut(
        id=str(scan.id),
        repo_full_name=scan.repo_full_name,
        commit_sha=scan.commit_sha,
        status=scan.status,
        triggered_by=str(scan.triggered_by),
        triggered_by_email=requester.email if requester else None,
        error_message=scan.error_message,
        finding_counts=codescan_service.finding_counts(org, str(scan.id)) if scan.status == "complete" else {},
        started_at=scan.started_at,
        completed_at=scan.completed_at,
        created_at=scan.created_at,
    )


def get_summary(org: Org, user: User) -> DashboardSummaryOut:
    """Pure composition over each module's already-proven service layer -
    no new business logic. Role gating happens here (server-side, defense
    in depth) rather than only in the frontend: a caller who can't approve
    tools gets an empty pending_tool_requests/pending_policy_drafts/
    pending_alerts/tool_request_counts/escalation_counts/training_summary,
    same asymmetry the pre-Milestone-10 dashboard page encoded client-side."""
    govern = _is_govern(user)
    assure = _is_assure(user)
    can_approve = _can_approve_tools(user)

    all_policies = policy_service.list_policies(org)
    awaiting_approval = [p for p in all_policies if p.status == "draft" and p.storage_key is not None]

    my_policy_drafts = [_to_policy_out(org, p) for p in awaiting_approval if assure and str(p.created_by) == str(user.id)]
    pending_policy_drafts = [_to_policy_out(org, p) for p in awaiting_approval] if govern else []

    my_tool_requests_raw = [r for r in tools_service.list_requests(org, mine=user) if r.status == "pending"]
    my_tool_requests = [_to_tool_request_out(org, r) for r in my_tool_requests_raw]

    pending_tool_requests: list[ToolRequestOut] = []
    tool_request_counts: dict[str, int] = {}
    if can_approve:
        all_requests = tools_service.list_requests(org)
        tool_request_counts = {status: sum(1 for r in all_requests if r.status == status) for status in TOOL_REQUEST_STATUSES}
        pending_tool_requests = [_to_tool_request_out(org, r) for r in all_requests if r.status == "pending"]

    # No my_alerts - escalations are anonymous, so there is no per-user
    # "alerts you raised" list to hand back (see escalations/models.py).
    pending_alerts: list[EscalationOut] = []
    escalation_counts: dict[str, int] = {}
    if can_approve:
        all_alerts = escalations_service.list_escalations(org)
        escalation_counts = {status: sum(1 for e in all_alerts if e.status == status) for status in ESCALATION_STATUSES}
        pending_alerts = [_to_escalation_out(org, e) for e in all_alerts if e.status != "resolved"]

    my_training = [_to_module_out(v) for v in training_service.list_modules(org, user)]
    training_summary = _training_summary(org) if can_approve else None

    my_recent_scans = [_to_scan_out(org, s) for s in codescan_service.list_scans(org, mine=user)[:10]]
    scan_finding_counts = codescan_service.org_wide_finding_counts(org) if can_approve else {}

    return DashboardSummaryOut(
        pending_policy_drafts=pending_policy_drafts,
        pending_tool_requests=pending_tool_requests,
        pending_alerts=pending_alerts,
        my_policy_drafts=my_policy_drafts,
        my_tool_requests=my_tool_requests,
        my_training=my_training,
        training_summary=training_summary,
        tool_request_counts=tool_request_counts,
        escalation_counts=escalation_counts,
        my_recent_scans=my_recent_scans,
        scan_finding_counts=scan_finding_counts,
    )
