from datetime import datetime

from pydantic import BaseModel


class GithubConnectionCreate(BaseModel):
    app_id: str
    private_key: str
    installation_id: str


class GithubConnectionStatusOut(BaseModel):
    configured: bool
    account_login: str | None
    app_slug: str | None
    created_at: datetime | None


class RepoOut(BaseModel):
    full_name: str
    default_branch: str
    private: bool


class ScanCreate(BaseModel):
    repo_full_name: str


class FindingOut(BaseModel):
    id: str
    category: str
    category_label: str
    severity: str
    file_path: str
    line_start: int | None
    line_end: int | None
    description: str
    sources: list[str]
    confidence: str


class ScanRunOut(BaseModel):
    id: str
    repo_full_name: str
    commit_sha: str | None
    status: str
    triggered_by: str
    triggered_by_email: str | None
    error_message: str | None
    finding_counts: dict[str, int]
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


class ScanDetailOut(ScanRunOut):
    findings: list[FindingOut]


class ScanReportDownloadOut(BaseModel):
    download_url: str
