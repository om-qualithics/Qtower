from apps.api.core.db import SessionLocal, org_scoped_session
from apps.api.modules.dashboard import service as dashboard_service
from apps.api.modules.escalations import service as escalations_service
from apps.api.modules.escalations.models import Escalation
from apps.api.modules.identity.models import Org, User
from apps.api.modules.policy.models import Policy
from apps.api.modules.tools import service as tools_service
from apps.api.modules.tools.models import ApprovedTool, ToolRequest


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


def _make_user(org: Org, email: str, business_role: str = "operator") -> User:
    with org_scoped_session(str(org.id)) as db:
        user = User(org_id=org.id, email=email, business_role=business_role)
        db.add(user)
        db.flush()
        db.refresh(user)
        db.expunge(user)
        return user


def _delete_org(org: Org) -> None:
    with org_scoped_session(str(org.id)) as db:
        db.query(ToolRequest).filter(ToolRequest.org_id == org.id).update(
            {ToolRequest.resulting_tool_id: None}, synchronize_session=False
        )
        db.query(ApprovedTool).filter(ApprovedTool.org_id == org.id).update(
            {ApprovedTool.created_from_request_id: None}, synchronize_session=False
        )
        db.query(ToolRequest).filter(ToolRequest.org_id == org.id).delete(synchronize_session=False)
        db.query(ApprovedTool).filter(ApprovedTool.org_id == org.id).delete(synchronize_session=False)
        db.query(Escalation).filter(Escalation.org_id == org.id).delete(synchronize_session=False)
        db.query(Policy).filter(Policy.org_id == org.id).delete(synchronize_session=False)
        db.query(User).filter(User.org_id == org.id).delete(synchronize_session=False)
    db = SessionLocal()
    try:
        db.query(Org).filter(Org.id == org.id).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def test_get_summary_role_gating() -> None:
    org = _make_org("Dashboard Test Org")
    try:
        operator = _make_user(org, "operator@example.com", "operator")
        assure = _make_user(org, "assure@example.com", "assure")
        govern = _make_user(org, "govern@example.com", "govern")

        tools_service.create_request(
            org, operator, "tool", "Some Tool", "https://example.com", " ".join(["word"] * 150)
        )
        escalations_service.create_escalation(org, "other", "Something felt off")

        with org_scoped_session(str(org.id)) as db:
            draft = Policy(org_id=org.id, answers={}, status="draft", storage_key="policies/x/y/document.docx", created_by=assure.id)
            db.add(draft)
            db.flush()

        operator_summary = dashboard_service.get_summary(org, operator)
        assert operator_summary.pending_tool_requests == []
        assert operator_summary.pending_policy_drafts == []
        assert operator_summary.tool_request_counts == {}
        assert operator_summary.training_summary is None
        assert len(operator_summary.my_tool_requests) == 1
        assert not hasattr(operator_summary, "my_alerts")  # anonymous - no per-user alerts field exists at all

        assure_summary = dashboard_service.get_summary(org, assure)
        assert len(assure_summary.pending_tool_requests) == 1
        assert assure_summary.tool_request_counts.get("pending") == 1
        assert assure_summary.pending_policy_drafts == []  # policy.approve is govern-only
        assert len(assure_summary.my_policy_drafts) == 1
        assert assure_summary.training_summary is not None

        govern_summary = dashboard_service.get_summary(org, govern)
        assert len(govern_summary.pending_tool_requests) == 1
        assert len(govern_summary.pending_policy_drafts) == 1
        assert govern_summary.my_tool_requests == []
        assert govern_summary.my_policy_drafts == []
    finally:
        _delete_org(org)
