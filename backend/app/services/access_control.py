"""Shared visibility rules — who may see which clients (BRD §13).

BRD §15 "RM privacy": one RM must not see another RM's clients unless role/hierarchy allows it.
"Supervisor visibility": a supervisor sees the clients of every RM who reports to them
(directly or further down the chain).

Who is restricted: staff users. Administrators see every client. Business-role permissions
`view.all_clients` / `view.department_clients` widen a staff user's view.

A user's *team* = themself + everyone below them in the supervisor chain.

Clients: visible when a team member is the Anchor RM (spoc_id), a Non-anchor RM, or the creator
(owner_id); or, with view.department_clients, when the Anchor RM is in the user's department.
"""
from sqlalchemy import or_, false
from sqlalchemy.orm import Session

from app.auth.permissions import has_permission
from app.models import Account, User, UserRole


# ─── Team (supervisor hierarchy) ─────────────────────────────────────────────

def team_user_ids(db: Session, user_id: int) -> set[int]:
    """The user plus everyone who reports to them, directly or indirectly. Cycle-safe."""
    team = {user_id}
    frontier = [user_id]
    while frontier:
        rows = db.query(User.id).filter(User.supervisor_id.in_(frontier)).all()
        frontier = [r.id for r in rows if r.id not in team]
        team.update(frontier)
    return team


def would_create_supervisor_cycle(db: Session, user_id: int, new_supervisor_id: int | None) -> bool:
    """True if making new_supervisor_id the supervisor of user_id loops the hierarchy."""
    if new_supervisor_id is None:
        return False
    return new_supervisor_id in team_user_ids(db, user_id)


def _is_restricted(user: User) -> bool:
    return user.role == UserRole.RM and not has_permission(user, "view.all_clients")


# ─── Clients ────────────────────────────────────────────────────────────────

def _account_ids_with_non_anchor(db: Session, ids: set[int]) -> list[int]:
    """Accounts whose Non-anchor RM list includes any of `ids`. non_anchor_rm_ids is a JSON list,
    which has no portable SQL 'contains', so it's filtered in Python (client counts are small)."""
    rows = db.query(Account.id, Account.non_anchor_rm_ids).filter(Account.non_anchor_rm_ids.isnot(None)).all()
    return [r.id for r in rows if ids.intersection(r.non_anchor_rm_ids or [])]


def same_person(other: User | None, user: User) -> bool:
    """True when `other` is `user` or another of the same person's logins (one login per role, Triam
    29-10-2026). Maker-checker uses it: nobody approves their own work under a different login."""
    return other is not None and other.person_key == user.person_key


def account_visibility_clause(db: Session, user: User):
    """Filter for Account queries, or None when the user sees every client."""
    if not _is_restricted(user):
        return None
    team = team_user_ids(db, user.id)
    anchor_ids = set(team)
    if has_permission(user, "view.department_clients") and user.department_id:
        anchor_ids |= {r.id for r in db.query(User.id).filter(User.department_id == user.department_id).all()}
    return or_(
        Account.spoc_id.in_(anchor_ids),
        Account.owner_id.in_(team),
        Account.id.in_(_account_ids_with_non_anchor(db, team)) if team else false(),
    )


def user_can_access_account(db: Session, account: Account, user: User) -> bool:
    if not _is_restricted(user):
        return True
    team = team_user_ids(db, user.id)
    if account.spoc_id in team or account.owner_id in team:
        return True
    if team.intersection(account.non_anchor_rm_ids or []):
        return True
    if has_permission(user, "view.department_clients") and user.department_id and account.spoc_id:
        anchor = db.get(User, account.spoc_id)
        return bool(anchor and anchor.department_id == user.department_id)
    return False
