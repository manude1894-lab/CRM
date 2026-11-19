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


# ─── Onboarding statuses the RM sets (UAT 18-11-2026 rows 112-121) ──────────────────────────────────────

def test_pending_with_client_is_a_label_the_client_can_still_be_edited_and_submitted(db, people):
    import pytest
    from fastapi import HTTPException
    rm = people["maker"]
    acc = flow.complete_client(db, rm)
    wf.change_status(db, acc, rm, "pending_client", "Waiting for the passport copies")
    assert (acc.profile_status, acc.status_reason) == ("Pending with Client", "Waiting for the passport copies")
    account_service.update_account(db, acc.id, AccountUpdate(nature_of_business="Fintech payments"), rm)
    wf.change_status(db, acc, rm, "pending_authority")
    assert acc.profile_status == "Pending with Regn Authority" and acc.status_reason is None
    flow.submit(db, acc, rm)
    assert acc.profile_status == "Awaiting Approval" and acc.status_reason is None
    with pytest.raises(HTTPException):  # not while it is with Compliance
        wf.change_status(db, acc, rm, "hold")


def test_on_hold_cannot_be_submitted_until_resumed(db, people):
    import pytest
    from fastapi import HTTPException
    rm = people["maker"]
    acc = flow.complete_client(db, rm)
    wf.change_status(db, acc, rm, "hold", "Client travelling until December")
    assert {a["action"] for a in wf.allowed_actions(db, acc, rm)} == {"resume", "drop"}
    with pytest.raises(HTTPException):
        flow.submit(db, acc, rm)
    account_service.update_account(db, acc.id, AccountUpdate(nature_of_business="Still editable"), rm)
    assert acc.client_id is None  # saving a parked client issues no Client ID
    wf.change_status(db, acc, rm, "resume")
    assert acc.profile_status == "WIP" and acc.status_reason is None
    flow.submit(db, acc, rm)


def test_drop_needs_a_reason_from_the_list_and_other_needs_text(db, people):
    import pytest
    from fastapi import HTTPException
    rm = people["maker"]
    acc = flow.complete_client(db, rm)
    for code, text in ((None, "No reply"), ("Lost interest", None), ("Other", None)):
        with pytest.raises(HTTPException) as e:
            wf.change_status(db, acc, rm, "drop", text, code)
        assert e.value.status_code == 400
    wf.change_status(db, acc, rm, "drop", "Three reminders, no reply", "Client not responding")
    assert (acc.profile_status, acc.status_reason_code) == ("Dropped", "Client not responding")


def test_a_dropped_client_is_read_only_until_the_rm_reopens_it(db, people):
    import pytest
    from fastapi import HTTPException
    from app.schemas.account import AccountCreate
    rm = people["maker"]
    acc = flow.complete_client(db, rm)
    wf.change_status(db, acc, rm, "drop", None, "Client withdrew")
    assert [a["action"] for a in wf.allowed_actions(db, acc, rm)] == ["reopen"]
    with pytest.raises(HTTPException) as e:
        account_service.update_account(db, acc.id, AccountUpdate(nature_of_business="x"), rm)
    assert e.value.status_code == 409 and "Reopen" in e.value.detail
    with pytest.raises(HTTPException) as e:  # its name stays taken, and the RM is told why
        account_service.create_account(db, AccountCreate(company_name="Complete Co", anchor_entity="TCPL", spoc_id=rm.id), rm)
    assert "dropped" in e.value.detail
    wf.change_status(db, acc, rm, "reopen")
    assert (acc.profile_status, acc.status_reason_code) == ("WIP", None)
    account_service.update_account(db, acc.id, AccountUpdate(nature_of_business="Back on"), rm)


def test_the_final_approver_rejects_and_the_rm_drops(db, people):
    rm = people["maker"]
    acc = flow.complete_client(db, rm)
    flow.submit(db, acc, rm)
    flow.compliance_approve(db, acc, people["checker"])
    wf.reject(db, acc, people["approver"], "Documents missing or incomplete", "Source of funds not evidenced")
    wf.change_status(db, acc, rm, "drop", "Client cannot evidence the source of funds", "Rejected and not pursued")
    assert acc.profile_status == "Dropped" and acc.client_id is None


