import io

import docx
import pytest

from apps.api.core import storage
from apps.api.core.db import SessionLocal, org_scoped_session
from apps.api.modules.ai_gateway.models import LlmUsageLog
from apps.api.modules.ai_gateway.schemas import GatewayResponse
from apps.api.modules.identity.models import Org, User
from apps.api.modules.policy.models import Policy
from apps.api.modules.tools import service, tasks
from apps.api.modules.tools.models import ApprovedTool, ToolRequest
from apps.api.modules.tools.service import ToolApprovalError, ToolRequestDuplicateError

# Milestone 18 (Request forms) added a 150-word minimum on intended_use_case -
# every test that isn't specifically exercising that validation needs a use
# case long enough to clear it.
SAMPLE_USE_CASE = " ".join(["word"] * 150)
assert len(SAMPLE_USE_CASE.split()) == 150


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


def _make_user(org: Org, email: str, business_role: str = "assure") -> User:
    with org_scoped_session(str(org.id)) as db:
        user = User(org_id=org.id, email=email, business_role=business_role)
        db.add(user)
        db.flush()
        db.refresh(user)
        db.expunge(user)
        return user


def _make_active_policy(org: Org) -> None:
    """Real minimal docx uploaded and approved, so
    policy_service.get_active_policy_text()/has_active_policy() see a
    live policy - needed for any test exercising the AI precheck path,
    which Milestone 10 gates on a policy actually being active."""
    with org_scoped_session(str(org.id)) as db:
        policy = Policy(org_id=org.id, answers={}, status="draft", storage_key="")
        db.add(policy)
        db.flush()
        db.refresh(policy)
        policy_id = str(policy.id)
        storage_key = f"policies/{org.id}/{policy_id}/document.docx"
        policy.storage_key = storage_key
        db.flush()

    doc = docx.Document()
    doc.add_paragraph("Employees may use approved AI tools for coding assistance. Do not paste customer PII into any AI tool.")
    buf = io.BytesIO()
    doc.save(buf)
    storage.upload_bytes(storage_key, buf.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")

    from apps.api.modules.policy import service as policy_service

    with org_scoped_session(str(org.id)) as db:
        existing = db.query(User).filter(User.org_id == org.id).first()
        if existing is not None:
            db.expunge(existing)
    approver = existing if existing is not None else _make_user(org, "policy-approver@example.com", "govern")
    policy_service.approve(org, policy_id, approver)


def _delete_org(org: Org) -> None:
    with org_scoped_session(str(org.id)) as db:
        # tool_request.resulting_tool_id <-> approved_tool.created_from_request_id
        # is a genuine circular FK (each row points at the other), so both
        # sides must be nulled out before either table can be deleted.
        db.query(ToolRequest).filter(ToolRequest.org_id == org.id).update(
            {ToolRequest.resulting_tool_id: None}, synchronize_session=False
        )
        db.query(ApprovedTool).filter(ApprovedTool.org_id == org.id).update(
            {ApprovedTool.created_from_request_id: None}, synchronize_session=False
        )
        db.query(ToolRequest).filter(ToolRequest.org_id == org.id).delete(synchronize_session=False)
        db.query(ApprovedTool).filter(ApprovedTool.org_id == org.id).delete(synchronize_session=False)
        db.query(LlmUsageLog).filter(LlmUsageLog.org_id == org.id).delete(synchronize_session=False)
        db.query(Policy).filter(Policy.org_id == org.id).delete(synchronize_session=False)
        db.query(User).filter(User.org_id == org.id).delete(synchronize_session=False)
    db = SessionLocal()
    try:
        db.query(Org).filter(Org.id == org.id).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def test_parse_assessment_handles_clean_json() -> None:
    classification, rationale = tasks._parse_assessment('{"classification": "Approvable", "rational": "Fine."}')
    assert classification == "approvable"
    assert rationale == "Fine."


def test_parse_assessment_handles_json_wrapped_in_prose() -> None:
    raw = 'Sure, here is my answer:\n{"classification": "Need Review", "rational": "Ambiguous."}\nHope that helps!'
    classification, rationale = tasks._parse_assessment(raw)
    assert classification == "needs_review"
    assert rationale == "Ambiguous."


def test_parse_assessment_normalizes_every_classification_label() -> None:
    assert tasks._parse_assessment('{"classification": "Unapprovable", "explanation": "No."}')[0] == "cannot_approve"
    assert tasks._parse_assessment('{"classification": "cannot approve", "rationale": "No."}')[0] == "cannot_approve"
    assert tasks._parse_assessment('{"classification": "needs review", "explanation": "Hmm."}')[0] == "needs_review"


def test_parse_assessment_raises_on_missing_rationale() -> None:
    with pytest.raises(ValueError):
        tasks._parse_assessment('{"classification": "Approvable"}')


def test_parse_assessment_raises_on_unrecognized_classification() -> None:
    with pytest.raises(ValueError):
        tasks._parse_assessment('{"classification": "Maybe", "rational": "Unclear."}')


def test_parse_assessment_raises_on_garbage() -> None:
    with pytest.raises(ValueError):
        tasks._parse_assessment("not json at all")


def test_create_request_rejects_use_case_under_150_words() -> None:
    org = _make_org("Tools Short Use Case Org")
    try:
        requester = _make_user(org, "requester-short@example.com")
        short_use_case = " ".join(["word"] * 149)
        with pytest.raises(service.ToolRequestValidationError):
            service.create_request(org, requester, "tool", "Short Use Case Tool", "https://example.com/s", short_use_case)
    finally:
        _delete_org(org)


def test_create_request_accepts_use_case_at_exactly_150_words() -> None:
    org = _make_org("Tools Boundary Use Case Org")
    try:
        requester = _make_user(org, "requester-boundary@example.com")
        request = service.create_request(
            org, requester, "tool", "Boundary Tool", "https://example.com/bnd", SAMPLE_USE_CASE
        )
        assert request.intended_use_case == SAMPLE_USE_CASE
    finally:
        _delete_org(org)


def test_create_request_rejects_invalid_data_tier() -> None:
    org = _make_org("Tools Invalid Tier Org")
    try:
        requester = _make_user(org, "requester-badtier@example.com")
        with pytest.raises(service.ToolRequestValidationError):
            service.create_request(
                org, requester, "tool", "Bad Tier Tool", "https://example.com/bt", SAMPLE_USE_CASE,
                data_tiers=["not_a_real_tier"],
            )
    finally:
        _delete_org(org)


def test_create_request_persists_data_tiers_and_enterprise_flag() -> None:
    org = _make_org("Tools New Fields Org")
    try:
        requester = _make_user(org, "requester-newfields@example.com")
        request = service.create_request(
            org, requester, "tool", "New Fields Tool", "https://example.com/nf", SAMPLE_USE_CASE,
            data_tiers=["confidential", "internal"], requires_enterprise_account=True,
        )
        assert request.data_tiers == ["confidential", "internal"]
        assert request.requires_enterprise_account is True
    finally:
        _delete_org(org)


def test_create_request_skips_assessment_without_active_policy() -> None:
    org = _make_org("Tools No Policy Org")
    try:
        requester = _make_user(org, "requester-nopolicy@example.com")
        request = service.create_request(org, requester, "tool", "Unassessed Tool", "https://example.com/np", SAMPLE_USE_CASE)

        assert request.ai_assessment_status == "skipped"
        assert request.ai_assessment_result is None
        assert request.ai_assessment_explanation == service.NO_ACTIVE_POLICY_EXPLANATION
    finally:
        _delete_org(org)


def test_create_request_rejects_normalized_duplicate_name() -> None:
    org = _make_org("Tools Dup Org")
    try:
        requester = _make_user(org, "requester@example.com")
        approver = _make_user(org, "approver@example.com", "govern")
        request = service.create_request(org, requester, "tool", "Claude", "https://claude.ai", SAMPLE_USE_CASE)
        service.approve_request(org, str(request.id), approver, description="AI assistant", allowed_tiers=["public"])

        with pytest.raises(ToolRequestDuplicateError):
            service.create_request(org, requester, "tool", "  claude  ", "https://claude.ai/other", SAMPLE_USE_CASE)
    finally:
        _delete_org(org)


def test_approve_request_rejects_self_approval() -> None:
    org = _make_org("Tools Self Approve Org")
    try:
        requester = _make_user(org, "requester2@example.com")
        request = service.create_request(org, requester, "tool", "Some Tool", "https://example.com", SAMPLE_USE_CASE)

        with pytest.raises(ToolApprovalError):
            service.approve_request(org, str(request.id), requester, description="x", allowed_tiers=["public"])
    finally:
        _delete_org(org)


def test_approve_request_rejects_non_pending_request() -> None:
    org = _make_org("Tools Non Pending Org")
    try:
        requester = _make_user(org, "requester3@example.com")
        approver = _make_user(org, "approver3@example.com", "govern")
        request = service.create_request(org, requester, "tool", "Some Tool 2", "https://example.com/2", SAMPLE_USE_CASE)
        service.approve_request(org, str(request.id), approver, description="x", allowed_tiers=["public"])

        with pytest.raises(ToolApprovalError):
            service.approve_request(org, str(request.id), approver, description="x", allowed_tiers=["public"])
    finally:
        _delete_org(org)


@pytest.mark.parametrize("request_type", ["tool", "feature", "webextension"])
def test_approve_request_creates_catalog_entry_for_every_request_type(request_type: str) -> None:
    org = _make_org(f"Tools Catalog Org {request_type}")
    try:
        requester = _make_user(org, f"requester-{request_type}@example.com")
        approver = _make_user(org, f"approver-{request_type}@example.com", "govern")
        request = service.create_request(
            org, requester, request_type, f"Thing ({request_type})", "https://example.com/x", SAMPLE_USE_CASE
        )
        approved = service.approve_request(
            org, str(request.id), approver, description="one-liner", allowed_tiers=["public", "internal"]
        )
        assert approved.status == "approved"
        assert approved.resulting_tool_id is not None

        catalog = service.list_approved_tools(org)
        assert len(catalog) == 1
        assert catalog[0].source_type == request_type
        assert catalog[0].allowed_tiers == ["public", "internal"]
    finally:
        _delete_org(org)


def test_reject_request_happy_path() -> None:
    org = _make_org("Tools Reject Org")
    try:
        requester = _make_user(org, "requester4@example.com")
        approver = _make_user(org, "approver4@example.com", "govern")
        request = service.create_request(org, requester, "tool", "Rejected Tool", "https://example.com/r", SAMPLE_USE_CASE)

        rejected = service.reject_request(org, str(request.id), approver, reason="not needed")
        assert rejected.status == "rejected"
        assert rejected.decision_note == "not needed"
        assert service.list_approved_tools(org) == []
    finally:
        _delete_org(org)


def test_update_and_delete_approved_tool_direct_curation() -> None:
    org = _make_org("Tools Manage Org")
    try:
        requester = _make_user(org, "requester7@example.com")
        approver = _make_user(org, "approver7@example.com", "govern")
        request = service.create_request(org, requester, "tool", "Curated Tool", "https://example.com/c", SAMPLE_USE_CASE)
        approved = service.approve_request(org, str(request.id), approver, description="orig", allowed_tiers=["public"])
        tool_id = str(approved.resulting_tool_id)

        updated = service.update_approved_tool(
            org, tool_id, name="Curated Tool v2", description="edited", access_url="https://example.com/c2",
            allowed_tiers=["internal", "public"],
        )
        assert updated is not None
        assert updated.name == "Curated Tool v2"
        assert updated.allowed_tiers == ["internal", "public"]

        assert service.delete_approved_tool(org, tool_id) is True
        assert service.list_approved_tools(org) == []
    finally:
        _delete_org(org)


def test_update_approved_tool_sets_and_clears_logo_url() -> None:
    org = _make_org("Tools Logo URL Org")
    try:
        requester = _make_user(org, "requester-logo-url@example.com")
        approver = _make_user(org, "approver-logo-url@example.com", "govern")
        request = service.create_request(org, requester, "tool", "Logo Tool", "https://example.com/logo", SAMPLE_USE_CASE)
        approved = service.approve_request(org, str(request.id), approver, description="d", allowed_tiers=[])
        tool_id = str(approved.resulting_tool_id)

        updated = service.update_approved_tool(
            org, tool_id, name="Logo Tool", description="d", access_url="https://example.com/logo",
            allowed_tiers=[], logo_url="https://cdn.example.com/logo.png",
        )
        assert updated.logo_url == "https://cdn.example.com/logo.png"

        cleared = service.update_approved_tool(
            org, tool_id, name="Logo Tool", description="d", access_url="https://example.com/logo",
            allowed_tiers=[], logo_url=None,
        )
        assert cleared.logo_url is None
    finally:
        _delete_org(org)


def test_upload_tool_logo_round_trips_bytes_and_content_type() -> None:
    org = _make_org("Tools Logo Upload Org")
    try:
        requester = _make_user(org, "requester-logo-upload@example.com")
        approver = _make_user(org, "approver-logo-upload@example.com", "govern")
        request = service.create_request(org, requester, "tool", "Upload Logo Tool", "https://example.com/u", SAMPLE_USE_CASE)
        approved = service.approve_request(org, str(request.id), approver, description="d", allowed_tiers=[])
        tool_id = str(approved.resulting_tool_id)

        png_bytes = b"\x89PNG\r\n\x1a\nfake-but-good-enough-for-a-storage-round-trip-test"
        updated = service.upload_tool_logo(org, tool_id, "image/png", png_bytes)
        assert updated is not None
        assert updated.logo_url == f"/tools/approved/{tool_id}/logo-file"

        data, content_type = service.get_tool_logo_bytes(org, tool_id)
        assert data == png_bytes
        assert content_type == "image/png"
    finally:
        _delete_org(org)


def test_assess_tool_request_fails_safe_on_non_json_mock_response(monkeypatch) -> None:
    """The mock provider's canned text isn't JSON, so the task must land on
    ai_assessment_status="failed" and MUST NOT set ai_assessment_result -
    proving a broken/unparseable assessment can never look like an
    approval."""
    monkeypatch.setattr("apps.api.modules.ai_gateway.service.settings.ai_provider", "mock")
    org = _make_org("Tools Assess Fail Org")
    try:
        _make_active_policy(org)
        requester = _make_user(org, "requester5@example.com")
        request = service.create_request(org, requester, "tool", "Assessed Tool", "https://example.com/a", SAMPLE_USE_CASE)

        tasks.assess_tool_request(str(request.id), str(org.id))

        refreshed = service.get_request(org, str(request.id))
        assert refreshed.ai_assessment_status == "failed"
        assert refreshed.ai_assessment_result is None
    finally:
        _delete_org(org)


def test_assess_tool_request_parses_valid_json_response(monkeypatch) -> None:
    org = _make_org("Tools Assess Happy Org")
    try:
        _make_active_policy(org)
        requester = _make_user(org, "requester6@example.com")
        request = service.create_request(org, requester, "tool", "Assessed Tool 2", "https://example.com/b", SAMPLE_USE_CASE)

        def _fake_complete(feature, org_arg, prompt, system=None):
            return GatewayResponse(
                content='{"classification": "approvable", "explanation": "Looks fine."}',
                provider="mock",
                model="mock-echo-1",
                prompt_tokens=1,
                completion_tokens=1,
                cost_usd=0.0,
            )

        monkeypatch.setattr("apps.api.modules.tools.tasks.ai_gateway_service.complete", _fake_complete)

        tasks.assess_tool_request(str(request.id), str(org.id))

        refreshed = service.get_request(org, str(request.id))
        assert refreshed.ai_assessment_status == "complete"
        assert refreshed.ai_assessment_result == "approvable"
        assert refreshed.ai_assessment_explanation == "Looks fine."
    finally:
        _delete_org(org)
