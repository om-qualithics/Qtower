from fastapi import APIRouter, Cookie, Depends, HTTPException

from apps.api.modules.authz import service as authz_service
from apps.api.modules.codescan import service as codescan_service
from apps.api.modules.codescan.schemas import (
    GithubConnectionCreate,
    GithubConnectionStatusOut,
    RepoOut,
    ScanCreate,
    ScanDetailOut,
    ScanReportDownloadOut,
    ScanRunOut,
)
from apps.api.modules.codescan.service import CodescanConnectionError, CodescanValidationError
from apps.api.modules.codescan.taxonomy import category_label
from apps.api.modules.codescan.tasks import scan_repository
from apps.api.modules.identity import service as identity_service
from apps.api.modules.licensing.service import require_valid_license

router = APIRouter(prefix="/codescan", tags=["codescan"], dependencies=[Depends(require_valid_license)])


def _require_user(session_token: str | None):
    user = identity_service.get_current_user(session_token)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def _to_scan_out(org, scan) -> ScanRunOut:
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


@router.post("/github/connection", response_model=GithubConnectionStatusOut)
def create_github_connection(body: GithubConnectionCreate, misty_session: str | None = Cookie(default=None)):
    user = _require_user(misty_session)
    if not authz_service.can(user, "codescan.connect"):
        raise HTTPException(status_code=403, detail="Forbidden")
    org = identity_service.get_org()
    try:
        connection = codescan_service.create_github_connection(org, user, body.app_id, body.private_key, body.installation_id)
    except CodescanValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except CodescanConnectionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return GithubConnectionStatusOut(
        configured=True, account_login=connection.account_login, app_slug=connection.app_slug, created_at=connection.created_at
    )


@router.get("/github/connection", response_model=GithubConnectionStatusOut)
def get_github_connection_status(misty_session: str | None = Cookie(default=None)):
    user = _require_user(misty_session)
    if not authz_service.can(user, "codescan.connect"):
        raise HTTPException(status_code=403, detail="Forbidden")
    org = identity_service.get_org()
    connection = codescan_service.get_connection_status(org)
    if connection is None:
        return GithubConnectionStatusOut(configured=False, account_login=None, app_slug=None, created_at=None)
    return GithubConnectionStatusOut(
        configured=True, account_login=connection.account_login, app_slug=connection.app_slug, created_at=connection.created_at
    )


@router.get("/github/repos", response_model=list[RepoOut])
def list_repos(misty_session: str | None = Cookie(default=None)):
    user = _require_user(misty_session)
    if not authz_service.can(user, "codescan.run"):
        raise HTTPException(status_code=403, detail="Forbidden")
    org = identity_service.get_org()
    try:
        repos = codescan_service.list_repos(org)
    except CodescanConnectionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [RepoOut(**r) for r in repos]


@router.post("/scans", response_model=ScanRunOut)
def create_scan(body: ScanCreate, misty_session: str | None = Cookie(default=None)):
    user = _require_user(misty_session)
    if not authz_service.can(user, "codescan.run"):
        raise HTTPException(status_code=403, detail="Forbidden")
    org = identity_service.get_org()
    try:
        scan = codescan_service.create_scan(org, user, body.repo_full_name)
    except CodescanValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except CodescanConnectionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    scan_repository.delay(str(scan.id), str(org.id))
    return _to_scan_out(org, scan)


@router.get("/scans", response_model=list[ScanRunOut])
def list_scans(mine: bool = False, misty_session: str | None = Cookie(default=None)):
    user = _require_user(misty_session)
    if not authz_service.can(user, "codescan.view"):
        raise HTTPException(status_code=403, detail="Forbidden")
    org = identity_service.get_org()
    scans = codescan_service.list_scans(org, mine=user if mine else None)
    return [_to_scan_out(org, s) for s in scans]


@router.get("/scans/{scan_id}", response_model=ScanDetailOut)
def get_scan(scan_id: str, misty_session: str | None = Cookie(default=None)):
    user = _require_user(misty_session)
    if not authz_service.can(user, "codescan.view"):
        raise HTTPException(status_code=403, detail="Forbidden")
    org = identity_service.get_org()
    scan = codescan_service.get_scan(org, scan_id)
    if scan is None:
        raise HTTPException(status_code=404, detail="Scan not found")
    findings = codescan_service.list_findings(org, scan_id) if scan.status == "complete" else []
    base = _to_scan_out(org, scan)
    return ScanDetailOut(
        **base.model_dump(),
        findings=[
            {
                "id": str(f.id),
                "category": f.category,
                "category_label": category_label(f.category),
                "severity": f.severity,
                "file_path": f.file_path,
                "line_start": f.line_start,
                "line_end": f.line_end,
                "description": f.description,
                "sources": f.sources,
                "confidence": f.confidence,
            }
            for f in findings
        ],
    )


@router.get("/scans/{scan_id}/report", response_model=ScanReportDownloadOut)
def get_scan_report(scan_id: str, misty_session: str | None = Cookie(default=None)):
    user = _require_user(misty_session)
    if not authz_service.can(user, "codescan.view"):
        raise HTTPException(status_code=403, detail="Forbidden")
    org = identity_service.get_org()
    url = codescan_service.get_report_download_url(org, scan_id)
    if url is None:
        raise HTTPException(status_code=404, detail="Report not found or scan not yet complete")
    return ScanReportDownloadOut(download_url=url)
