BUSINESS_ROLES = ("govern", "assure", "operator")
SYSTEM_ROLES = ("user", "admin", "super_admin")
ADMIN_SYSTEM_ROLES = ("admin", "super_admin")

# "super_admin" is deliberately excluded here - it's granted exclusively by
# a successful super-admin local login (identity_service.authenticate_super_admin),
# never assignable through the Manage Users screen. Keeps "who holds the
# break-glass identity" defined by deployment config (SUPER_ADMIN_EMAIL),
# not by any in-app action.
ASSIGNABLE_SYSTEM_ROLES = ("user", "admin")
