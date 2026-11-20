"""Permission resolution (BRD §15). Code asks "may this user do X?", never "is this user an MLRO?".

Effective permissions = everything for the Admin tier, otherwise the flags on the user's active
business roles (main + additional, Role.permissions). The staff tier grants no extra flags.
"""
from app.models import User, UserRole, PERMISSIONS


# A permission that only makes sense together with another. A checker must be able to open any
# client they may be asked to approve, so approving implies seeing all clients (BRD §15).
IMPLIED = {
    "client.approve": {"view.all_clients", "client.cdd_edit"},
    "client.final_approve": {"view.all_clients"},
}


# A role with this permission is client-facing (RM, RO, FO, Sales Manager …): its users hold clients,
# are listed among the RMs and get the full client menu. Set by the administrator on the role.
PORTFOLIO_PERMISSION = "client.portfolio"


# Triam UAT 19-11-2026: downloading reports as Excel / PDF is given to a user by the Administrator (the user's
# "Can export reports" tick-box), not by a business role. Administrators always may.
REPORT_EXPORT = "report.export"


def user_permissions(user: User) -> set[str]:
    if user.role == UserRole.ADMIN:
        return (set(PERMISSIONS) - {"read_only"}) | {REPORT_EXPORT}
    granted = {p for role in user.all_business_roles for p in (role.permissions or []) if p in PERMISSIONS}
    for p in list(granted):
        granted |= IMPLIED.get(p, set())
    if getattr(user, "can_export_reports", False):
        granted.add(REPORT_EXPORT)
    return granted


def has_permission(user: User, flag: str) -> bool:
    return flag in user_permissions(user)
