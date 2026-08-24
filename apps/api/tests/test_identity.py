import pytest

from apps.api.core.db import SessionLocal, org_scoped_session
from apps.api.modules.identity import service
from apps.api.modules.identity.models import Org, User
from apps.api.modules.identity.service import IdentityValidationError


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


def _make_user(org: Org, email: str, business_role: str = "operator", system_role: str = "user") -> User:
    with org_scoped_session(str(org.id)) as db:
        user = User(org_id=org.id, email=email, business_role=business_role, system_role=system_role)
        db.add(user)
        db.flush()
        db.refresh(user)
        db.expunge(user)
        return user


def _delete_org(org: Org) -> None:
    with org_scoped_session(str(org.id)) as db:
        db.query(User).filter(User.org_id == org.id).delete(synchronize_session=False)
    db = SessionLocal()
    try:
        db.query(Org).filter(Org.id == org.id).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def test_list_org_users() -> None:
    org = _make_org("List Users Org")
    try:
        _make_user(org, "a@example.com")
        _make_user(org, "b@example.com")
        users = service.list_org_users(org)
        assert sorted(u.email for u in users) == ["a@example.com", "b@example.com"]
    finally:
        _delete_org(org)


def test_get_current_user_rejects_a_deactivated_users_still_valid_token() -> None:
    """Regression test: a session JWT is never re-validated against
    Jackson, so deactivation (e.g. a SCIM user.deleted event) must be
    enforced by get_current_user() checking user.active itself - without
    it, a deactivated user keeps full access for the rest of their
    session's 12h TTL."""
    org = _make_org("Deactivation Org")
    try:
        user = _make_user(org, "leaver@example.com")
        token = service.issue_session_token(user)
        assert service.get_current_user(token) is not None

        with org_scoped_session(str(org.id)) as db:
            db.get(User, user.id).active = False

        assert service.get_current_user(token) is None
    finally:
        _delete_org(org)


def test_update_user_role_happy_path_sets_manual_source() -> None:
    org = _make_org("Update Role Org")
    try:
        target = _make_user(org, "target@example.com")
        updated = service.update_user_role(org, str(target.id), "govern", "admin")
        assert updated.business_role == "govern"
        assert updated.system_role == "admin"
        assert updated.role_source == "manual"
    finally:
        _delete_org(org)


def test_update_user_role_rejects_invalid_roles() -> None:
    org = _make_org("Update Role Invalid Org")
    try:
        target = _make_user(org, "target2@example.com")
        with pytest.raises(IdentityValidationError):
            service.update_user_role(org, str(target.id), "not_a_role", "admin")
        with pytest.raises(IdentityValidationError):
            service.update_user_role(org, str(target.id), "govern", "not_a_role")
    finally:
        _delete_org(org)


def test_update_user_role_cannot_assign_super_admin() -> None:
    """super_admin is exclusively granted by the break-glass login, never
    through the normal role-management endpoint."""
    org = _make_org("No Super Admin Assign Org")
    try:
        target = _make_user(org, "target3@example.com")
        with pytest.raises(IdentityValidationError):
            service.update_user_role(org, str(target.id), "govern", "super_admin")
    finally:
        _delete_org(org)


def test_update_user_role_refuses_to_remove_the_last_admin() -> None:
    org = _make_org("Last Admin Org")
    try:
        only_admin = _make_user(org, "onlyadmin@example.com", "govern", "admin")
        with pytest.raises(IdentityValidationError):
            service.update_user_role(org, str(only_admin.id), "operator", "user")
    finally:
        _delete_org(org)


def test_update_user_role_allows_demotion_when_another_admin_remains() -> None:
    org = _make_org("Two Admins Org")
    try:
        admin_one = _make_user(org, "admin1@example.com", "govern", "admin")
        _make_user(org, "admin2@example.com", "govern", "admin")
        demoted = service.update_user_role(org, str(admin_one.id), "operator", "user")
        assert demoted.system_role == "user"
    finally:
        _delete_org(org)


def test_authenticate_super_admin_disabled_when_unconfigured(monkeypatch) -> None:
    monkeypatch.setattr("apps.api.modules.identity.service.settings.super_admin_email", "")
    monkeypatch.setattr("apps.api.modules.identity.service.settings.super_admin_password_hash", "")
    org = _make_org("Super Admin Disabled Org")
    try:
        assert service.authenticate_super_admin(org, "anyone@example.com", "anything") is None
    finally:
        _delete_org(org)


def test_authenticate_super_admin_wrong_credentials(monkeypatch) -> None:
    import bcrypt

    password_hash = bcrypt.hashpw(b"correct-horse", bcrypt.gensalt()).decode("utf-8")
    monkeypatch.setattr("apps.api.modules.identity.service.settings.super_admin_email", "root@example.com")
    monkeypatch.setattr("apps.api.modules.identity.service.settings.super_admin_password_hash", password_hash)
    org = _make_org("Super Admin Wrong Creds Org")
    try:
        assert service.authenticate_super_admin(org, "root@example.com", "wrong-password") is None
        assert service.authenticate_super_admin(org, "someone-else@example.com", "correct-horse") is None
    finally:
        _delete_org(org)


def test_authenticate_super_admin_creates_and_grants_role(monkeypatch) -> None:
    import bcrypt

    password_hash = bcrypt.hashpw(b"correct-horse", bcrypt.gensalt()).decode("utf-8")
    monkeypatch.setattr("apps.api.modules.identity.service.settings.super_admin_email", "root@example.com")
    monkeypatch.setattr("apps.api.modules.identity.service.settings.super_admin_password_hash", password_hash)
    org = _make_org("Super Admin Grant Org")
    try:
        user = service.authenticate_super_admin(org, "root@example.com", "correct-horse")
        assert user is not None
        assert user.system_role == "super_admin"
        assert user.role_source == "manual"

        # A subsequent real SAML login for the same email (business_role
        # mapping is role_source-gated) must not downgrade the grant -
        # handle_callback() never touches system_role at all, and skips
        # business_role remapping whenever role_source == "manual".
        with org_scoped_session(str(org.id)) as db:
            from apps.api.modules.identity.models import User as _User

            reloaded = db.query(_User).filter(_User.org_id == org.id, _User.email == "root@example.com").first()
            assert reloaded.role_source == "manual"
            assert reloaded.system_role == "super_admin"
    finally:
        _delete_org(org)


def test_create_sso_connection_requires_exactly_one_of_url_or_xml() -> None:
    org = _make_org("SSO Connection Validation Org")
    try:
        with pytest.raises(IdentityValidationError):
            service.create_sso_connection(org)
        with pytest.raises(IdentityValidationError):
            service.create_sso_connection(org, metadata_url="https://example.com/metadata.xml", metadata_xml="<xml/>")
    finally:
        _delete_org(org)
