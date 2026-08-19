from pydantic import BaseModel


class BrandingConfigOut(BaseModel):
    org_display_name: str | None
    logo_url: str | None
    primary_color: str | None
    secondary_color: str | None
    enabled_feature_modules: list[str] | None
    escalation_notify_override_email: str | None


class BrandingConfigUpdate(BaseModel):
    org_display_name: str | None = None
    logo_url: str | None = None
    primary_color: str | None = None
    secondary_color: str | None = None
    escalation_notify_override_email: str | None = None
