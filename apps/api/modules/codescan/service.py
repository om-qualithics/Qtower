import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from apps.api.core import storage
from apps.api.core.crypto import decrypt_secret, encrypt_secret
from apps.api.core.db import org_scoped_session
from apps.api.modules.codescan import github_client
from apps.api.modules.codescan.constants import scan_report_key
from apps.api.modules.codescan.models import Finding, GithubConnection, ScanRun
from apps.api.modules.identity.models import Org, User


class CodescanValidationError(Exception):
    pass


class CodescanConnectionError(Exception):
    pass


def create_github_connection(org: Org, user: User, app_id: str, private_key: str, installation_id: str) -> GithubConnection:
    """Validates immediately by minting a token and listing repos once -
    fail fast with a clear error on bad input, same "call the real API at
    connect-time, don't silently accept" pattern
    identity_service.create_sso_connection() already uses against Jackson.
    Replaces any existing connection (at most one per org, same shape as
    OrgSsoConnection)."""
    if not app_id.strip() or not private_key.strip() or not installation_id.strip():
        raise CodescanValidationError("App ID, private key, and installation ID are all required")

    try:
        token = github_client.mint_installation_token(app_id.strip(), private_key, installation_id.strip())
        repos = github_client.list_repositories(token)
    except github_client.GithubClientError as exc:
        raise CodescanConnectionError(str(exc)) from exc

    account_login = repos[0]["owner"]["login"] if repos else None
    encrypted_key = encrypt_secret(private_key)

    with org_scoped_session(str(org.id)) as db:
        existing = db.scalars(select(GithubConnection).where(GithubConnection.org_id == org.id)).first()
        if existing:
            db.delete(existing)
            db.flush()
        connection = GithubConnection(
            org_id=org.id,
            app_id=app_id.strip(),
            installation_id=installation_id.strip(),
            private_key_encrypted=encrypted_key,
            account_login=account_login,
            created_by=user.id,
        )
        db.add(connection)
        db.flush()
        db.refresh(connection)
        db.expunge(connection)
        return connection


def get_connection_status(org: Org) -> GithubConnection | None:
    with org_scoped_session(str(org.id)) as db:
        connection = db.scalars(select(GithubConnection).where(GithubConnection.org_id == org.id)).first()
        if connection is not None:
            db.expunge(connection)
        return connection


def _get_connection_or_raise(org: Org) -> GithubConnection:
    connection = get_connection_status(org)
    if connection is None:
        raise CodescanConnectionError("No GitHub connection configured for this org yet")
    return connection


def _mint_token(connection: GithubConnection) -> str:
    private_key = decrypt_secret(connection.private_key_encrypted)
    try:
        return github_client.mint_installation_token(connection.app_id, private_key, connection.installation_id)
    except github_client.GithubClientError as exc:
        raise CodescanConnectionError(str(exc)) from exc


def list_repos(org: Org) -> list[dict]:
    """Live call, no persisted repo table - see plan: avoids a stale,
    separately-maintained repo list."""
    connection = _get_connection_or_raise(org)
    token = _mint_token(connection)
    try:
        repos = github_client.list_repositories(token)
    except github_client.GithubClientError as exc:
        raise CodescanConnectionError(str(exc)) from exc
    return [
        {"full_name": r["full_name"], "default_branch": r.get("default_branch", "main"), "private": r.get("private", True)}
        for r in repos
    ]


def create_scan(org: Org, user: User, repo_full_name: str) -> ScanRun:
    if not repo_full_name.strip():
        raise CodescanValidationError("repo_full_name is required")
    connection = _get_connection_or_raise(org)

    with org_scoped_session(str(org.id)) as db:
        scan = ScanRun(
            org_id=org.id,
            github_connection_id=connection.id,
            repo_full_name=repo_full_name.strip(),
            triggered_by=user.id,
        )
        db.add(scan)
        db.flush()
        db.refresh(scan)
        db.expunge(scan)
        return scan


