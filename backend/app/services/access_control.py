"""Shared case-visibility rules for RM role-based access control.

An RM sees/edits a case if they are the primary RM (Case.rm_id), an additional RM
(CaseAdditionalRM), or the Single Point of Contact on the case's account
(Account.spoc_id). Admin / Ops / Screening are unaffected — they keep full visibility
(SPOC only restricts the RM role, per the client's decision).
"""
from sqlalchemy import or_, select

from app.models import Case, CaseAdditionalRM, Account, User, UserRole


def rm_visibility_clause(user_id: int):
    """A filter expression for any query that selects (or is joined to) Case."""
    return or_(
        Case.rm_id == user_id,
        Case.id.in_(select(CaseAdditionalRM.case_id).where(CaseAdditionalRM.user_id == user_id)),
        Case.account_id.in_(select(Account.id).where(Account.spoc_id == user_id)),
    )


def user_can_access_case(case: Case, user: User) -> bool:
    """Python-level check for an already-loaded Case (single-object 403 guards)."""
    if user.role != UserRole.RM:
        return True
    if case.rm_id == user.id:
        return True
    if any(r.user_id == user.id for r in case.additional_rms):
        return True
    if case.account_id and case.account is not None and case.account.spoc_id == user.id:
        return True
    return False
