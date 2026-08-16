from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.api.modules.identity.models import User

# business_role x system_role x action permission matrix. None means "no
# restriction on that axis". Every route handler must go through can() -
# never an inline `if user.role == ...` check (handoff §2.7).
_PERMISSIONS: dict[str, dict[str, set[str] | None]] = {
    "identity.view_self": {"system_role": None, "business_role": None},
    "identity.manage_sso": {"system_role": {"admin", "super_admin"}, "business_role": None},
    "branding.manage": {"system_role": {"admin", "super_admin"}, "business_role": None},
    "tools.approve_request": {"system_role": None, "business_role": {"govern", "assure"}},
}


def can(user: "User", action: str, resource: object = None) -> bool:
    rule = _PERMISSIONS.get(action)
    if rule is None:
        return False

    allowed_system_roles = rule["system_role"]
    if allowed_system_roles is not None and user.system_role not in allowed_system_roles:
        return False

    allowed_business_roles = rule["business_role"]
    if allowed_business_roles is not None and user.business_role not in allowed_business_roles:
        return False

    return True
