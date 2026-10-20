"""Service layer: Dashboard snapshot MI (BRD §2) — prospects, the client lifecycle, approvals, service
requests and invoices, limited to what the user may see."""
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models import Account, ApprovalRequest, ApprovalStatus, Instruction, InstructionStatus, User, UserRole
from app.services import access_control, client_workflow_service as wf
from app.services import instruction_service, invoice_service, prospect_service

# BRD §9 status lifecycle, in order.
CLIENT_STATUSES = [wf.NEW, wf.WIP, wf.AWAITING, wf.APPROVED, wf.ACTIVE, wf.INACTIVE, wf.MARKED_EXIT, wf.EXITED]
AML_REVIEW_WINDOW_DAYS = 60


def _visible_accounts(db: Session, user: User):
    q = db.query(Account)
    clause = access_control.account_visibility_clause(db, user)
    return q.filter(clause) if clause is not None else q


def build_dashboard(db: Session, user: User) -> dict:
    today = date.today()
    accounts = _visible_accounts(db, user).all()
    by_status = {s: 0 for s in CLIENT_STATUSES}
    for a in accounts:
        if a.profile_status in by_status:
            by_status[a.profile_status] += 1

    prospects = prospect_service.list_prospects(db, user)
    open_prospects = [p for p in prospects if p.converted_account_id is None and p.status != "Lost"]

    open_srs = instruction_service._apply_rbac_filter(db, db.query(Instruction), user).filter(
        Instruction.status.notin_((InstructionStatus.COMPLETED.value, InstructionStatus.CANCELLED.value))).count()
    _, raised = invoice_service.list_invoices(db, user, limit=1, status="Raised")
    _, overdue = invoice_service.list_invoices(db, user, limit=1, status="Overdue")

    visible_ids = {a.id for a in accounts}
    pending = db.query(ApprovalRequest).filter(ApprovalRequest.status == ApprovalStatus.PENDING.value).all()
    pending = [r for r in pending if r.account_id in visible_ids]

    horizon = today + timedelta(days=AML_REVIEW_WINDOW_DAYS)
    aml_due = sorted(
        ({"account_id": a.id, "client_id": a.client_id, "company_name": a.company_name, "risk_rating": a.risk_rating,
          "next_aml_review_date": a.next_aml_review_date, "days_remaining": (a.next_aml_review_date - today).days}
         for a in accounts
         if a.profile_status in (wf.APPROVED, wf.ACTIVE) and a.next_aml_review_date and a.next_aml_review_date <= horizon),
        key=lambda r: r["next_aml_review_date"])

    portfolio = []
    for u in db.query(User).filter(User.is_active == True).order_by(User.name).all():  # noqa: E712
        mine = [a for a in accounts if a.spoc_id == u.id]
        if not mine and (not u.handles_clients or u.role == UserRole.ADMIN):
            continue  # central desks (Compliance, Approver, Accounts, ...) and administrators hold no portfolio
        portfolio.append({
            "user_id": u.id, "name": u.name, "total": len(mine),
            "in_progress": sum(1 for a in mine if a.profile_status in (wf.NEW, wf.WIP, wf.AWAITING)),
            "active": sum(1 for a in mine if a.profile_status in (wf.APPROVED, wf.ACTIVE)),
        })

    return {
        "kpis": {
            "prospects_open": len(open_prospects),
            "prospects_unassigned": sum(1 for p in open_prospects if p.owner_id is None),
            "clients_in_progress": by_status[wf.NEW] + by_status[wf.WIP],
            "clients_awaiting_approval": by_status[wf.AWAITING],
            "clients_active": by_status[wf.APPROVED] + by_status[wf.ACTIVE],
            "service_requests_open": open_srs,
            "invoices_unpaid": raised + overdue,
            "aml_reviews_due": len(aml_due),
        },
        "client_status_breakdown": [{"status": s, "count": by_status[s]} for s in CLIENT_STATUSES],
        "approvals_pending": {
            "compliance": sum(1 for r in pending if r.request_type != "client_profile" or wf.stage_of(r) == wf.STAGE_COMPLIANCE),
            "approver": sum(1 for r in pending if r.request_type == "client_profile" and wf.stage_of(r) == wf.STAGE_APPROVER),
        },
        "aml_reviews_due": aml_due,
        "portfolio_by_rm": portfolio,
    }
