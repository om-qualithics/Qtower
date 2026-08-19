from datetime import datetime

from pydantic import BaseModel


class ApprovedToolOut(BaseModel):
    id: str
    name: str
    description: str
    source_type: str
    access_url: str
    allowed_tiers: list[str]
    details: str | None
    created_at: datetime


class ToolRequestOut(BaseModel):
    id: str
    request_type: str
    name: str
    link: str
    intended_use_case: str
    status: str
    ai_assessment_status: str
    ai_assessment_result: str | None
    ai_assessment_explanation: str | None
    requested_by: str
    requested_by_email: str | None
    decided_by: str | None
    decided_at: datetime | None
    decision_note: str | None
    resulting_tool_id: str | None
    created_at: datetime
    updated_at: datetime


class ToolRequestCreate(BaseModel):
    request_type: str
    name: str
    link: str
    intended_use_case: str


class ToolRequestApprove(BaseModel):
    description: str
    allowed_tiers: list[str]


class ToolRequestReject(BaseModel):
    reason: str | None = None


class ApprovedToolUpdate(BaseModel):
    name: str
    description: str
    access_url: str
    allowed_tiers: list[str]
