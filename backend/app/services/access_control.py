"""Shared visibility rules — who may see which clients and cases (BRD §15).

BRD §15 "RM privacy": one RM must not see another RM's clients unless role/hierarchy allows it.
"Supervisor visibility": a supervisor sees the clients of every RM who reports to them
(directly or further down the chain).

Who is restricted: the RM system tier only. Admin / Ops / Screening keep full visibility, as before
(SPOC only restricts the RM role, per the client's earlier decision). Business-role permissions
`view.all_clients` / `view.department_clients` widen an RM's view.

A user's *team* = themself + everyone below them in the supervisor chain.

Clients: visible when a team member is the Anchor RM (spoc_id), a Non-anchor RM, or the creator
(owner_id); or, with view.department_clients, when the Anchor RM is in the user's department.

Cases: visible when a team member is the primary RM, an additional RM, or the Anchor RM on the
case's client.
"""
from sqlalchemy import or_, select, false, true
from sqlalchemy.orm import Session, object_session

from app.auth.permissions import has_permission
from app.models import Case, CaseAdditionalRM, Account, User, UserRole


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


def _db_for(user: User) -> Session | None:
    return object_session(user)


def _is_restricted(user: User) -> bool:
    return user.role == UserRole.RM and not has_permission(user, "view.all_clients")


# ─── Clients ────────────────────────────────────────────────────────────────

def _account_ids_with_non_anchor(db: Session, ids: set[int]) -> list[int]:
    """Accounts whose Non-anchor RM list includes any of `ids`. non_anchor_rm_ids is a JSON list,
    which has no portable SQL 'contains', so it's filtered in Python (client counts are small)."""
    rows = db.query(Account.id, Account.non_anchor_rm_ids).filter(Account.non_anchor_rm_ids.isnot(None)).all()
    return [r.id for r in rows if ids.intersection(r.non_anchor_rm_ids or [])]


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


# ─── Cases ──────────────────────────────────────────────────────────────────

def rm_visibility_clause(user: User | int):
    """A filter expression for any query that selects (or is joined to) Case.

    Accepts a User (preferred — includes the supervisor's team) or a bare user id (legacy callers:
    that user only)."""
    if isinstance(user, User):
        if not _is_restricted(user):
            return true()
        db = _db_for(user)
        ids = team_user_ids(db, user.id) if db is not None else {user.id}
    else:
        ids = {user}
    return or_(
        Case.rm_id.in_(ids),
        Case.id.in_(select(CaseAdditionalRM.case_id).where(CaseAdditionalRM.user_id.in_(ids))),
        Case.account_id.in_(select(Account.id).where(Account.spoc_id.in_(ids))),
    )


def user_can_access_case(case: Case, user: User) -> bool:
    """Python-level check for an already-loaded Case (single-object 403 guards)."""
    if not _is_restricted(user):
        return True
    db = _db_for(user)
    ids = team_user_ids(db, user.id) if db is not None else {user.id}
    if case.rm_id in ids:
        return True
    if any(r.user_id in ids for r in case.additional_rms):
        return True
    if case.account_id and case.account is not None and case.account.spoc_id in ids:
        return True
    return False
