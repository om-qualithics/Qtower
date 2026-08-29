"""Normalizes each scanner's native JSON output into the common Finding
shape (category/severity/file_path/line_start/line_end/description/
sources/confidence) and deduplicates overlapping findings across tools.

Category assignment is a best-effort keyword classifier over each raw
finding's rule id/message, not a hand-maintained per-rule-id mapping
table - Semgrep/Bandit's rule catalogs run into the thousands, and a
precise mapping is real, ongoing content work out of scope for Phase 1.
Every raw finding still lands in *some* category (falling back to
"other"), so nothing is silently dropped - just occasionally
mis-bucketed, which is a labeling-quality gap, not a correctness one
(severity/file/line/description all still come straight from the tool).
"""

import json
import re

_KEYWORD_CATEGORY_MAP: list[tuple[re.Pattern, str]] = [
    (re.compile(r"sql[-_]?inject", re.I), "sql_injection"),
    (re.compile(r"command[-_]?inject|os[-_]?system|subprocess|shell[-_]?inject", re.I), "command_injection"),
    (re.compile(r"\bxss\b|cross-site-scripting", re.I), "xss"),
    (re.compile(r"log[-_]?inject", re.I), "log_injection"),
    (re.compile(r"ldap", re.I), "ldap_injection"),
    (re.compile(r"\bxxe\b|xml.*external.*entity", re.I), "xxe_injection"),
    (re.compile(r"template[-_]?inject|ssti", re.I), "ssti"),
    (re.compile(r"nosql|mongo.*inject", re.I), "nosql_injection"),
    (re.compile(r"path[-_]?travers|directory[-_]?travers", re.I), "path_traversal"),
    (re.compile(r"csv[-_]?inject|formula[-_]?inject", re.I), "csv_injection"),
    (re.compile(r"hardcoded[-_]?password|hardcoded[-_]?secret|hardcoded[-_]?credential|api[-_]?key", re.I), "hardcoded_secrets"),
    (re.compile(r"missing[-_]?auth|no[-_]?auth|unauthenticated", re.I), "missing_auth"),
    (re.compile(r"\bidor\b|broken[-_]?access|missing[-_]?ownership", re.I), "idor"),
    (re.compile(r"default[-_]?role|default[-_]?admin", re.I), "permissive_default_roles"),
    (re.compile(r"rate[-_]?limit", re.I), "missing_rate_limiting"),
    (re.compile(r"session", re.I), "insecure_session"),
    (re.compile(r"csrf", re.I), "missing_csrf"),
    (re.compile(r"\bmd5\b|\bsha1\b|\bdes\b|weak[-_]?cipher|weak[-_]?crypto|weak[-_]?hash", re.I), "weak_crypto"),
    (re.compile(r"hardcoded.*(key|iv)\b", re.I), "hardcoded_crypto_key"),
    (re.compile(r"random|insecure.*random|predictable", re.I), "weak_randomness"),
    (re.compile(r"\btls\b|\bssl\b.*disabled|no[-_]?encryption|cleartext", re.I), "missing_transport_encryption"),
    (re.compile(r"verify=false|cert.*valid|ssl.*verif", re.I), "improper_cert_validation"),
    (re.compile(r"\bssrf\b|server-side request forgery", re.I), "ssrf"),
    (re.compile(r"deserializ|\bpickle\b|yaml\.load\b", re.I), "insecure_deserialization"),
    (re.compile(r"input[-_]?valid|missing[-_]?valid", re.I), "missing_input_validation"),
    (re.compile(r"error[-_]?handl|stack[-_]?trace|debug.*error", re.I), "improper_error_handling"),
    (re.compile(r"output[-_]?encod|escap", re.I), "missing_output_encoding"),
    (re.compile(r"iam|wildcard.*permission|\*.*policy", re.I), "overly_broad_iam"),
    (re.compile(r"debug\s*=\s*true|debug[-_]?endpoint|debug[-_]?mode", re.I), "exposed_debug_endpoints"),
    (re.compile(r"insecure[-_]?default|misconfig", re.I), "insecure_default_config"),
    (re.compile(r"\bcve-\d", re.I), "vulnerable_dependency"),
]


def _classify(*texts: str) -> str:
    combined = " ".join(t for t in texts if t)
    for pattern, category in _KEYWORD_CATEGORY_MAP:
        if pattern.search(combined):
            return category
    return "other"


_SEVERITY_MAP = {
    "error": "high", "critical": "critical", "high": "high", "warning": "medium",
    "medium": "medium", "info": "low", "low": "low", "unknown": "medium",
}
_CONFIDENCE_MAP = {"high": "high", "medium": "medium", "low": "low"}


