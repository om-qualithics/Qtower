import io

import docx

from apps.api.core import storage
from apps.api.core.db import SessionLocal, org_scoped_session
from apps.api.modules.ai_gateway.models import LlmUsageLog
from apps.api.modules.identity.models import Org, User
from apps.api.modules.policy.models import Policy
from apps.api.modules.projects import service, tasks
from apps.api.modules.projects.models import Project, ProjectRequest, ProjectToolLink, ProjectVendorLink
from apps.api.modules.projects.service import ProjectApprovalError, ProjectValidationError
from apps.api.modules.tools.models import ApprovedTool, ToolRequest
from apps.api.modules.vendors.models import Vendor, VendorChecklistResponse, VendorRequest, VendorRequestChecklistResponse
from apps.api.modules.ai_gateway.schemas import GatewayResponse


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


def _make_active_policy(org: Org, approver: User) -> None:
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
    doc.add_paragraph("Employees may use approved AI tools for coding assistance.")
    buf = io.BytesIO()
    doc.save(buf)
    storage.upload_bytes(
        storage_key, buf.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )

    from apps.api.modules.policy import service as policy_service

    policy_service.approve(org, policy_id, approver)


def _make_approved_tool(org: Org, name: str = "Approved Tool") -> ApprovedTool:
    with org_scoped_session(str(org.id)) as db:
        tool = ApprovedTool(org_id=org.id, name=name, description="d", access_url="https://x", allowed_tiers=[])
        db.add(tool)
        db.flush()
        db.refresh(tool)
        db.expunge(tool)
        return tool


def _make_vendor(org: Org, name: str = "Approved Vendor") -> Vendor:
    with org_scoped_session(str(org.id)) as db:
        vendor = Vendor(org_id=org.id, name=name, type="commercial")
        db.add(vendor)
        db.flush()
        db.refresh(vendor)
        db.expunge(vendor)
        return vendor


def _delete_org(org: Org) -> None:
    with org_scoped_session(str(org.id)) as db:
        db.query(ProjectRequest).filter(ProjectRequest.org_id == org.id).update(
            {ProjectRequest.resulting_project_id: None}, synchronize_session=False
        )
        db.query(Project).filter(Project.org_id == org.id).update(
            {Project.created_from_request_id: None}, synchronize_session=False
        )
        db.query(ProjectToolLink).filter(ProjectToolLink.org_id == org.id).delete(synchronize_session=False)
        db.query(ProjectVendorLink).filter(ProjectVendorLink.org_id == org.id).delete(synchronize_session=False)
        db.query(ProjectRequest).filter(ProjectRequest.org_id == org.id).delete(synchronize_session=False)
        db.query(Project).filter(Project.org_id == org.id).delete(synchronize_session=False)

        db.query(VendorRequest).filter(VendorRequest.org_id == org.id).update(
            {VendorRequest.resulting_vendor_id: None}, synchronize_session=False
        )
        db.query(Vendor).filter(Vendor.org_id == org.id).update(
            {Vendor.created_from_request_id: None}, synchronize_session=False
        )
        db.query(VendorChecklistResponse).filter(VendorChecklistResponse.org_id == org.id).delete(
            synchronize_session=False
        )
        db.query(VendorRequestChecklistResponse).filter(VendorRequestChecklistResponse.org_id == org.id).delete(
            synchronize_session=False
        )
        db.query(VendorRequest).filter(VendorRequest.org_id == org.id).delete(synchronize_session=False)
        db.query(Vendor).filter(Vendor.org_id == org.id).delete(synchronize_session=False)

        db.query(ToolRequest).filter(ToolRequest.org_id == org.id).update(
            {ToolRequest.resulting_tool_id: None}, synchronize_session=False
        )
        db.query(ApprovedTool).filter(ApprovedTool.org_id == org.id).update(
            {ApprovedTool.created_from_request_id: None}, synchronize_session=False
        )
        db.query(ToolRequest).filter(ToolRequest.org_id == org.id).delete(synchronize_session=False)
        db.query(ApprovedTool).filter(ApprovedTool.org_id == org.id).delete(synchronize_session=False)

        db.query(Policy).filter(Policy.org_id == org.id).delete(synchronize_session=False)
        db.query(LlmUsageLog).filter(LlmUsageLog.org_id == org.id).delete(synchronize_session=False)

        db.query(User).filter(User.org_id == org.id).delete(synchronize_session=False)
    db = SessionLocal()
    try:
        db.query(Org).filter(Org.id == org.id).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def test_create_project_request_with_zero_links_succeeds() -> None:
    org = _make_org("Projects Zero Links Org")
    try:
        requester = _make_user(org, "requester-zero@example.com")
        request = service.create_project_request(
            org, requester, "Support Bot", "An internal support bot", "saves time", "no PII", False
        )
        assert request.status == "pending"
        assert request.project_assessment_status == "skipped"  # no active policy
    finally:
        _delete_org(org)


