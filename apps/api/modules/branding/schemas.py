from datetime import datetime

from pydantic import BaseModel


class BrandingConfigOut(BaseModel):
    org_display_name: str | None
    logo_url: str | None
    primary_color: str | None
    secondary_color: str | None
    enabled_feature_modules: list[str] | None
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
