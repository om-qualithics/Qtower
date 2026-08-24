from datetime import datetime

from pydantic import BaseModel


class TrainingQuestion(BaseModel):
    id: str
    prompt: str
    options: list[str] | None = None


class TrainingModuleOut(BaseModel):
    """Module content + the *current user's* progress against it, joined
    in by the service - same "embed the caller-specific bit" shape as
    ToolRequestOut embedding requested_by_email."""

    id: str
    order_index: int
    key: str
    title: str
    description: str
    body_text: str
    video_type: str
    video_url: str | None
    questions: list[TrainingQuestion]
    completion_status: str
    answers: dict[str, str]
    is_locked: bool


class TrainingModuleCreate(BaseModel):
    order_index: int
    key: str
    title: str
    description: str
    body_text: str
    video_type: str = "placeholder"
    video_url: str | None = None
    questions: list[TrainingQuestion] = []


class TrainingModuleUpdate(BaseModel):
    order_index: int | None = None
    title: str | None = None
    description: str | None = None
    body_text: str | None = None
    video_type: str | None = None
    video_url: str | None = None
    questions: list[TrainingQuestion] | None = None
    is_active: bool | None = None


class TrainingProgressUpdate(BaseModel):
    answers: dict[str, str]


class TrainingModuleSummary(BaseModel):
    module_id: str
    title: str
    total_users: int
    completed_count: int
    completion_pct: float


class TrainingSummaryOut(BaseModel):
    modules: list[TrainingModuleSummary]
    org_completion_pct: float


class TrainingCompletionOut(BaseModel):
    status: str
    answers: dict[str, str]
    completed_at: datetime | None
