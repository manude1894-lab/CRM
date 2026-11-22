"""Triam data review 21-11-2026: the report observations. Dates entered before a rule existed are caught at
Submit; an imported existing client needs its Anchor Triam Entity (for the Client ID) and sensible dates; and a
report lists every client whose data needs correcting."""
from datetime import date, datetime, timedelta, timezone

from app.schemas.account import AccountImportRow
from app.services import account_service, standard_reports_service as rpt

FUTURE = date(2099, 1, 1)


def test_submit_catches_a_licence_start_date_in_the_future(make_user, make_account):
    rm = make_user("Rita RM")
    acc = make_account(name="Far Future Ltd", spoc=rm, account_type="Corporate", license_start_date=FUTURE,
                       incorporation_date=date(2020, 1, 1))
    labels = [m["label"] for m in account_service.missing_mandatory(acc)]
    assert "License Start Date is in the future. Correct it" in labels


def test_import_needs_the_entity_for_an_existing_client_and_refuses_future_dates(db, make_user):
    admin = make_user("Ada Admin", role="admin")
    rows = [AccountImportRow(company_name="No Entity Ltd", profile_status="Active"),
            AccountImportRow(company_name="Time Travel Ltd", anchor_entity="TCPL", license_start_date=FUTURE),
            AccountImportRow(company_name="Good Ltd", anchor_entity="TCPL")]
    res = {r.company_name: r for r in account_service.import_accounts(db, admin, rows, dry_run=False)}
    assert res["No Entity Ltd"].status == "error" and "Anchor Triam Entity" in res["No Entity Ltd"].message
    assert res["Time Travel Ltd"].status == "error" and "future" in res["Time Travel Ltd"].message
    assert res["Good Ltd"].status == "ok"


def test_data_quality_report_lists_what_to_correct(db, make_user, make_account):
    admin = make_user("Ada Admin", role="admin")
    now = datetime.now(timezone.utc)
    make_account(name="Messy Ltd", account_type="Corporate", profile_status="Active", approved_at=now,
                 license_start_date=FUTURE, registration_number="1", is_pep=True, risk_rating="Medium",
                 edd_reason="Old reason", engagement_letter_signed=True, is_regulated=False, licensing_authority="DED")
    make_account(name="Clean Ltd", account_type="Corporate", profile_status="Active", approved_at=now, client_id="TCPL/00009",
                 risk_rating="Low", registration_number="CN-12345", license_number="L-777", is_regulated=False,
                 licensing_authority="DED", engagement_letter_signed=True, license_start_date=date.today() - timedelta(days=30))
    make_account(name="Draft Ltd", profile_status="WIP", license_start_date=FUTURE)  # still being filled in
    report = rpt.run(db, admin, "data-quality")
    by_name = {r[0]: r for r in report["rows"]}
    assert set(by_name) == {"Messy Ltd"}
    what = by_name["Messy Ltd"][-1]
    for expected in ("No Client ID", "Licence start date in the future", "Incorporation number looks too short",
                     "PEP with Medium risk", "EDD reason recorded but risk is Medium"):
        assert expected in what


def test_existing_clients_without_an_id_get_one(db, make_account):
    old = make_account(name="Old Active Ltd", anchor_entity="TCPL", profile_status="Active")
    no_entity = make_account(name="No Entity Ltd", profile_status="Active")
    draft = make_account(name="Draft Ltd", anchor_entity="TCPL", profile_status="WIP")
    assert account_service.issue_missing_client_ids(db) == 1
    db.refresh(old), db.refresh(no_entity), db.refresh(draft)
    assert old.client_id and not no_entity.client_id and not draft.client_id
    assert account_service.issue_missing_client_ids(db) == 0
