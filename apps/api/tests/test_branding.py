from apps.api.core.db import SessionLocal, org_scoped_session
from apps.api.modules.branding import service as branding_service
from apps.api.modules.branding.models import DeploymentConfig
from apps.api.modules.identity.models import Org


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


def _delete_org(org: Org) -> None:
    with org_scoped_session(str(org.id)) as db:
        db.query(DeploymentConfig).filter(DeploymentConfig.org_id == org.id).delete(synchronize_session=False)
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