def test_create_project_request_rejects_invalid_data_tier() -> None:
    org = _make_org("Projects Invalid Tier Org")
    try:
        requester = _make_user(org, "requester-badtier@example.com")
        try:
            service.create_project_request(
                org, requester, "X", "d", "j", "f", False, data_tiers=["not_a_real_tier"]
            )
            assert False, "expected ProjectValidationError"
        except ProjectValidationError:
            pass
    finally:
        _delete_org(org)


def test_create_project_request_persists_data_tiers() -> None:
    org = _make_org("Projects Data Tiers Org")
    try:
        requester = _make_user(org, "requester-tiers@example.com")
        request = service.create_project_request(
            org, requester, "Tiered Project", "d", "j", "f", False, data_tiers=["restricted", "public"]
        )
        assert request.data_tiers == ["restricted", "public"]
    finally:
        _delete_org(org)


def test_create_project_request_rejects_link_with_both_id_and_other_name() -> None:
    org = _make_org("Projects Bad Link Org")
    try:
        requester = _make_user(org, "requester-badlink@example.com")
        tool = _make_approved_tool(org)
        try:
            service.create_project_request(
                org, requester, "X", "d", "j", "f", False,
                tool_links=[{"tool_id": str(tool.id), "other_name": "Also Named"}],
            )
            assert False, "expected ProjectValidationError"
        except ProjectValidationError:
            pass
    finally:
        _delete_org(org)


def test_create_project_request_rejects_unknown_tool_id() -> None:
    org = _make_org("Projects Unknown Tool Org")
    try:
        requester = _make_user(org, "requester-unknown@example.com")
        try:
            service.create_project_request(
                org, requester, "X", "d", "j", "f", False,
                tool_links=[{"tool_id": "00000000-0000-0000-0000-000000000000"}],
            )
            assert False, "expected ProjectValidationError"
        except ProjectValidationError:
            pass
    finally:
        _delete_org(org)


def test_create_project_request_accepts_registered_and_other_links() -> None:
    org = _make_org("Projects Mixed Links Org")
    try:
        requester = _make_user(org, "requester-mixed@example.com")
        tool = _make_approved_tool(org)
        vendor = _make_vendor(org)
        request = service.create_project_request(
            org, requester, "Mixed Project", "d", "j", "f", True,
            tool_links=[{"tool_id": str(tool.id)}, {"other_name": "Unlisted Tool"}],
            vendor_links=[{"vendor_id": str(vendor.id)}],
        )
        tool_links = service.get_request_tool_links(org, str(request.id))
        vendor_links = service.get_request_vendor_links(org, str(request.id))
        assert len(tool_links) == 2
        assert sum(1 for link in tool_links if link.tool_id is not None) == 1
        assert sum(1 for link in tool_links if link.other_name == "Unlisted Tool") == 1
        assert len(vendor_links) == 1
        assert vendor_links[0].vendor_id == vendor.id
    finally:
        _delete_org(org)


def test_approve_project_request_rejects_self_approval() -> None:
    org = _make_org("Projects Self Approve Org")
    try:
        requester = _make_user(org, "requester-self@example.com")
        request = service.create_project_request(org, requester, "X", "d", "j", "f", False)
        try:
            service.approve_project_request(org, str(request.id), requester)
            assert False, "expected ProjectApprovalError"
        except ProjectApprovalError as exc:
            assert "own request" in str(exc)
    finally:
        _delete_org(org)


