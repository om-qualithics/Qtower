import pytest

from apps.api.core.crypto import decrypt_secret, encrypt_secret
from apps.api.core.db import SessionLocal, org_scoped_session
from apps.api.modules.codescan import github_client, service
from apps.api.modules.codescan.models import GithubConnection
from apps.api.modules.codescan.parsers import dedupe, parse_bandit, parse_gitleaks, parse_semgrep, parse_trivy
from apps.api.modules.codescan.service import CodescanConnectionError, CodescanValidationError
from apps.api.modules.identity.models import Org, User


def _make_org(name: str) -> Org:
    db = SessionLocal()
    try:
        org = Org(name=name)
        db.add(org)
        db.commit()
        db.refresh(org)
        return org
    finally:
        db.close()


def _make_user(org: Org, email: str, business_role: str = "assure", system_role: str = "user") -> User:
    with org_scoped_session(str(org.id)) as db:
        user = User(org_id=org.id, email=email, business_role=business_role, system_role=system_role)
        db.add(user)
        db.flush()
        db.refresh(user)
        db.expunge(user)
        return user


def _delete_org(org: Org) -> None:
    with org_scoped_session(str(org.id)) as db:
        db.query(GithubConnection).filter(GithubConnection.org_id == org.id).delete(synchronize_session=False)
        db.query(User).filter(User.org_id == org.id).delete(synchronize_session=False)
    db = SessionLocal()
    try:
        db.query(Org).filter(Org.id == org.id).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def test_encrypt_decrypt_round_trip() -> None:
    ciphertext = encrypt_secret("-----BEGIN PRIVATE KEY-----\nfake\n-----END PRIVATE KEY-----")
    assert ciphertext != "-----BEGIN PRIVATE KEY-----\nfake\n-----END PRIVATE KEY-----"
    assert decrypt_secret(ciphertext) == "-----BEGIN PRIVATE KEY-----\nfake\n-----END PRIVATE KEY-----"


def test_create_github_connection_validates_against_the_real_api(monkeypatch) -> None:
    org = _make_org("Codescan Connect Org")
    try:
        user = _make_user(org, "assure@example.com")
        monkeypatch.setattr(
            "apps.api.modules.codescan.service.github_client.mint_installation_token", lambda *a, **k: "fake-token"
        )
        monkeypatch.setattr(
            "apps.api.modules.codescan.service.github_client.list_repositories",
            lambda token: [{"full_name": "acme/backend", "owner": {"login": "acme"}}],
        )
        connection = service.create_github_connection(org, user, "12345", "fake-pem", "67890")
        assert connection.account_login == "acme"
        assert connection.private_key_encrypted != "fake-pem"
        assert decrypt_secret(connection.private_key_encrypted) == "fake-pem"
    finally:
        _delete_org(org)


def test_create_github_connection_rejects_bad_credentials(monkeypatch) -> None:
    org = _make_org("Codescan Connect Reject Org")
    try:
        user = _make_user(org, "assure2@example.com")

        def _raise(*a, **k):
            raise github_client.GithubClientError("bad app id")

        monkeypatch.setattr("apps.api.modules.codescan.service.github_client.mint_installation_token", _raise)
        with pytest.raises(CodescanConnectionError):
            service.create_github_connection(org, user, "bad", "bad", "bad")
    finally:
        _delete_org(org)


def test_create_github_connection_rejects_missing_fields() -> None:
    org = _make_org("Codescan Connect Missing Org")
    try:
        user = _make_user(org, "assure3@example.com")
        with pytest.raises(CodescanValidationError):
            service.create_github_connection(org, user, "", "key", "123")
    finally:
        _delete_org(org)


