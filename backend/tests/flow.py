"""Test helpers for the new-client approval flow (BRD §7–§10):
RM submits → Compliance (MLRO) completes the CDD section and approves → Approver gives final approval."""
from datetime import date
from decimal import Decimal

from app.models import Document
from app.schemas.account import AccountCreate, AccountUpdate
from app.schemas.account_party import AccountPartyCreate
from app.services import account_service, account_party_service, client_workflow_service as wf


def submit(db, acc, user, comment="Client documents collected and checked"):
    return wf.submit(db, acc, user, comment, True)


def fill_cdd(db, acc, mlro, risk="Low"):
    account_service.update_account(db, acc.id, AccountUpdate(
        risk_rating=risk, kyc_verified_by="Rita RM", cdd_completion_date=date(2026, 9, 1),
        edd_reason="High-risk country" if risk == "High" else None), mlro)
    db.refresh(acc)


def compliance_approve(db, acc, mlro, comment="CDD complete and documents verified"):
    if account_service.missing_cdd(acc):
        fill_cdd(db, acc, mlro)
    return wf.approve(db, acc, mlro, comment)


def approve_all(db, acc, mlro, approver):
    compliance_approve(db, acc, mlro)
    return wf.approve(db, acc, approver, "Final approval given")


def complete_client(db, maker, with_document=True):
    """A Corporate client with every BRD mandatory field filled in (with_document=False: an empty folder,
    for tests about the folder itself)."""
    acc = account_service.create_account(db, AccountCreate(
        company_name="Complete Co", nature_of_business="Fintech", anchor_entity="TCPL", spoc_id=maker.id,
        country="United Arab Emirates", registration_number="CI-123", incorporation_date=date(2020, 1, 1),
        license_number="L-1", licensing_authority="DMCC", license_start_date=date(2024, 1, 1),
        license_expiry_date=date(2030, 1, 1), license_activities="Consulting", financial_year_end="12-31",
        services_obtained=["Accounting & Bookkeeping"], client_category="Existing",
        contact_mobile_country_code="+971", contact_mobile_number="43334444", contact_email="info@complete.example",
        nature_of_services_sought=["Accounting & Bookkeeping"],
        registered_address={"line1": "Office 1201, Tower A", "city": "Dubai", "country": "United Arab Emirates"},
        operating_address={"line1": "Office 1201, Tower A", "city": "Dubai", "country": "United Arab Emirates"},
        is_regulated=False, corp_tax_registered=False, has_introducer=False, engagement_letter_signed=False,
        br_person_met="Jane Owner", br_meeting_date=date(2026, 10, 1), br_meeting_time="10:30",
        br_meeting_place="Triam office, DIFC", br_meeting_mode="Face to Face",
        br_rationale="Fintech start-up needing accounting; company secretarial likely within two years.",
    ), maker)
    account_party_service.create_party(db, acc.id, AccountPartyCreate(
        party_role="Shareholder", country_of_residence="United Arab Emirates", nationality="United Arab Emirates", full_name="Jane Owner", mobile_country_code="+971", mobile_number="501234567", country_of_incorp_or_birth="India",
        residential_address={"line1": "Villa 12, Street 4", "city": "Dubai"},
        email="jane@example.com", effective_ownership_percent=Decimal("100"),
    ), maker)
    if with_document:
        add_document(db, acc, maker)
        db.refresh(acc)
        for party in acc.parties:
            add_document(db, acc, maker, filename="passport.pdf", party_id=party.id)
    db.refresh(acc)
    assert with_document is False or account_service.missing_mandatory(acc) == []
    return acc


def add_document(db, acc, user, **fields):
    """A supporting document filed on the client: at least one is needed to submit (UAT-02)."""
    fields = {"filename": "licence.pdf", **fields}
    doc = Document(account_id=acc.id, category="Other", content_type="application/pdf",
                   size_bytes=8, content=b"%PDF-1.4", uploaded_by_id=user.id, **fields)
    db.add(doc)
    db.commit()
    return doc


def approved_client(db, people):
    """A complete client taken through both approvals and activated."""
    acc = complete_client(db, people["maker"])
    submit(db, acc, people["maker"])
    approve_all(db, acc, people["checker"], people["approver"])
    wf.change_status(db, acc, people["maker"], "activate")
    return acc
