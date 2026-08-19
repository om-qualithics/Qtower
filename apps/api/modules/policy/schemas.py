from datetime import datetime
from typing import Any

from pydantic import BaseModel


class OptionOut(BaseModel):
    value: str
    label: str
    checked_by_default: bool


class ColumnOut(BaseModel):
    key: str
    label: str


class QuestionOut(BaseModel):
    key: str
    type: str
    label: str
    required: bool
    options: list[OptionOut]
    allow_other: bool
    category: str | None
    columns: list[ColumnOut]
    initial_rows: list[dict]
    addable: bool
    locked_rows: bool


class StepOut(BaseModel):
    id: int
    title: str
    questions: list[QuestionOut]


class PolicyOut(BaseModel):
    id: str
    status: str
    source: str
    has_document: bool
    current_step: int
    version: int
    policy_owner_name: str | None
    approver_name: str | None
    answers: dict[str, Any]
    created_by: str | None
    generated_at: datetime | None
    approved_at: datetime | None
    created_at: datetime
    updated_at: datetime


class PolicyListItemOut(BaseModel):
    id: str
    status: str
    source: str
    has_document: bool
    current_step: int
    version: int
    policy_owner_name: str | None
    created_by: str | None
    generated_at: datetime | None
    approved_at: datetime | None
    created_at: datetime
    updated_at: datetime


class PolicyStepUpdate(BaseModel):
    step: int
    answers: dict[str, Any]


class PolicyDownloadOut(BaseModel):
    download_url: str


class PolicyGenerateError(BaseModel):
    missing_required: list[str]
