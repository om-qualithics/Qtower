"""Tier 1 finding taxonomy (Qtower_CodeScan_Phase1_Handoff.md section 3) -
static Python data, same "catalog as code" precedent as
policy/questions.py's question catalog and authz's permission matrix.
Both the report renderer and the frontend's category labels read from
this - there is no DB table for the taxonomy itself, only for the
Finding rows that reference a category key."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CategoryDef:
    key: str
    label: str
    tools: tuple[str, ...]


TIER1_CATEGORIES: tuple[CategoryDef, ...] = (
    CategoryDef("sql_injection", "SQL injection", ("semgrep",)),
    CategoryDef("command_injection", "Command/OS injection", ("semgrep", "bandit")),
    CategoryDef("xss", "Cross-site scripting (XSS)", ("semgrep",)),
    CategoryDef("log_injection", "Log injection", ("semgrep",)),
    CategoryDef("ldap_injection", "LDAP injection", ("semgrep",)),
    CategoryDef("xxe_injection", "XXE injection", ("semgrep", "bandit")),
    CategoryDef("ssti", "Server-side template injection", ("semgrep",)),
    CategoryDef("nosql_injection", "NoSQL injection", ("semgrep",)),
    CategoryDef("path_traversal", "Path traversal", ("semgrep", "bandit")),
    CategoryDef("csv_injection", "CSV/formula injection", ("semgrep",)),
    CategoryDef("hardcoded_secrets", "Hardcoded credentials/secrets", ("gitleaks",)),
    CategoryDef("missing_auth", "Missing authentication on endpoints", ("semgrep",)),
    CategoryDef("idor", "Broken authorization (IDOR)", ("semgrep",)),
    CategoryDef("permissive_default_roles", "Overly permissive default roles", ("semgrep",)),
    CategoryDef("missing_rate_limiting", "Missing rate limiting on auth", ("semgrep",)),
    CategoryDef("insecure_session", "Insecure session management", ("semgrep", "bandit")),
    CategoryDef("missing_csrf", "Missing CSRF protection", ("semgrep",)),
    CategoryDef("weak_crypto", "Insecure crypto algorithms", ("bandit", "semgrep")),
    CategoryDef("hardcoded_crypto_key", "Hardcoded encryption keys/IVs", ("bandit", "gitleaks")),
    CategoryDef("weak_randomness", "Weak randomness for security use", ("bandit",)),
    CategoryDef("missing_transport_encryption", "Missing encryption at rest/in transit", ("semgrep",)),
    CategoryDef("improper_cert_validation", "Improper certificate validation", ("bandit", "semgrep")),
    CategoryDef("ssrf", "SSRF", ("semgrep",)),
    CategoryDef("insecure_deserialization", "Insecure deserialization", ("bandit", "semgrep")),
    CategoryDef("missing_input_validation", "Missing input validation", ("semgrep",)),
    CategoryDef("improper_error_handling", "Improper error handling", ("semgrep",)),
    CategoryDef("missing_output_encoding", "Missing output encoding", ("semgrep",)),
    CategoryDef("overly_broad_iam", "Overly broad IAM/cloud permissions", ("trivy",)),
    CategoryDef("exposed_debug_endpoints", "Exposed debug endpoints in prod", ("semgrep",)),
    CategoryDef("insecure_default_config", "Insecure default configurations", ("trivy",)),
    # Not in the handoff doc's 30-item table, but real output Trivy/Gitleaks
    # produce that doesn't map cleanly to any category above - kept as a
    # deliberate catch-all rather than silently dropping real findings.
    CategoryDef("vulnerable_dependency", "Vulnerable dependency", ("trivy",)),
    CategoryDef("other", "Other", ("semgrep", "bandit", "gitleaks", "trivy")),
)

CATEGORY_KEYS: tuple[str, ...] = tuple(c.key for c in TIER1_CATEGORIES)
_CATEGORY_BY_KEY = {c.key: c for c in TIER1_CATEGORIES}


def category_label(key: str) -> str:
    cat = _CATEGORY_BY_KEY.get(key)
    return cat.label if cat else key
