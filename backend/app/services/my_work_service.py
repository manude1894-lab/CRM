"""Role-level dashboard (Triam BRD mark-up §2): the work waiting for *this* user, by what they may do.

Each item is {key, label, count, page, hint}; the dashboard shows the ones with something to do.
"""
from sqlalchemy.orm import Session

from app.auth.permissions import has_permission
from app.models import Account, ApprovalRequest, ApprovalStatus, Invoice, Prospect, User
from app.services import access_control, client_workflow_service as wf


def _visible_accounts(db: Session, user: User):
    q = db.query(Account)
    clause = access_control.account_visibility_clause(db, user)
    return q.filter(clause) if clause is not None else q


def my_work(db: Session, user: User) -> list[dict]:
    items: list[dict] = []

    def add(key, label, count, page, hint=None):
        items.append({"key": key, "label": label, "count": count, "page": page, "hint": hint})

    pending = db.query(ApprovalRequest).filter(ApprovalRequest.status == ApprovalStatus.PENDING.value).all()
    if has_permission(user, "client.approve"):
        new_clients = [r for r in pending if r.request_type == "client_profile" and wf.stage_of(r) == wf.STAGE_COMPLIANCE and r.maker_id != user.id]
        others = [r for r in pending if r.request_type != "client_profile" and r.maker_id != user.id]
        add("compliance_new", "New clients waiting for Compliance", len(new_clients), "approvals", "Complete the CDD section, then approve or reject")
        add("compliance_changes", "Amendments and cases waiting for Compliance", len(others), "approvals")
    if has_permission(user, "client.final_approve"):
        final = [r for r in pending if r.request_type == "client_profile" and wf.stage_of(r) == wf.STAGE_APPROVER and r.maker_id != user.id]
        add("approver", "New clients waiting for your final approval", len(final), "approvals")
    if has_permission(user, "invoice.manage"):
        add("invoice_requests", "Invoice instructions to raise", db.query(Invoice).filter(Invoice.status.in_(("Requested", "Draft"))).count(), "invoices")
        add("invoice_unpaid", "Raised invoices not yet paid", db.query(Invoice).filter(Invoice.status.in_(("Raised", "Overdue"))).count(), "invoices")
    if has_permission(user, "prospect.assign"):
        add("prospects_unassigned", "Prospects waiting to be assigned", db.query(Prospect).filter(Prospect.owner_id.is_(None), Prospect.status != "Lost").count(), "prospects")

    # Everyone who prepares clients (RM / RO / FO / Sales)
    mine = _visible_accounts(db, user).filter((Account.spoc_id == user.id) | (Account.owner_id == user.id))
    in_progress = mine.filter(Account.profile_status.in_((wf.NEW, wf.WIP))).all()
    returned_ids = {r.account_id for r in db.query(ApprovalRequest.account_id).filter(
        ApprovalRequest.request_type == "client_profile", ApprovalRequest.status == ApprovalStatus.REJECTED.value,
        ApprovalRequest.account_id.in_([a.id for a in in_progress] or [-1])).all()}
    add("my_returned", "My clients returned with comments", len(returned_ids), "accounts", "Fix the points raised and submit again")
    add("my_in_progress", "My clients being prepared", len(in_progress) - len(returned_ids), "accounts")
    add("my_with_review", "My clients with Compliance / Approver", mine.filter(Account.profile_status == wf.AWAITING).count(), "accounts")
    add("my_prospects", "My prospects without a client yet", db.query(Prospect).filter(
        Prospect.owner_id == user.id, Prospect.converted_account_id.is_(None), Prospect.status != "Lost").count(), "prospects")
    add("my_invoices_ready", "My invoices ready to send to the client", db.query(Invoice).filter(
        Invoice.requested_by_id == user.id, Invoice.status == "Raised").count(), "invoices")
    return items
