from apps.api.core.templating import substitute
from apps.api.modules.branding import service as branding_service
from apps.api.modules.identity.models import Org

# One entry today - escalation-raised is the only notification type this
# app sends (Milestone 7). Keyed by a stable string so deployment_config.
# email_templates can hold a per-org override under the same key.
DEFAULT_TEMPLATES: dict[str, dict[str, str]] = {
    "escalation_raised": {
        "subject": "[Q Tower] New escalation: {{category}}",
        "body": "{{reporter_email}} raised a new escalation.\n\nCategory: {{category}}\n\n{{description}}",
    },
}


def render_template(org: Org, key: str, context: dict[str, str]) -> tuple[str, str]:
    config = branding_service.get_config(org)
    override = (config.email_templates or {}).get(key) if config else None
    template = override or DEFAULT_TEMPLATES[key]
    return substitute(template["subject"], context), substitute(template["body"], context)
