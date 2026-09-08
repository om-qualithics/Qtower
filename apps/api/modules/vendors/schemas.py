from datetime import date, datetime

from pydantic import BaseModel


class VendorChecklistItemOut(BaseModel):
    id: str
    key: str
    question: str
    tier: str
    applies_to: str
    sort_order: int


class VendorChecklistResponseOut(BaseModel):
    checklist_item_id: str
    answer: str
    evidence_note: str | None
    last_verified_date: date | None


class VendorOut(BaseModel):
    id: str
    name: str
    type: str
    category: str | None
    logo_url: str | None
    website_url: str | None
    status: str
    overall_score: float | None
    created_at: datetime


class VendorDetailOut(VendorOut):
    checklist_responses: list[VendorChecklistResponseOut]


class ChecklistResponseUpdate(BaseModel):
    checklist_item_id: str
    answer: str
    evidence_note: str | None = None
    last_verified_date: date | None = None


class ChecklistResponsesUpdate(BaseModel):
    responses: list[ChecklistResponseUpdate]


class VendorRequestChecklistAnswer(BaseModel):
    checklist_item_id: str
    answer: str
    evidence_note: str | None = None


class VendorRequestOut(BaseModel):
    id: str
    name: str
    type: str
    website_url: str | None
    business_justification: str
    projected_status: str | None
    overall_score: float | None
    status: str
    requested_by: str
    requested_by_email: str | None
    decided_by: str | None
    decided_at: datetime | None
    resulting_vendor_id: str | None
    created_at: datetime
    checklist_responses: list[VendorRequestChecklistAnswer]


class VendorRequestCreate(BaseModel):
    name: str
    type: str
    website_url: str | None = None
    business_justification: str
    responses: list[VendorRequestChecklistAnswer] = []


class VendorLogoUrlUpdate(BaseModel):
    logo_url: str | None = None
