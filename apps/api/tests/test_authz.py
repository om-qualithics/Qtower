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


def test_manage_users_requires_admin_system_role() -> None:
    assert not can(_user("govern", "user"), "identity.manage_users")
    assert can(_user("operator", "admin"), "identity.manage_users")
    assert can(_user("operator", "super_admin"), "identity.manage_users")


def test_manage_sso_requires_admin_system_role() -> None:
    assert not can(_user("operator", "user"), "identity.manage_sso")
    assert can(_user("operator", "admin"), "identity.manage_sso")
    assert can(_user("operator", "super_admin"), "identity.manage_sso")


def test_tools_view_allowed_for_any_authenticated_user() -> None:
    assert can(_user("operator", "user"), "tools.view")
    assert can(_user("govern", "super_admin"), "tools.view")


def test_tools_request_allows_govern_assure_operator_or_system_admin() -> None:
    assert can(_user("govern", "user"), "tools.request")
    assert can(_user("assure", "user"), "tools.request")
    assert can(_user("operator", "user"), "tools.request")
    assert can(_user("operator", "admin"), "tools.request")


def test_tools_approve_requires_govern_assure_or_system_admin() -> None:
    assert not can(_user("operator", "user"), "tools.approve")
    assert can(_user("govern", "user"), "tools.approve")
    assert can(_user("assure", "user"), "tools.approve")
    assert can(_user("operator", "admin"), "tools.approve")


def test_tools_manage_requires_govern_assure_or_system_admin() -> None:
    assert not can(_user("operator", "user"), "tools.manage")
    assert can(_user("govern", "user"), "tools.manage")
    assert can(_user("assure", "user"), "tools.manage")
    assert can(_user("operator", "super_admin"), "tools.manage")


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


def test_escalations_create_allowed_for_any_authenticated_user() -> None:
    assert can(_user("operator", "user"), "escalations.create")
    assert can(_user("govern", "super_admin"), "escalations.create")
    assert can(_user("operator", "user"), "escalations.view")
    assert can(_user("govern", "super_admin"), "escalations.view")


def test_escalations_manage_requires_govern_assure_or_system_admin() -> None:
    assert not can(_user("operator", "user"), "escalations.manage")
    assert can(_user("govern", "user"), "escalations.manage")
    assert can(_user("assure", "user"), "escalations.manage")
    assert can(_user("operator", "admin"), "escalations.manage")


def test_training_view_allowed_for_any_authenticated_user() -> None:
    assert can(_user("operator", "user"), "training.view")
    assert can(_user("govern", "super_admin"), "training.view")


def test_training_manage_requires_govern_assure_or_system_admin() -> None:
    assert not can(_user("operator", "user"), "training.manage")
    assert can(_user("govern", "user"), "training.manage")
    assert can(_user("assure", "user"), "training.manage")
    assert can(_user("operator", "admin"), "training.manage")


def test_dashboard_view_allowed_for_any_authenticated_user() -> None:
    assert can(_user("operator", "user"), "dashboard.view")
    assert can(_user("govern", "super_admin"), "dashboard.view")


def test_codescan_connect_is_assure_only_not_govern() -> None:
    """Deliberate deviation from every other "manage"-style permission in
    this matrix (which is always {govern, assure}) - explicit instruction
    for Milestone 13, asserted here so a future edit that "fixes" this
    back to the usual shape gets caught."""
    assert can(_user("assure", "user"), "codescan.connect")
    assert not can(_user("govern", "user"), "codescan.connect")
    assert not can(_user("operator", "user"), "codescan.connect")
    assert can(_user("operator", "admin"), "codescan.connect")


def test_codescan_run_and_view_allowed_for_any_authenticated_user() -> None:
    for action in ("codescan.run", "codescan.view"):
        assert can(_user("govern", "user"), action)
        assert can(_user("assure", "user"), action)
        assert can(_user("operator", "user"), action)