def parse_semgrep(raw_json: str) -> list[dict]:
    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError:
        return []
    findings = []
    for r in data.get("results", []):
        extra = r.get("extra", {})
        check_id = r.get("check_id", "")
        metadata = extra.get("metadata", {}) or {}
        findings.append(
            {
                "category": _classify(check_id, extra.get("message", "")),
                "severity": _SEVERITY_MAP.get(str(extra.get("severity", "")).lower(), "medium"),
                "file_path": r.get("path", "unknown"),
                "line_start": (r.get("start") or {}).get("line"),
                "line_end": (r.get("end") or {}).get("line"),
                "description": extra.get("message", check_id)[:2000],
                "sources": ["semgrep"],
                "confidence": _CONFIDENCE_MAP.get(str(metadata.get("confidence", "")).lower(), "medium"),
            }
        )
    return findings


def parse_bandit(raw_json: str) -> list[dict]:
    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError:
        return []
    findings = []
    for r in data.get("results", []):
        test_name = r.get("test_name", "")
        findings.append(
            {
                "category": _classify(test_name, r.get("issue_text", "")),
                "severity": _SEVERITY_MAP.get(str(r.get("issue_severity", "")).lower(), "medium"),
                "file_path": r.get("filename", "unknown"),
                "line_start": r.get("line_number"),
                "line_end": r.get("line_number"),
                "description": r.get("issue_text", test_name)[:2000],
                "sources": ["bandit"],
                "confidence": _CONFIDENCE_MAP.get(str(r.get("issue_confidence", "")).lower(), "medium"),
            }
        )
    return findings


def parse_gitleaks(raw_json: str) -> list[dict]:
    try:
        data = json.loads(raw_json) if raw_json.strip() else []
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    findings = []
    for r in data:
        description = r.get("Description") or r.get("RuleID") or "Hardcoded secret detected"
        findings.append(
            {
                "category": "hardcoded_secrets",
                "severity": "critical",  # a committed secret is always treated as critical, regardless of rule
                "file_path": r.get("File", "unknown"),
                "line_start": r.get("StartLine"),
                "line_end": r.get("EndLine"),
                "description": description[:2000],
                "sources": ["gitleaks"],
                "confidence": "high",
            }
        )
    return findings


def parse_trivy(raw_json: str) -> list[dict]:
    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError:
        return []
    findings = []
    for result in data.get("Results", []):
        target = result.get("Target", "unknown")
        for vuln in result.get("Vulnerabilities", []) or []:
            findings.append(
                {
                    "category": "vulnerable_dependency",
                    "severity": _SEVERITY_MAP.get(str(vuln.get("Severity", "")).lower(), "medium"),
                    "file_path": target,
                    "line_start": None,
                    "line_end": None,
                    "description": f"{vuln.get('VulnerabilityID', '')}: {vuln.get('Title', '')}"[:2000],
                    "sources": ["trivy"],
                    "confidence": "high",
                }
            )
        for misconfig in result.get("Misconfigurations", []) or []:
            cause = misconfig.get("CauseMetadata", {}) or {}
            findings.append(
                {
                    "category": _classify(misconfig.get("ID", ""), misconfig.get("Title", "")) or "insecure_default_config",
                    "severity": _SEVERITY_MAP.get(str(misconfig.get("Severity", "")).lower(), "medium"),
                    "file_path": target,
                    "line_start": cause.get("StartLine"),
                    "line_end": cause.get("EndLine"),
                    "description": misconfig.get("Message", misconfig.get("Title", ""))[:2000],
                    "sources": ["trivy"],
                    "confidence": "medium",
                }
            )
    return findings


_SEVERITY_RANK = {"critical": 3, "high": 2, "medium": 1, "low": 0}
_CONFIDENCE_RANK = {"high": 2, "medium": 1, "low": 0}


def dedupe(all_findings: list[dict]) -> list[dict]:
    """Merges findings that share (file_path, line_start, category) -
    the same fingerprint two tools corroborating the same real issue at
    the same location would produce - into one row whose `sources` lists
    every tool that flagged it, keeping the higher severity/confidence of
    the merged set."""
    merged: dict[tuple, dict] = {}
    for f in all_findings:
        key = (f["file_path"], f.get("line_start"), f["category"])
        if key not in merged:
            merged[key] = dict(f)
            continue
        existing = merged[key]
        existing["sources"] = sorted(set(existing["sources"]) | set(f["sources"]))
        if _SEVERITY_RANK.get(f["severity"], 1) > _SEVERITY_RANK.get(existing["severity"], 1):
            existing["severity"] = f["severity"]
        if _CONFIDENCE_RANK.get(f["confidence"], 1) > _CONFIDENCE_RANK.get(existing["confidence"], 1):
            existing["confidence"] = f["confidence"]
    return list(merged.values())
