# code_scan_critical is deliberately absent - Code Scan critical findings no
# longer create escalations (see codescan/tasks.py) since Raise Alert is
# anonymous and a code-scan-triggered alert would have an obvious "reporter"
# (whoever ran the scan), breaking that guarantee. The Postgres enum type
# still has the value (see migration 0013's note) but the app never writes it.
CATEGORIES = ("policy_violation", "unapproved_tool_use", "data_exposure_concern", "other")

# Screenshots are the single most likely attachment for an AI-misuse
# report, alongside PDFs/Word docs of the relevant conversation/contract.
ALLOWED_ATTACHMENT_EXTENSIONS = (".pdf", ".doc", ".docx", ".png", ".jpg", ".jpeg")


def escalation_attachment_key(org_id: str, escalation_id: str, filename: str) -> str:
    return f"escalations/{org_id}/{escalation_id}/{filename}"
