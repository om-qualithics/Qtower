from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.core.db import SessionLocal, org_scoped_session
from apps.api.modules.branding import service as branding_service
from apps.api.modules.branding.models import DeploymentConfig
from apps.api.modules.branding.router import router as branding_router
from apps.api.modules.identity import service as identity_service
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


def _make_admin_user(org: Org, email: str) -> User:
    with org_scoped_session(str(org.id)) as db:
        user = User(org_id=org.id, email=email, business_role="govern", system_role="admin")
        db.add(user)
        db.flush()
        db.refresh(user)
        db.expunge(user)
        return user


def _delete_org(org: Org) -> None:
    with org_scoped_session(str(org.id)) as db:
        db.query(DeploymentConfig).filter(DeploymentConfig.org_id == org.id).delete(synchronize_session=False)
        db.query(User).filter(User.org_id == org.id).delete(synchronize_session=False)
    db = SessionLocal()
    try:
        db.query(Org).filter(Org.id == org.id).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def test_update_config_can_clear_a_field_back_to_null() -> None:
    """Regression test: update_config() used to silently skip any None
    value, which - combined with the router's exclude_unset=True - made it
    impossible to ever clear a nullable field back to null via PATCH. An
    explicit None in the fields dict must mean "clear this," not "leave
    unchanged" (that's what a missing key means)."""
    org = _make_org("Branding Clear Field Org")
    try:
        config = branding_service.update_config(org, {"org_display_name": "Acme Inc", "logo_url": "https://x/y.png"})
        assert config.org_display_name == "Acme Inc"

        cleared = branding_service.update_config(org, {"org_display_name": None})
        assert cleared.org_display_name is None
        # A field not mentioned at all must stay untouched.
        assert cleared.logo_url == "https://x/y.png"

        reread = branding_service.get_config(org)
        assert reread is not None
        assert reread.org_display_name is None
    finally:
        _delete_org(org)


def _build_branding_only_app() -> FastAPI:
    """Same throwaway-app pattern as test_license_gate.py - isolates the
    branding router from main.py's real lifespan (license sync, MinIO
    bucket creation) and its single-org-per-container get_org() lookup,
    neither of which this test needs or should depend on."""
    app = FastAPI()
    app.include_router(branding_router)
    return app


def test_public_config_endpoint_excludes_admin_only_fields(monkeypatch) -> None:
    """Regression test: the unauthenticated GET /branding/config used to
    share its serializer with the branding.manage-gated PATCH response,
    so it leaked email_templates/tool_assessment_prompt/
    escalation_notify_override_email to anyone with no session at all.
    GET /branding/config must return only the public branding subset;
    GET /branding/admin-config (branding.manage-gated) is the only place
    the admin-authored fields should appear."""
    org = _make_org("Public Config Leak Org")
    try:
        branding_service.update_config(
            org,
            {
                "org_display_name": "Acme Inc",
                "tool_assessment_prompt": "SECRET PROMPT TEXT",
                "email_templates": {"escalation_raised": {"subject": "s", "body": "b"}},
                "escalation_notify_override_email": "secret@acme.example",
            },
        )
        monkeypatch.setattr("apps.api.modules.branding.router.identity_service.get_org", lambda: org)
        client = TestClient(_build_branding_only_app())

        public_resp = client.get("/branding/config")
        assert public_resp.status_code == 200
        body = public_resp.json()
        assert body["org_display_name"] == "Acme Inc"
        assert "tool_assessment_prompt" not in body
        assert "email_templates" not in body
        assert "escalation_notify_override_email" not in body

        admin = _make_admin_user(org, "admin@public-config-leak.example")
        client.cookies.set(identity_service.SESSION_COOKIE_NAME, identity_service.issue_session_token(admin))
        admin_resp = client.get("/branding/admin-config")
        assert admin_resp.status_code == 200
        admin_body = admin_resp.json()
        assert admin_body["tool_assessment_prompt"] == "SECRET PROMPT TEXT"
        assert admin_body["email_templates"]["escalation_raised"]["subject"] == "s"
        assert admin_body["escalation_notify_override_email"] == "secret@acme.example"

        unauth_admin_resp = TestClient(_build_branding_only_app()).get("/branding/admin-config")
        assert unauth_admin_resp.status_code == 401
    finally:
        _delete_org(org)
