MAX_CLONE_SIZE_MB = 500  # sanity ceiling for `git clone --depth 1`, not enforced by size but by clone timeout below
CLONE_TIMEOUT_SECONDS = 300
SCAN_TOOL_TIMEOUT_SECONDS = 300


def scan_report_key(org_id: str, scan_id: str) -> str:
    return f"codescan/{org_id}/{scan_id}/report.pdf"