def test_approve_project_request_copies_links_to_new_project() -> None:
    org = _make_org("Projects Copy Links Org")
    try:
        requester = _make_user(org, "requester-copy@example.com")
        approver = _make_user(org, "approver-copy@example.com", "govern")
        tool = _make_approved_tool(org)
        request = service.create_project_request(
            org, requester, "Copy Project", "d", "j", "f", False,
            tool_links=[{"tool_id": str(tool.id)}, {"other_name": "Shadow Tool"}],
        )
        approved = service.approve_project_request(org, str(request.id), approver)
        assert approved.status == "approved"
        project_id = str(approved.resulting_project_id)

        project_links = service.get_project_tool_links(org, project_id)
        assert len(project_links) == 2
        assert sum(1 for link in project_links if link.tool_id == tool.id) == 1
        assert sum(1 for link in project_links if link.other_name == "Shadow Tool") == 1

        # Original request links stay in place as a record of what was
        # originally submitted (copy, not move).
        request_links = service.get_request_tool_links(org, str(request.id))
        assert len(request_links) == 2
    finally:
        _delete_org(org)


def test_delete_project_nulls_both_sides_of_circular_fk() -> None:
    org = _make_org("Projects Delete Org")
    try:
        requester = _make_user(org, "requester-delete@example.com")
        approver = _make_user(org, "approver-delete@example.com", "govern")
        request = service.create_project_request(org, requester, "Doomed", "d", "j", "f", False)
        approved = service.approve_project_request(org, str(request.id), approver)
        project_id = str(approved.resulting_project_id)

        deleted = service.delete_project(org, project_id)
        assert deleted is True

        with org_scoped_session(str(org.id)) as db:
            assert db.get(Project, approved.resulting_project_id) is None
            surviving_request = db.get(ProjectRequest, request.id)
            assert surviving_request is not None
            assert surviving_request.resulting_project_id is None
    finally:
        _delete_org(org)


def test_has_active_policy_gate_skips_assessment_with_no_active_policy() -> None:
    org = _make_org("Projects No Policy Org")
    try:
        requester = _make_user(org, "requester-nopolicy@example.com")
        request = service.create_project_request(org, requester, "X", "d", "j", "f", False)
        assert request.project_assessment_status == "skipped"
        assert request.project_assessment_result is None
    finally:
        _delete_org(org)


def test_assess_project_request_fails_safe_on_non_json_mock_response(monkeypatch) -> None:
    monkeypatch.setattr("apps.api.modules.ai_gateway.service.settings.ai_provider", "mock")
    org = _make_org("Projects Assess Fail Org")
    try:
        approver = _make_user(org, "policy-approver-fail@example.com", "govern")
        _make_active_policy(org, approver)
        requester = _make_user(org, "requester-assess-fail@example.com")
        request = service.create_project_request(org, requester, "Assessed", "d", "j", "f", False)
        assert request.project_assessment_status == "pending"

        tasks.assess_project_request(str(request.id), str(org.id))

        refreshed = service.get_project_request(org, str(request.id))
        assert refreshed.project_assessment_status == "failed"
        assert refreshed.project_assessment_result is None
    finally:
        _delete_org(org)


def test_assess_project_request_parses_valid_json_response(monkeypatch) -> None:
    org = _make_org("Projects Assess Happy Org")
    try:
        approver = _make_user(org, "policy-approver-happy@example.com", "govern")
        _make_active_policy(org, approver)
        requester = _make_user(org, "requester-assess-happy@example.com")
        request = service.create_project_request(org, requester, "Assessed 2", "d", "j", "f", False)

        def _fake_complete(feature, org_arg, prompt, system=None):
            return GatewayResponse(
                content='{"classification": "needs review", "rational": "Uses sensitive data."}',
                provider="mock",
                model="mock-echo-1",
                prompt_tokens=1,
                completion_tokens=1,
                cost_usd=0.0,
            )

        monkeypatch.setattr("apps.api.modules.projects.tasks.ai_gateway_service.complete", _fake_complete)

        tasks.assess_project_request(str(request.id), str(org.id))

        refreshed = service.get_project_request(org, str(request.id))
        assert refreshed.project_assessment_status == "complete"
        assert refreshed.project_assessment_result == "needs_review"
        assert refreshed.project_assessment_explanation == "Uses sensitive data."
    finally:
        _delete_org(org)
