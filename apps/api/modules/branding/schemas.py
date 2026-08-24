from datetime import datetime

from pydantic import BaseModel


class BrandingPublicConfigOut(BaseModel):
    """Served by the unauthenticated GET /branding/config - the login page
    needs these fields before anyone is signed in. Deliberately excludes
    every admin-authored field below (email_templates, tool_assessment_prompt,
    escalation_notify_override_email) - those are internal configuration,
    not something the pre-auth screen needs, and have no business being
    readable by an anonymous caller."""

    org_display_name: str | None
    logo_url: str | None
    primary_color: str | None
    secondary_color: str | None
    enabled_feature_modules: list[str] | None


class BrandingConfigOut(BrandingPublicConfigOut):
    """Full config including admin-authored fields - only ever returned
    from an authenticated, branding.manage-gated route (the PATCH response
    and GET /branding/admin-config)."""

    escalation_notify_override_email: str | None
    email_templates: dict[str, dict[str, str]] | None
    tool_assessment_prompt: str | None


class BrandingConfigUpdate(BaseModel):
    org_display_name: str | None = None
    logo_url: str | None = None
    primary_color: str | None = None
    secondary_color: str | None = None
    escalation_notify_override_email: str | None = None
    email_templates: dict[str, dict[str, str]] | None = None
    tool_assessment_prompt: str | None = None


class LicenseStatusOut(BaseModel):
    license_valid: bool
    license_seat_count: int | None
    license_expires_at: datetime | None
    license_validated_at: datetime | None
    enabled_feature_modules: list[str] | None
