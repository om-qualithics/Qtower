from datetime import datetime

from pydantic import BaseModel


class LinkIn(BaseModel):
    """Exactly one of tool_id/other_name (or vendor_id/other_name) must be
    set - validated in service.py, not here, since the two link kinds
    share this same shape but reference different catalogs."""

    tool_id: str | None = None
    vendor_id: str | None = None
    other_name: str | None = None


class LinkOut(BaseModel):
    id: str
    tool_id: str | None = None
    vendor_id: str | None = None
    other_name: str | None
    # Populated by the router from the live catalog - None for an "other"
    # (not registered in inventory) link, otherwise the linked entry's
    # own name/status so the risk-rollup view doesn't need a second fetch.
    name: str | None
    status: str | None
    in_inventory: bool


class ProjectOut(BaseModel):
    id: str
    name: str
    description: str
    lifecycle_stage: str
    owner_user_id: str | None
    created_at: datetime
    updated_at: datetime


class ProjectDetailOut(ProjectOut):
    linked_tools: list[LinkOut]
    linked_vendors: list[LinkOut]


class ProjectRequestOut(BaseModel):
    id: str
    name: str
    description: str
    business_justification: str
    data_flow_description: str
    data_tiers: list[str]
    human_in_loop: bool
    status: str
    project_assessment_status: str
    project_assessment_result: str | None
    project_assessment_explanation: str | None
    requested_by: str
    requested_by_email: str | None
    decided_by: str | None
    decided_at: datetime | None
    resulting_project_id: str | None
    created_at: datetime
    updated_at: datetime
    linked_tools: list[LinkOut]
    linked_vendors: list[LinkOut]


class ProjectRequestCreate(BaseModel):
    name: str
    description: str
    business_justification: str
    data_flow_description: str
    data_tiers: list[str] = []
    human_in_loop: bool = False
    tool_links: list[LinkIn] = []
    vendor_links: list[LinkIn] = []


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    lifecycle_stage: str | None = None
