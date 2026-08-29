from datetime import datetime

from pydantic import BaseModel


class EscalationOut(BaseModel):
    id: str
    category: str
    description: str
    related_tool_request_id: str | None
    related_policy_id: str | None
    status: str
    assigned_to: str | None
    resolution_note: str | None
    has_attachment: bool
    attachment_filename: str | None
    created_at: datetime
    updated_at: datetime


class EscalationUpdate(BaseModel):
    status: str | None = None
    assigned_to: str | None = None
    resolution_note: str | None = None


class EscalationDownloadOut(BaseModel):
    download_url: str
