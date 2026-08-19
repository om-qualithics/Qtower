"""PLACEHOLDER prompt for the tool-request AI precheck - not the real
assessment prompt yet, per instruction to wire the plumbing now and drop
the real prompt in later. The one hard requirement future edits must keep:
the model must answer as strict JSON, {"classification": "approvable" |
"needs_review" | "cannot_approve", "explanation": "..."} - tasks.py parses
against exactly that contract, and a response that doesn't match it is
treated as a failed assessment (never as an approval)."""

TOOL_ASSESSMENT_SYSTEM_PROMPT = (
    "You are a placeholder AI policy assessment reviewer for Q Tower. "
    "TODO: replace this system prompt with the real assessment instructions. "
    'Always respond with strict JSON only: {"classification": '
    '"approvable" | "needs_review" | "cannot_approve", "explanation": "..."}.'
)


def build_assessment_prompt(policy_text: str | None, request_type: str, name: str, link: str, use_case: str) -> str:
    policy_section = policy_text if policy_text else "No approved AI policy exists yet for this organization."
    return (
        f"Active AI Policy:\n{policy_section}\n\n"
        f"Request type: {request_type}\n"
        f"Name: {name}\n"
        f"Link: {link}\n"
        f"Intended use case: {use_case}\n\n"
        "Classify this request against the active AI Policy above."
    )
