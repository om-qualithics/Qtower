from fastapi import APIRouter, Cookie, HTTPException

from apps.api.modules.authz import service as authz_service
from apps.api.modules.branding import service as branding_service
from apps.api.modules.branding.schemas import BrandingConfigOut, BrandingConfigUpdate, LicenseStatusOut
from apps.api.modules.identity import service as identity_service

router = APIRouter(prefix="/branding", tags=["branding"])


def _to_config_out(config) -> BrandingConfigOut:
    if config is None:
        return BrandingConfigOut(
            org_display_name=None,
            logo_url=None,
            primary_color=None,
            secondary_color=None,
            enabled_feature_modules=None,
            escalation_notify_override_email=None,
            email_templates=None,
            tool_assessment_prompt=None,
        )
    return BrandingConfigOut(
        org_display_name=config.org_display_name,
        logo_url=config.logo_url,
        primary_color=config.primary_color,
        secondary_color=config.secondary_color,
        enabled_feature_modules=config.enabled_feature_modules,
        escalation_notify_override_email=config.escalation_notify_override_email,
        email_templates=config.email_templates,
        tool_assessment_prompt=config.tool_assessment_prompt,
    )


@router.get("/config", response_model=BrandingConfigOut)
def get_config():
    """Public - the login page needs branding before anyone is signed in."""
    org = identity_service.get_org()
    return _to_config_out(branding_service.get_config(org))


@router.patch("/config", response_model=BrandingConfigOut)
def update_config(body: BrandingConfigUpdate, misty_session: str | None = Cookie(default=None)):
    user = identity_service.get_current_user(misty_session)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if not authz_service.can(user, "branding.manage"):
        raise HTTPException(status_code=403, detail="Forbidden")

    org = identity_service.get_org()
    config = branding_service.update_config(org, body.model_dump(exclude_unset=True))
    return _to_config_out(config)


@router.get("/license", response_model=LicenseStatusOut)
def get_license_status(misty_session: str | None = Cookie(default=None)):
    """Admin-only, unlike /config - seat count/expiry is admin-facing, not
    needed pre-login the way branding colors/logo are."""
    user = identity_service.get_current_user(misty_session)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if not authz_service.can(user, "branding.manage"):
        raise HTTPException(status_code=403, detail="Forbidden")

    org = identity_service.get_org()
    config = branding_service.get_config(org)
    if config is None:
        return LicenseStatusOut(
            license_valid=False,
            license_seat_count=None,
            license_expires_at=None,
            license_validated_at=None,
            enabled_feature_modules=None,
        )
    return LicenseStatusOut(
        license_valid=config.license_valid,
        license_seat_count=config.license_seat_count,
        license_expires_at=config.license_expires_at,
        license_validated_at=config.license_validated_at,
        enabled_feature_modules=config.enabled_feature_modules,
    )