def list_scans(org: Org, *, mine: User | None = None) -> list[ScanRun]:
    with org_scoped_session(str(org.id)) as db:
        query = select(ScanRun).where(ScanRun.org_id == org.id)
        if mine is not None:
            query = query.where(ScanRun.triggered_by == mine.id)
        scans = db.scalars(query.order_by(ScanRun.created_at.desc())).all()
        for scan in scans:
            db.expunge(scan)
        return list(scans)


def get_scan(org: Org, scan_id: str) -> ScanRun | None:
    with org_scoped_session(str(org.id)) as db:
        scan = db.get(ScanRun, uuid.UUID(scan_id))
        if scan is None or str(scan.org_id) != str(org.id):
            return None
        db.expunge(scan)
        return scan


_SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def list_findings(org: Org, scan_id: str) -> list[Finding]:
    """Ordered critical -> high -> medium -> low (the app's one canonical
    ordering for a scan's findings) so every caller - the detail view, the
    PDF report - shows the same order without each re-sorting itself."""
    with org_scoped_session(str(org.id)) as db:
        findings = db.scalars(
            select(Finding).where(Finding.org_id == org.id, Finding.scan_run_id == uuid.UUID(scan_id))
        ).all()
        for finding in findings:
            db.expunge(finding)
        return sorted(findings, key=lambda f: _SEVERITY_RANK.get(f.severity, 99))


def finding_counts(org: Org, scan_id: str) -> dict[str, int]:
    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for finding in list_findings(org, scan_id):
        counts[finding.severity] = counts.get(finding.severity, 0) + 1
    return counts


def org_wide_finding_counts(org: Org) -> dict[str, int]:
    """Severity counts summed across the org's most recent *completed*
    scan per repo - the dashboard's org-wide "Code Scan" card. Powers a
    quick "what's our current standing" view, not a running total across
    every scan ever run (a repo scanned 10 times shouldn't count its
    findings 10x)."""
    latest_per_repo: dict[str, ScanRun] = {}
    for scan in list_scans(org):
        if scan.status != "complete":
            continue
        existing = latest_per_repo.get(scan.repo_full_name)
        if existing is None or scan.created_at > existing.created_at:
            latest_per_repo[scan.repo_full_name] = scan

    totals = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for scan in latest_per_repo.values():
        counts = finding_counts(org, str(scan.id))
        for severity, count in counts.items():
            totals[severity] = totals.get(severity, 0) + count
    return totals


def get_report_download_url(org: Org, scan_id: str) -> str | None:
    scan = get_scan(org, scan_id)
    if scan is None or not scan.report_pdf_key:
        return None
    return storage.presigned_url(scan.report_pdf_key, expires_seconds=300)


def mark_scan_running(org_id: str, scan_id: str) -> None:
    with org_scoped_session(org_id) as db:
        scan = db.get(ScanRun, uuid.UUID(scan_id))
        if scan is not None:
            scan.status = "running"
            scan.started_at = datetime.now(timezone.utc)


def mark_scan_complete(org_id: str, scan_id: str, *, commit_sha: str, report_pdf_key: str) -> None:
    with org_scoped_session(org_id) as db:
        scan = db.get(ScanRun, uuid.UUID(scan_id))
        if scan is not None:
            scan.status = "complete"
            scan.commit_sha = commit_sha
            scan.report_pdf_key = report_pdf_key
            scan.completed_at = datetime.now(timezone.utc)


def mark_scan_failed(org_id: str, scan_id: str, *, error_message: str) -> None:
    with org_scoped_session(org_id) as db:
        scan = db.get(ScanRun, uuid.UUID(scan_id))
        if scan is not None:
            scan.status = "failed"
            scan.error_message = error_message[:500]
            scan.completed_at = datetime.now(timezone.utc)


def bulk_insert_findings(org_id: str, scan_id: str, findings: list[dict]) -> None:
    with org_scoped_session(org_id) as db:
        for f in findings:
            db.add(
                Finding(
                    org_id=uuid.UUID(org_id),
                    scan_run_id=uuid.UUID(scan_id),
                    category=f["category"],
                    severity=f["severity"],
                    file_path=f["file_path"],
                    line_start=f.get("line_start"),
                    line_end=f.get("line_end"),
                    description=f["description"],
                    sources=f["sources"],
                    confidence=f.get("confidence", "medium"),
                )
            )
