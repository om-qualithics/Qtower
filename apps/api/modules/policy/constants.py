TEMPLATE_KEY = "policy-templates/enterprise_ai_policy_v1.docx"

MAX_UPLOAD_SIZE_BYTES = 20 * 1024 * 1024


def policy_storage_key(org_id: str, policy_id: str) -> str:
    """One object per policy row - not per version, since a draft's real
    version number isn't known until it's approved and the file shouldn't
    need renaming/re-uploading at that point."""
    return f"policies/{org_id}/{policy_id}/document.docx"
