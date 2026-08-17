TEMPLATE_KEY = "policy-templates/enterprise_ai_policy_v1.docx"


def policy_storage_key(org_id: str, policy_id: str, version: int) -> str:
    return f"policies/{org_id}/{policy_id}/v{version}.docx"
