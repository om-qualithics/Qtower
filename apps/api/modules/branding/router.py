from fastapi import APIRouter, Cookie, HTTPException

from apps.api.modules.authz import service as authz_service
from apps.api.modules.branding import service as branding_service
from apps.api.modules.branding.schemas import BrandingConfigOut, BrandingConfigUpdate
from apps.api.modules.identity import service as identity_service

router = APIRouter(prefix="/branding", tags=["branding"])


@router.get("/config", response_model=BrandingConfigOut)
def get_config():
    """Public - the login page needs branding before anyone is signed in."""
    org = identity_service.get_org()
    config = branding_service.get_config(org)
    if config is None:
        return BrandingConfigOut(
            org_display_name=None,
            logo_url=None,
            primary_color=None,
            secondary_color=None,
            enabled_feature_modules=None,
            escalation_notify_override_email=None,
        )
    return BrandingConfigOut(
        org_display_name=config.org_display_name,
        logo_url=config.logo_url,
        primary_color=config.primary_color,
        secondary_color=config.secondary_color,
        enabled_feature_modules=config.enabled_feature_modules,
        escalation_notify_override_email=config.escalation_notify_override_email,
    )


@router.patch("/config", response_model=BrandingConfigOut)
def update_config(body: BrandingConfigUpdate, misty_session: str | None = Cookie(default=None)):
    user = identity_service.get_current_user(misty_session)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if not authz_service.can(user, "branding.manage"):
        raise HTTPException(status_code=403, detail="Forbidden")

    org = identity_service.get_org()
    config = branding_service.update_config(org, body.model_dump(exclude_unset=True))
    return BrandingConfigOut(
        org_display_name=config.org_display_name,
        logo_url=config.logo_url,
        primary_color=config.primary_color,
        secondary_color=config.secondary_color,
        enabled_feature_modules=config.enabled_feature_modules,
        escalation_notify_override_email=config.escalation_notify_override_email,
    )
