from pydantic import BaseModel

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
    my_alerts: list[EscalationOut]

    my_training: list[TrainingModuleOut]
    training_summary: TrainingSummaryOut | None

    tool_request_counts: dict[str, int]
    escalation_counts: dict[str, int]