def test_create_github_connection_replaces_existing(monkeypatch) -> None:
    org = _make_org("Codescan Connect Replace Org")
    try:
        user = _make_user(org, "assure4@example.com")
        monkeypatch.setattr(
            "apps.api.modules.codescan.service.github_client.mint_installation_token", lambda *a, **k: "tok"
        )
        monkeypatch.setattr(
            "apps.api.modules.codescan.service.github_client.list_repositories",
            lambda token: [{"full_name": "acme/repo1", "owner": {"login": "acme"}}],
        )
        service.create_github_connection(org, user, "111", "key1", "aaa")
        service.create_github_connection(org, user, "222", "key2", "bbb")

        with org_scoped_session(str(org.id)) as db:
            rows = db.query(GithubConnection).filter(GithubConnection.org_id == org.id).all()
            assert len(rows) == 1
            assert rows[0].app_id == "222"
    finally:
        _delete_org(org)


def test_parse_semgrep_maps_sql_injection() -> None:
    raw = """
    {"results": [{"check_id": "python.django.security.sql-injection", "path": "app.py",
      "start": {"line": 10}, "end": {"line": 10},
      "extra": {"message": "possible sql injection", "severity": "ERROR", "metadata": {"confidence": "HIGH"}}}]}
    """
    findings = parse_semgrep(raw)
    assert len(findings) == 1
    assert findings[0]["category"] == "sql_injection"
    assert findings[0]["severity"] == "high"
    assert findings[0]["confidence"] == "high"
    assert findings[0]["sources"] == ["semgrep"]


def test_parse_bandit_maps_hardcoded_secret() -> None:
    raw = """
    {"results": [{"test_name": "hardcoded_password_string", "filename": "config.py", "line_number": 5,
      "issue_severity": "HIGH", "issue_confidence": "MEDIUM", "issue_text": "hardcoded password found"}]}
    """
    findings = parse_bandit(raw)
    assert len(findings) == 1
    assert findings[0]["category"] == "hardcoded_secrets"
    assert findings[0]["severity"] == "high"
    assert findings[0]["sources"] == ["bandit"]


def test_parse_gitleaks_is_always_critical() -> None:
    raw = '[{"Description": "AWS key", "File": ".env", "StartLine": 1, "EndLine": 1, "RuleID": "aws-key"}]'
    findings = parse_gitleaks(raw)
    assert len(findings) == 1
    assert findings[0]["category"] == "hardcoded_secrets"
    assert findings[0]["severity"] == "critical"


def test_parse_trivy_maps_vulnerable_dependency() -> None:
    raw = """
    {"Results": [{"Target": "requirements.txt", "Vulnerabilities": [
      {"VulnerabilityID": "CVE-2024-1234", "Severity": "CRITICAL", "Title": "bad thing"}]}]}
    """
    findings = parse_trivy(raw)
    assert len(findings) == 1
    assert findings[0]["category"] == "vulnerable_dependency"
    assert findings[0]["severity"] == "critical"


def test_dedupe_merges_overlapping_findings() -> None:
    findings = [
        {"category": "sql_injection", "severity": "medium", "file_path": "app.py", "line_start": 10,
         "line_end": 10, "description": "a", "sources": ["semgrep"], "confidence": "low"},
        {"category": "sql_injection", "severity": "high", "file_path": "app.py", "line_start": 10,
         "line_end": 10, "description": "b", "sources": ["bandit"], "confidence": "high"},
    ]
    merged = dedupe(findings)
    assert len(merged) == 1
    assert set(merged[0]["sources"]) == {"semgrep", "bandit"}
    assert merged[0]["severity"] == "high"
    assert merged[0]["confidence"] == "high"


def test_dedupe_keeps_distinct_findings_separate() -> None:
    findings = [
        {"category": "sql_injection", "severity": "high", "file_path": "app.py", "line_start": 10,
         "line_end": 10, "description": "a", "sources": ["semgrep"], "confidence": "high"},
        {"category": "xss", "severity": "high", "file_path": "app.py", "line_start": 10,
         "line_end": 10, "description": "b", "sources": ["semgrep"], "confidence": "high"},
    ]
    assert len(dedupe(findings)) == 2
