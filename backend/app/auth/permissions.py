"""Permission resolution (BRD §15). Code asks "may this user do X?", never "is this user an MLRO?".

Effective permissions = everything for the Admin tier, otherwise the flags on the user's active
business role (Role.permissions). The system tiers (rm / ops / screening) grant no extra flags —
their existing screen access is unchanged and still enforced by require_roles.
"""
from app.models import User, UserRole, PERMISSIONS


def user_permissions(user: User) -> set[str]:
    if user.role == UserRole.ADMIN:
        return set(PERMISSIONS)
    role = user.business_role
    if role is None or not role.is_active:
        return set()
    return {p for p in (role.permissions or []) if p in PERMISSIONS}


def has_permission(user: User, flag: str) -> bool:
    return flag in user_permissions(user)
