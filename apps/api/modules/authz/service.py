from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.api.modules.identity.models import User

# business_role x system_role x action permission matrix. Each action maps
# to a list of rules (OR'd together); within one rule, both axes must match
# where set (AND) - None means "no restriction on that axis". This lets an
# action be granted by either of two independent role paths (e.g. policy.
# manage: the govern business role OR a system admin) without collapsing
# into one over-broad rule. Every route handler must go through can() -
# never an inline `if user.role == ...` check (handoff §2.7).
_PERMISSIONS: dict[str, list[dict[str, set[str] | None]]] = {
    "identity.view_self": [{"system_role": None, "business_role": None}],
    "identity.manage_sso": [{"system_role": {"admin", "super_admin"}, "business_role": None}],
    "branding.manage": [{"system_role": {"admin", "super_admin"}, "business_role": None}],
    "tools.approve_request": [{"system_role": None, "business_role": {"govern", "assure"}}],
    "policy.manage": [
        {"system_role": None, "business_role": {"govern"}},
        {"system_role": {"admin", "super_admin"}, "business_role": None},
    ],
    "policy.view": [{"system_role": None, "business_role": None}],
}


def can(user: "User", action: str, resource: object = None) -> bool:
    rules = _PERMISSIONS.get(action)
    if not rules:
        return False

    for rule in rules:
        allowed_system_roles = rule["system_role"]
        if allowed_system_roles is not None and user.system_role not in allowed_system_roles:
            continue
        allowed_business_roles = rule["business_role"]
        if allowed_business_roles is not None and user.business_role not in allowed_business_roles:
            continue
        return True

    return False
