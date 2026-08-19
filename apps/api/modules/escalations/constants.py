CATEGORIES = ("policy_violation", "unapproved_tool_use", "data_exposure_concern", "other")

# Screenshots are the single most likely attachment for an AI-misuse
# report, alongside PDFs/Word docs of the relevant conversation/contract.
ALLOWED_ATTACHMENT_EXTENSIONS = (".pdf", ".doc", ".docx", ".png", ".jpg", ".jpeg")


def escalation_attachment_key(org_id: str, escalation_id: str, filename: str) -> str:
    return f"escalations/{org_id}/{escalation_id}/{filename}"
