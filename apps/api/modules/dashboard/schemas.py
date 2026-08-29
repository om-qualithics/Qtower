from pydantic import BaseModel

from apps.api.modules.codescan.schemas import ScanRunOut
from apps.api.modules.escalations.schemas import EscalationOut
from apps.api.modules.policy.schemas import PolicyListItemOut
from apps.api.modules.tools.schemas import ToolRequestOut
from apps.api.modules.training.schemas import TrainingModuleOut, TrainingSummaryOut


class DashboardSummaryOut(BaseModel):
    """One-call replacement for the seven separate fetches the frontend
    used to make. Every list here is already role-filtered server-side
    (see dashboard/service.py::get_summary) - a caller without approval
    rights gets empty pending_*/counts/training_summary back from the
    service itself, not just a hidden section in the UI."""

    pending_policy_drafts: list[PolicyListItemOut]
    pending_tool_requests: list[ToolRequestOut]
    pending_alerts: list[EscalationOut]

    my_policy_drafts: list[PolicyListItemOut]
    my_tool_requests: list[ToolRequestOut]
    # No my_alerts - escalations are anonymous, there is no "mine" to
    # report back to a specific user (see escalations/models.py).

    my_training: list[TrainingModuleOut]
    training_summary: TrainingSummaryOut | None

    tool_request_counts: dict[str, int]
    escalation_counts: dict[str, int]

    # codescan.view is open to every role (Milestone 13 - "segregation
    # later"), so my_recent_scans is never empty-gated the way the other
    # my_* lists sometimes are; scan_finding_counts (org-wide) mirrors the
    # can_approve gating the other *_counts fields already use.
    my_recent_scans: list[ScanRunOut]
    scan_finding_counts: dict[str, int]
