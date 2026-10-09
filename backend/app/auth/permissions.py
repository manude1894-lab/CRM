"""Permission resolution (BRD §15). Code asks "may this user do X?", never "is this user an MLRO?".

Effective permissions = everything for the Admin tier, otherwise the flags on the user's active
business roles (main + additional, Role.permissions). The system tiers (rm / ops / screening) grant no extra flags —
their existing screen access is unchanged and still enforced by require_roles.
"""
from app.models import User, UserRole, PERMISSIONS


# A permission that only makes sense together with another. A checker must be able to open any
# client they may be asked to approve, so approving implies seeing all clients (BRD §15).
IMPLIED = {
    "client.approve": {"view.all_clients", "client.cdd_edit"},
    "client.final_approve": {"view.all_clients"},
}


def user_permissions(user: User) -> set[str]:
    if user.role == UserRole.ADMIN:
        return set(PERMISSIONS)
    granted = {p for role in user.all_business_roles for p in (role.permissions or []) if p in PERMISSIONS}
    for p in list(granted):
        granted |= IMPLIED.get(p, set())
    return granted


def has_permission(user: User, flag: str) -> bool:
    return flag in user_permissions(user)
