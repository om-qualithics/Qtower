import uuid

from apps.api.modules.authz.service import can
from apps.api.modules.identity.models import User


def _user(business_role: str, system_role: str) -> User:
    return User(
        id=uuid.uuid4(),
        org_id=uuid.uuid4(),
        email="test@example.com",
        business_role=business_role,
        system_role=system_role,
    )


def test_view_self_allowed_for_any_authenticated_user() -> None:
    assert can(_user("operator", "user"), "identity.view_self")
    assert can(_user("govern", "super_admin"), "identity.view_self")


def test_manage_sso_requires_admin_system_role() -> None:
    assert not can(_user("operator", "user"), "identity.manage_sso")
    assert can(_user("operator", "admin"), "identity.manage_sso")
    assert can(_user("operator", "super_admin"), "identity.manage_sso")


def test_approve_tool_request_requires_govern_or_assure_business_role() -> None:
    assert not can(_user("operator", "admin"), "tools.approve_request")
    assert can(_user("govern", "user"), "tools.approve_request")
    assert can(_user("assure", "user"), "tools.approve_request")


def test_unknown_action_is_denied_by_default() -> None:
    assert not can(_user("govern", "super_admin"), "nonexistent.action")


def test_policy_manage_allows_govern_assure_or_system_admin() -> None:
    assert can(_user("govern", "user"), "policy.manage")
    assert can(_user("assure", "user"), "policy.manage")
    assert can(_user("operator", "admin"), "policy.manage")
    assert can(_user("operator", "super_admin"), "policy.manage")
    assert not can(_user("operator", "user"), "policy.manage")


def test_policy_approve_is_stricter_than_manage_assure_cannot_approve() -> None:
    assert can(_user("govern", "user"), "policy.approve")
    assert can(_user("operator", "admin"), "policy.approve")
    assert can(_user("operator", "super_admin"), "policy.approve")
    assert not can(_user("assure", "user"), "policy.approve")
    assert not can(_user("operator", "user"), "policy.approve")
