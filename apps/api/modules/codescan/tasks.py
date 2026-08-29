"""The scan execution task - subprocess-in-worker, not one Docker
container per scan (see plan: this app's deployment model is one full
Qtower deployment per org, so the "isolate customer A from customer B"
threat model this doc's original Docker-per-scan sketch was written for
doesn't apply here; the only isolation that matters is protecting this
one deployment's own secrets from a scanned repo, and a
tempfile.TemporaryDirectory() cleaned up on every exit path already
satisfies "ephemeral disk only, no leftover code between scans" without
needing container-level isolation). Same "Celery-task-only" rule every
other ai_gateway/notification caller already follows - never invoked
synchronously from a route."""

import subprocess
import tempfile
import uuid
from pathlib import Path

from apps.api.core import storage
from apps.api.core.celery_app import celery_app
from apps.api.core.crypto import decrypt_secret
from apps.api.core.db import SessionLocal
from apps.api.modules.codescan import github_client, service as codescan_service
from apps.api.modules.codescan.constants import CLONE_TIMEOUT_SECONDS, SCAN_TOOL_TIMEOUT_SECONDS, scan_report_key
from apps.api.modules.codescan.parsers import dedupe, parse_bandit, parse_gitleaks, parse_semgrep, parse_trivy
from apps.api.modules.codescan.report import render_report_pdf
from apps.api.modules.identity.models import Org


def _load_org(org_id: str) -> Org | None:
    db = SessionLocal()
    try:
        return db.get(Org, uuid.UUID(org_id))
    finally:
        db.close()


def _scrub(text: str, *secrets: str) -> str:
    for secret in secrets:
        if secret:
            text = text.replace(secret, "***")
    return text


def _run(args: list[str], cwd: str, timeout: int) -> str:
    """Runs a scanner subprocess and returns stdout - never raises on a
    tool's own nonzero exit code (Semgrep/Bandit/Gitleaks all exit
    nonzero when findings exist, which is not a failure), only on the
    subprocess itself failing to start or timing out."""
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    return result.stdout


@celery_app.task(name="codescan.scan_repository")
def scan_repository(scan_id: str, org_id: str) -> None:
    org = _load_org(org_id)
    if org is None:
        return

    connection = codescan_service.get_connection_status(org)
    scan = codescan_service.get_scan(org, scan_id)
    if connection is None or scan is None:
        codescan_service.mark_scan_failed(org_id, scan_id, error_message="Scan or GitHub connection no longer exists")
        return

    codescan_service.mark_scan_running(org_id, scan_id)
    token = ""

    try:
        private_key = decrypt_secret(connection.private_key_encrypted)
        token = github_client.mint_installation_token(connection.app_id, private_key, connection.installation_id)
        clone_url = github_client.clone_url_with_token(scan.repo_full_name, token)

        with tempfile.TemporaryDirectory(prefix="codescan-") as tmpdir:
            clone = subprocess.run(
                ["git", "clone", "--depth", "1", clone_url, tmpdir],
                capture_output=True,
                text=True,
                timeout=CLONE_TIMEOUT_SECONDS,
            )
            if clone.returncode != 0:
                raise RuntimeError(f"git clone failed: {_scrub(clone.stderr, token)[:400]}")

            commit_sha = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=tmpdir, capture_output=True, text=True, timeout=30
            ).stdout.strip()

            all_findings: list[dict] = []
            all_findings += parse_semgrep(_run(["semgrep", "--config=auto", "--json", "--quiet", "."], tmpdir, SCAN_TOOL_TIMEOUT_SECONDS))
            all_findings += parse_bandit(_run(["bandit", "-r", ".", "-f", "json"], tmpdir, SCAN_TOOL_TIMEOUT_SECONDS))

            leaks_path = Path(tmpdir) / "_gitleaks_report.json"
            subprocess.run(
                ["gitleaks", "detect", "--source", ".", "--report-format", "json",
                 "--report-path", str(leaks_path), "--exit-code", "0", "--no-git"],
                cwd=tmpdir, capture_output=True, text=True, timeout=SCAN_TOOL_TIMEOUT_SECONDS,
            )
            gitleaks_json = leaks_path.read_text() if leaks_path.exists() else "[]"
            all_findings += parse_gitleaks(gitleaks_json)

            all_findings += parse_trivy(
                _run(["trivy", "fs", "--format", "json", "--scanners", "vuln,misconfig", "--quiet", "."],
                     tmpdir, SCAN_TOOL_TIMEOUT_SECONDS)
            )

        deduped = dedupe(all_findings)
        codescan_service.bulk_insert_findings(org_id, scan_id, deduped)

        counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for f in deduped:
            counts[f["severity"]] = counts.get(f["severity"], 0) + 1

        pdf_bytes = render_report_pdf(
            repo_full_name=scan.repo_full_name, commit_sha=commit_sha, findings=deduped, counts=counts, trend_note=None
        )
        report_key = scan_report_key(org_id, scan_id)
        storage.upload_bytes(report_key, pdf_bytes, content_type="application/pdf")

        codescan_service.mark_scan_complete(org_id, scan_id, commit_sha=commit_sha, report_pdf_key=report_key)

        # Critical findings no longer auto-create an Escalation (dropped per
        # product decision - Raise Alert is anonymous, and a code-scan-
        # triggered alert would always have an identifiable "reporter",
        # whoever ran the scan, undermining that guarantee). Critical
        # findings still surface in the scan's own findings list/report.
    except Exception as exc:  # noqa: BLE001 - any failure must land the scan on "failed", never leave it ambiguously stuck
        codescan_service.mark_scan_failed(org_id, scan_id, error_message=_scrub(str(exc), token))