def test_dashboard_counts_on_hold_as_being_prepared_and_lists_the_new_statuses(db, people):
    rm = people["maker"]
    acc = flow.complete_client(db, rm)
    wf.change_status(db, acc, rm, "hold")
    d = dashboard_service.build_dashboard(db, rm)
    assert d["kpis"]["clients_in_progress"] == 1
    counts = {s["status"]: s["count"] for s in d["client_status_breakdown"]}
    assert counts["On Hold"] == 1 and {"Pending with Client", "Pending with Regn Authority", "Dropped"} <= set(counts)


# ─── Reports (UAT 18-11-2026 rows 92-147) ───────────────────────────────────────────────────────────────

def test_onboarding_reports_split_approved_from_the_rest_with_dates_status_and_department(db, make_user, make_account):
    from datetime import timedelta
    from app.models import Department, UserRole
    from app.services import standard_reports_service as rpt
    sales, ops = Department(name="Sales"), Department(name="Ops")
    db.add_all([sales, ops])
    db.commit()
    admin = make_user("Ada", role=UserRole.ADMIN)
    rita = make_user("Rita RM", department_id=sales.id)
    otto = make_user("Otto RM", department_id=ops.id)
    now = datetime.now(timezone.utc)
    make_account(name="Approved Co", spoc=rita, anchor_entity="TCPL", profile_status="Active", approved_at=now,
                 licensing_authority="DMCC", is_regulated=False, nature_of_services_sought=["Audit Services"])
    make_account(name="Old Approved Co", spoc=rita, profile_status="Approved", approved_at=now - timedelta(days=90))
    make_account(name="Waiting Co", spoc=rita, profile_status="Pending with Client", status_reason="Passport copies")
    make_account(name="Paused Co", spoc=otto, profile_status="On Hold")

    approved = rpt.run(db, admin, "onboarding-approved", date_from=rpt._today() - timedelta(days=30))
    [row] = approved["rows"]
    assert approved["columns"][:10] == ["Anchor Triam Entity", "Pros ID", "Anchor RM", "Source", "Assigned Date", "Client Name",
                                        "Regn Authority", "Regulator", "Services applied", "Status"]
    assert (row[0], row[2], row[5], row[6], row[7], row[8], row[9]) == (
        "TCPL", "Rita RM", "Approved Co", "DMCC", "Not regulated", "Audit Services", "Active")

    rest = rpt.run(db, admin, "onboarding-in-progress")
    assert {r[5] for r in rest["rows"]} == {"Waiting Co", "Paused Co"}
    only = rpt.run(db, admin, "onboarding-in-progress", status="Pending with Client")["rows"]
    assert [(r[5], r[-1]) for r in only] == [("Waiting Co", "Passport copies")]
    assert [r[5] for r in rpt.run(db, admin, "onboarding-in-progress", department_id=ops.id)["rows"]] == ["Paused Co"]
    assert [r[5] for r in rpt.run(db, rita, "onboarding-in-progress")["rows"]] == ["Waiting Co"]  # an RM sees their own


def test_aml_review_reports_due_in_n_days_and_expired(db, make_user, make_account):
    from datetime import timedelta
    from app.services import standard_reports_service as rpt
    rm = make_user("Rita RM")
    today = rpt._today()
    make_account(name="Due Soon", spoc=rm, profile_status="Active", anchor_entity="TCPL", next_aml_review_date=today + timedelta(days=10))
    make_account(name="Due Later", spoc=rm, profile_status="Active", next_aml_review_date=today + timedelta(days=50))
    make_account(name="Expired", spoc=rm, profile_status="Approved", next_aml_review_date=today - timedelta(days=3))
    make_account(name="Still Onboarding", spoc=rm, profile_status="WIP", next_aml_review_date=today - timedelta(days=3))
    due = rpt.run(db, rm, "aml-reviews-due", days=30)
    assert [(r[0], r[3], r[5]) for r in due["rows"]] == [("TCPL", "Due Soon", 10)]
    assert [r[3] for r in rpt.run(db, rm, "aml-reviews-due", days=60)["rows"]] == ["Due Soon", "Due Later"]
    assert [(r[3], r[5]) for r in rpt.run(db, rm, "aml-reviews-expired")["rows"]] == [("Expired", 3)]
    risk = rpt.run(db, rm, "clients-risk")
    assert risk["columns"][-1] == "Days overdue" and "Still Onboarding" not in {r[2] for r in risk["rows"]}


def test_report_days_must_be_sensible(db, make_user):
    import pytest
    from fastapi import HTTPException
    from app.services import standard_reports_service as rpt
    with pytest.raises(HTTPException):
        rpt.run(db, make_user("Rita RM"), "aml-reviews-due", days=-1)
