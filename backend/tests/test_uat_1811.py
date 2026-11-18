"""Triam UAT issues log 18-11-2026.

- Row 90: Triam's Client ID is allotted only after the Final approval, not at the Compliance approval.
  Service requests still open once Compliance has approved (decision of 12-11-2026).
- Row 61: lists start with the latest and go to the oldest.
"""
from datetime import datetime, timezone

from app.models import ApprovalRequest
from app.schemas.account import AccountUpdate
from app.services import account_service, client_workflow_service as wf, dashboard_service, instruction_service as sr
from tests import flow


def _client(db, maker, name):
    acc = flow.complete_client(db, maker)
    account_service.update_account(db, acc.id, AccountUpdate(company_name=name), maker)
    db.refresh(acc)
    return acc


def test_client_id_waits_for_the_final_approval(db, people):
    acc = flow.complete_client(db, people["maker"])
    flow.submit(db, acc, people["maker"])
    assert acc.client_id is None and acc.approval_stage == "Compliance"

    flow.compliance_approve(db, acc, people["checker"])
    db.refresh(acc)
    assert acc.client_id is None and acc.approval_stage == "Approver"

    wf.approve(db, acc, people["approver"], "Final approval given")
    db.refresh(acc)
    assert acc.profile_status == "Approved" and acc.client_id == "TCPL/00001"
    assert acc.approval_stage is None


def test_service_requests_follow_the_compliance_approval_not_the_client_id(db, people):
    acc = flow.complete_client(db, people["maker"])
    flow.submit(db, acc, people["maker"])
    assert not sr.takes_requests(acc)  # still with Compliance
    flow.compliance_approve(db, acc, people["checker"])
    db.refresh(acc)
    assert acc.client_id is None and sr.takes_requests(acc)


def test_a_client_rejected_by_compliance_gets_no_client_id(db, people):
    acc = flow.complete_client(db, people["maker"])
    flow.submit(db, acc, people["maker"])
    wf.reject(db, acc, people["checker"], "Documents missing or incomplete", "The licence copy is not readable")
    db.refresh(acc)
    assert acc.profile_status == "Rejected" and acc.client_id is None


def test_approval_queues_list_the_latest_first(db, people):
    older = _client(db, people["maker"], "Older Co")
    flow.submit(db, older, people["maker"])
    newer = _client(db, people["maker"], "Newer Co")
    flow.submit(db, newer, people["maker"])

    inbox = wf.inbox(db, people["checker"])
    assert [r.account_id for r in inbox] == [newer.id, older.id]

    rows = dashboard_service.build_dashboard(db, people["maker"])["pending_approvals"]  # the RM's own clients
    assert [r["account_id"] for r in rows] == [newer.id, older.id]


def test_decided_requests_list_the_latest_decision_first(db, people):
    first = _client(db, people["maker"], "First Co")
    second = _client(db, people["maker"], "Second Co")
    flow.submit(db, first, people["maker"])
    flow.submit(db, second, people["maker"])
    # Decided in the other order: the queue follows the decision, not the submission.
    wf.reject(db, second, people["checker"], "Documents missing or incomplete", "The licence copy is not readable")
    wf.reject(db, first, people["checker"], "Documents missing or incomplete", "The passport copy is not readable")
    # Fixed decision times, so the test doesn't depend on the clock's resolution.
    for acc, day in ((second, 1), (first, 2)):
        req = db.query(ApprovalRequest).filter(ApprovalRequest.account_id == acc.id).one()
        req.decided_at = datetime(2026, 11, day, 9, 0, tzinfo=timezone.utc)
    db.commit()

    rejected = wf.inbox(db, people["checker"], status="Rejected")
    assert [r.account_id for r in rejected] == [first.id, second.id]


def test_imported_mobile_numbers_take_digits_only(db, make_user):
    """Row 88: letters in a phone number are refused on the form and, now, in the CSV import too."""
    from app.models import Account
    from app.schemas.account import AccountImportRow
    admin = make_user("Ada", role="admin")
    rows = [
        AccountImportRow(company_name="Letters Ltd", contact_mobile_country_code="+971", contact_mobile_number="50ABC4567"),
        AccountImportRow(company_name="Short Ltd", contact_mobile_country_code="+971", contact_mobile_number="5012"),
        AccountImportRow(company_name="Good Ltd", contact_mobile_country_code="+971", contact_mobile_number="050-123 4567"),
    ]
    results = account_service.import_accounts(db, admin, rows, dry_run=False)
    assert [r.status for r in results] == ["error", "error", "ok"]
    assert "digits only" in results[0].message and "9 digits" in results[1].message
    assert db.query(Account).filter(Account.company_name == "Good Ltd").one().contact_mobile_number == "501234567"
