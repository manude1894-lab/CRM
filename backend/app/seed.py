"""Seed database with demo users and a realistic DIFC client-onboarding dataset.

Usage:
    python -m app.seed [--force]
"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from sqlalchemy.orm import Session

from app.database import SessionLocal, engine, Base
from app.models import (
    User, UserRole, Account, Priority,
    Case, CaseStage, CaseStatus, CaseSource, InvoiceStatus,
    CDDRecord, CaseDocument, DocumentStatus,
    ComplianceSchedule, Notification,
    Activity, ActivityType, ActivityStatus,
)
from app.auth.security import hash_password

today = date.today()


def days_ago(n: int) -> date:
    return today - timedelta(days=n)


def days_from_now(n: int) -> date:
    return today + timedelta(days=n)


DEMO_USERS = [
    {"name": "Admin User", "email": "admin@ezeetechgroup.com", "password": "admin123", "role": UserRole.ADMIN},
    {"name": "Aisha Al Mansoori", "email": "aisha@ezeetechgroup.com", "password": "rm123", "role": UserRole.RM},
    {"name": "Imran Qureshi", "email": "imran@ezeetechgroup.com", "password": "rm123", "role": UserRole.RM},
    {"name": "Fatima Noor", "email": "fatima@ezeetechgroup.com", "password": "ops123", "role": UserRole.OPS},
    {"name": "David Kerr", "email": "david@ezeetechgroup.com", "password": "screen123", "role": UserRole.SCREENING},
]


ACCOUNTS = [
    {"uid": "ACC-0001", "company": "Meridian Capital Partners", "industry": "Family Office", "country": "UAE", "priority": "High", "existing": "No", "contacts": "Karim Haddad, Managing Partner"},
    {"uid": "ACC-0002", "company": "Alpine Fintech Solutions", "industry": "Fintech", "country": "UK", "priority": "High", "existing": "No", "contacts": "Emily Foster, CEO"},
    {"uid": "ACC-0003", "company": "Zenith Wealth Advisors", "industry": "Wealth Management", "country": "UAE", "priority": "Medium", "existing": "Yes", "contacts": "Rashid Al Naqbi, Director"},
    {"uid": "ACC-0004", "company": "Crescent Trading LLC", "industry": "Trading", "country": "UAE", "priority": "Medium", "existing": "No", "contacts": "Omar Khalil, Owner"},
    {"uid": "ACC-0005", "company": "Orion Consulting Group", "industry": "Consulting", "country": "USA", "priority": "Medium", "existing": "No", "contacts": "Laura Bennett, Partner"},
    {"uid": "ACC-0006", "company": "Falcon Asset Management", "industry": "Asset Management", "country": "UAE", "priority": "High", "existing": "No", "contacts": "Yousef Al Marri, CIO"},
    {"uid": "ACC-0007", "company": "NorthBridge Family Office", "industry": "Family Office", "country": "Singapore", "priority": "High", "existing": "No", "contacts": "Wei Ling Tan, Trustee"},
    {"uid": "ACC-0008", "company": "Vantage Insurance Brokers", "industry": "Insurance", "country": "UK", "priority": "Medium", "existing": "No", "contacts": "Sophie Clarke, Director"},
    {"uid": "ACC-0009", "company": "Hexagon Holdings", "industry": "Holding Company", "country": "UAE", "priority": "Medium", "existing": "Yes", "contacts": "Faisal Al Rumaithi, Chairman"},
    {"uid": "ACC-0010", "company": "Silverline Advisory", "industry": "Advisory", "country": "India", "priority": "Low", "existing": "No", "contacts": "Anjali Mehta, Founder"},
]

DOC_TYPES = ["Passport Copy", "Proof of Address", "Company Incorporation Certificate", "Source of Funds Declaration", "KYC Questionnaire"]


def _docs_for(received_count: int):
    docs = []
    for i, doc_type in enumerate(DOC_TYPES):
        received = i < received_count
        docs.append({"doc_type": doc_type, "received": received, "received_date": days_ago(10 - i) if received else None})
    return docs


CASES = [
    {"uid": "CASE-0001", "acc": "ACC-0001", "source": CaseSource.SENIOR_MGMT, "stage": CaseStage.NEW_INQUIRY, "status": CaseStatus.ACTIVE, "rm": None, "ops": None, "docs": _docs_for(0), "cdd": (DocumentStatus.NOT_STARTED, DocumentStatus.NOT_STARTED), "notes": "Inbound referral from senior management — awaiting RM assignment."},
    {"uid": "CASE-0002", "acc": "ACC-0002", "source": CaseSource.SOCIAL_MEDIA, "stage": CaseStage.RM_ASSIGNED, "status": CaseStatus.ACTIVE, "rm": "Aisha Al Mansoori", "ops": None, "docs": _docs_for(0), "cdd": (DocumentStatus.NOT_STARTED, DocumentStatus.NOT_STARTED), "notes": "Found us via LinkedIn campaign. RM assigned, doc request pending."},
    {"uid": "CASE-0003", "acc": "ACC-0003", "source": CaseSource.REFERRAL, "stage": CaseStage.DOCS_REQUESTED, "status": CaseStatus.ACTIVE, "rm": "Imran Qureshi", "ops": None, "docs": _docs_for(1), "cdd": (DocumentStatus.NOT_STARTED, DocumentStatus.NOT_STARTED), "notes": "Docs requested, client responsive so far."},
    {"uid": "CASE-0004", "acc": "ACC-0004", "source": CaseSource.OTHER, "stage": CaseStage.DOCS_REQUESTED, "status": CaseStatus.DOCS_PENDING, "rm": "Aisha Al Mansoori", "ops": None, "docs": _docs_for(1), "cdd": (DocumentStatus.NOT_STARTED, DocumentStatus.NOT_STARTED), "backdate_days": 8, "notes": "Client has gone quiet — 2 reminder emails sent, no response."},
    {"uid": "CASE-0005", "acc": "ACC-0005", "source": CaseSource.SENIOR_MGMT, "stage": CaseStage.CDD_KYC_IN_REVIEW, "status": CaseStatus.ACTIVE, "rm": "Imran Qureshi", "ops": None, "docs": _docs_for(5), "cdd": (DocumentStatus.SUBMITTED, DocumentStatus.SUBMITTED), "cdd_backdate_days": 5, "notes": "All docs in, forwarded to screening."},
    {"uid": "CASE-0006", "acc": "ACC-0006", "source": CaseSource.REFERRAL, "stage": CaseStage.CDD_KYC_IN_REVIEW, "status": CaseStatus.ACTIVE, "rm": "Aisha Al Mansoori", "ops": None, "docs": _docs_for(5), "cdd": (DocumentStatus.UNDER_REVIEW, DocumentStatus.UNDER_REVIEW), "cdd_backdate_days": 3, "notes": "Screening team actively reviewing KYC."},
    {"uid": "CASE-0007", "acc": "ACC-0007", "source": CaseSource.SOCIAL_MEDIA, "stage": CaseStage.CDD_APPROVED, "status": CaseStatus.ACTIVE, "rm": "Imran Qureshi", "ops": None, "docs": _docs_for(5), "cdd": (DocumentStatus.APPROVED, DocumentStatus.APPROVED), "notes": "CDD cleared — ready for invoicing."},
    {"uid": "CASE-0008", "acc": "ACC-0008", "source": CaseSource.REFERRAL, "stage": CaseStage.INVOICE_RAISED, "status": CaseStatus.ACTIVE, "rm": "Aisha Al Mansoori", "ops": None, "docs": _docs_for(5), "cdd": (DocumentStatus.APPROVED, DocumentStatus.APPROVED), "invoice_status": InvoiceStatus.RAISED, "invoice_amount": 45000, "invoice_raised_days_ago": 10, "notes": "Invoice overdue — follow up with client on payment."},
    {"uid": "CASE-0009", "acc": "ACC-0009", "source": CaseSource.SENIOR_MGMT, "stage": CaseStage.INVOICE_PAID, "status": CaseStatus.ACTIVE, "rm": "Imran Qureshi", "ops": None, "docs": _docs_for(5), "cdd": (DocumentStatus.APPROVED, DocumentStatus.APPROVED), "invoice_status": InvoiceStatus.PAID, "invoice_amount": 38000, "invoice_raised_days_ago": 14, "invoice_paid_days_ago": 5, "notes": "Payment received — handing off to Ops."},
    {"uid": "CASE-0010", "acc": "ACC-0010", "source": CaseSource.OTHER, "stage": CaseStage.OPS_ASSIGNED, "status": CaseStatus.ACTIVE, "rm": "Aisha Al Mansoori", "ops": "Fatima Noor", "docs": _docs_for(5), "cdd": (DocumentStatus.APPROVED, DocumentStatus.APPROVED), "invoice_status": InvoiceStatus.PAID, "invoice_amount": 22000, "invoice_raised_days_ago": 25, "invoice_paid_days_ago": 18, "notes": "Ops preparing the regulator application package."},
    {"uid": "CASE-0011", "acc": "ACC-0001", "source": CaseSource.SENIOR_MGMT, "stage": CaseStage.APPLICATION_SUBMITTED, "status": CaseStatus.ACTIVE, "rm": "Imran Qureshi", "ops": "Fatima Noor", "docs": _docs_for(5), "cdd": (DocumentStatus.APPROVED, DocumentStatus.APPROVED), "invoice_status": InvoiceStatus.PAID, "invoice_amount": 50000, "invoice_raised_days_ago": 40, "invoice_paid_days_ago": 32, "notes": "Application submitted to DIFC — awaiting decision."},
    {"uid": "CASE-0012", "acc": "ACC-0002", "source": CaseSource.SOCIAL_MEDIA, "stage": CaseStage.LICENSE_RECEIVED, "status": CaseStatus.ACTIVE, "rm": "Aisha Al Mansoori", "ops": "Fatima Noor", "docs": _docs_for(5), "cdd": (DocumentStatus.APPROVED, DocumentStatus.APPROVED), "invoice_status": InvoiceStatus.PAID, "invoice_amount": 60000, "invoice_raised_days_ago": 90, "invoice_paid_days_ago": 80, "license_days_ago": 60, "renewal_in": 305, "compliance_in": 305, "tax_in": 305, "notes": "License received — annual compliance schedule created."},
    {"uid": "CASE-0013", "acc": "ACC-0003", "source": CaseSource.REFERRAL, "stage": CaseStage.ACTIVE, "status": CaseStatus.ACTIVE, "rm": "Imran Qureshi", "ops": "Fatima Noor", "docs": _docs_for(5), "cdd": (DocumentStatus.APPROVED, DocumentStatus.APPROVED), "invoice_status": InvoiceStatus.PAID, "invoice_amount": 42000, "invoice_raised_days_ago": 300, "invoice_paid_days_ago": 290, "license_days_ago": 280, "renewal_in": 20, "compliance_in": 45, "tax_in": 10, "notes": "Active client — renewal and filings approaching, within the 60-day reminder window."},
    {"uid": "CASE-0014", "acc": "ACC-0005", "source": CaseSource.OTHER, "stage": CaseStage.ACTIVE, "status": CaseStatus.ACTIVE, "rm": "Aisha Al Mansoori", "ops": "Fatima Noor", "docs": _docs_for(5), "cdd": (DocumentStatus.APPROVED, DocumentStatus.APPROVED), "invoice_status": InvoiceStatus.PAID, "invoice_amount": 33000, "invoice_raised_days_ago": 120, "invoice_paid_days_ago": 110, "license_days_ago": 100, "renewal_in": 265, "compliance_in": 265, "tax_in": 265, "notes": "Active client — no near-term filings due."},
    {"uid": "CASE-0015", "acc": "ACC-0006", "source": CaseSource.REFERRAL, "stage": CaseStage.CDD_KYC_IN_REVIEW, "status": CaseStatus.REJECTED, "rm": "Imran Qureshi", "ops": None, "docs": _docs_for(3), "cdd": (DocumentStatus.REJECTED, DocumentStatus.REJECTED), "rejection_reason": "Adverse media findings during screening; beneficial ownership could not be verified.", "notes": "Failed screening — case closed."},
]

ACTIVITIES = [
    {"case": "CASE-0002", "company": "Alpine Fintech Solutions", "date_ago": 6, "type": "Call", "summary": "Welcome call with new client, explained onboarding journey", "outcome": "Client onboarded smoothly", "next": "Send document checklist", "owner": "Aisha Al Mansoori"},
    {"case": "CASE-0003", "company": "Zenith Wealth Advisors", "date_ago": 4, "type": "Email", "summary": "Sent CDD form and KYC document checklist", "outcome": "Client acknowledged receipt", "next": "Follow up in 3 business days", "owner": "Imran Qureshi"},
    {"case": "CASE-0004", "company": "Crescent Trading LLC", "date_ago": 8, "type": "Email", "summary": "First reminder for outstanding documents", "outcome": "No response", "next": "Escalate via phone call", "owner": "Aisha Al Mansoori"},
    {"case": "CASE-0004", "company": "Crescent Trading LLC", "date_ago": 3, "type": "Call", "summary": "Follow-up call — voicemail left", "outcome": "No response", "next": "Final reminder before hold", "owner": "Aisha Al Mansoori"},
    {"case": "CASE-0005", "company": "Orion Consulting Group", "date_ago": 5, "type": "Note", "summary": "All CDD documents received and forwarded to screening", "outcome": "Forwarded to screening team", "next": "Await screening outcome", "owner": "Imran Qureshi"},
    {"case": "CASE-0006", "company": "Falcon Asset Management", "date_ago": 3, "type": "Note", "summary": "Screening flagged additional beneficial ownership check", "outcome": "Under review", "next": "Awaiting screening decision", "owner": "Aisha Al Mansoori"},
    {"case": "CASE-0007", "company": "NorthBridge Family Office", "date_ago": 2, "type": "Email", "summary": "Notified client that CDD/KYC has been approved", "outcome": "Client pleased, awaiting invoice", "next": "Coordinate with Admin on invoicing", "owner": "Imran Qureshi"},
    {"case": "CASE-0008", "company": "Vantage Insurance Brokers", "date_ago": 10, "type": "Email", "summary": "Invoice shared with client for licensing fees", "outcome": "Invoice sent", "next": "Follow up on payment — overdue", "owner": "Aisha Al Mansoori"},
    {"case": "CASE-0009", "company": "Hexagon Holdings", "date_ago": 5, "type": "Call", "summary": "Confirmed receipt of payment, briefed Ops handoff", "outcome": "Payment confirmed", "next": "Assign Ops owner", "owner": "Imran Qureshi"},
    {"case": "CASE-0010", "company": "Silverline Advisory", "date_ago": 9, "type": "Meeting", "summary": "Kickoff meeting with Ops on regulator application", "outcome": "Application package in progress", "next": "Submit application to DIFC", "owner": "Fatima Noor"},
    {"case": "CASE-0011", "company": "Meridian Capital Partners", "date_ago": 12, "type": "Note", "summary": "Application submitted to DIFC registrar", "outcome": "Submitted, pending decision", "next": "Monitor regulator response", "owner": "Fatima Noor"},
    {"case": "CASE-0012", "company": "Alpine Fintech Solutions", "date_ago": 60, "type": "Email", "summary": "License received — congratulated client, compliance calendar set up", "outcome": "License issued", "next": "Monitor renewal/compliance dates", "owner": "Fatima Noor"},
    {"case": "CASE-0013", "company": "Zenith Wealth Advisors", "date_ago": 30, "type": "Call", "summary": "Annual check-in call ahead of upcoming renewal", "outcome": "Client confirmed continuing engagement", "next": "Prepare renewal paperwork", "owner": "Imran Qureshi"},
    {"case": "CASE-0014", "company": "Orion Consulting Group", "date_ago": 45, "type": "Note", "summary": "Routine account review — no issues flagged", "outcome": "Healthy account", "next": "Next review in 6 months", "owner": "Aisha Al Mansoori"},
    {"case": "CASE-0015", "company": "Falcon Asset Management", "date_ago": 2, "type": "Email", "summary": "Informed client that onboarding could not proceed", "outcome": "Case rejected after screening", "next": "Archive case", "owner": "Imran Qureshi"},
]


def _backdate(obj, field: str, days: int, db: Session):
    """Set a timestamp column to N days ago, bypassing onupdate (explicit value wins)."""
    setattr(obj, field, datetime.now(timezone.utc) - timedelta(days=days))
    db.add(obj)
    db.commit()


def seed(db: Session, force: bool = False):
    if not force and db.query(User).count() > 0:
        print("Seed skipped: users already exist. Pass --force to re-seed.")
        return

    print("-> Creating users...")
    users_by_name: dict[str, User] = {}
    for u in DEMO_USERS:
        user = User(name=u["name"], email=u["email"], hashed_password=hash_password(u["password"]), role=u["role"], is_active=True)
        db.add(user)
        db.flush()
        users_by_name[u["name"]] = user

    print("-> Creating accounts...")
    accounts_by_uid: dict[str, Account] = {}
    for i, a in enumerate(ACCOUNTS):
        owner_name = "Aisha Al Mansoori" if i % 2 == 0 else "Imran Qureshi"
        acc = Account(
            account_uid=a["uid"], company_name=a["company"], industry=a["industry"], country=a["country"],
            strategic_priority=Priority(a["priority"]), existing_relationship=a["existing"], key_contacts=a["contacts"],
            owner_id=users_by_name[owner_name].id,
        )
        db.add(acc)
        db.flush()
        accounts_by_uid[a["uid"]] = acc

    print("-> Creating cases, CDD records & document checklists...")
    cases_by_uid: dict[str, Case] = {}
    backdate_jobs = []  # (obj, field, days) applied after initial commit
    for c in CASES:
        account = accounts_by_uid[c["acc"]]
        case = Case(
            case_uid=c["uid"],
            account_id=account.id,
            rm_id=users_by_name[c["rm"]].id if c["rm"] else None,
            ops_owner_id=users_by_name[c["ops"]].id if c["ops"] else None,
            company_name=account.company_name,
            source=c["source"],
            stage=c["stage"],
            status=c["status"],
            invoice_status=c.get("invoice_status", InvoiceStatus.NOT_RAISED),
            invoice_amount=Decimal(str(c.get("invoice_amount", 0))),
            invoice_raised_date=days_ago(c["invoice_raised_days_ago"]) if c.get("invoice_raised_days_ago") else None,
            invoice_paid_date=days_ago(c["invoice_paid_days_ago"]) if c.get("invoice_paid_days_ago") else None,
            license_received_date=days_ago(c["license_days_ago"]) if c.get("license_days_ago") else None,
            license_expiry_date=days_from_now(365 - c["license_days_ago"]) if c.get("license_days_ago") else None,
            notes=c["notes"],
        )
        db.add(case)
        db.flush()
        cases_by_uid[c["uid"]] = case

        if c.get("backdate_days"):
            backdate_jobs.append((case, "updated_at", c["backdate_days"]))

        cdd_form_status, kyc_status = c["cdd"]
        cdd = CDDRecord(
            case_id=case.id,
            cdd_form_status=cdd_form_status,
            kyc_verification_status=kyc_status,
            screening_reviewer_id=users_by_name["David Kerr"].id if cdd_form_status in (DocumentStatus.APPROVED, DocumentStatus.REJECTED) else None,
            reviewed_at=datetime.now(timezone.utc) - timedelta(days=1) if cdd_form_status in (DocumentStatus.APPROVED, DocumentStatus.REJECTED) else None,
            rejection_reason=c.get("rejection_reason"),
        )
        db.add(cdd)
        db.flush()

        if c.get("cdd_backdate_days"):
            backdate_jobs.append((cdd, "updated_at", c["cdd_backdate_days"]))

        for doc in c["docs"]:
            db.add(CaseDocument(cdd_record_id=cdd.id, doc_type=doc["doc_type"], received=doc["received"], received_date=doc["received_date"]))

        if c.get("renewal_in") is not None:
            db.add(ComplianceSchedule(
                case_id=case.id,
                renewal_due_date=days_from_now(c["renewal_in"]),
                compliance_filing_due_date=days_from_now(c["compliance_in"]),
                tax_filing_due_date=days_from_now(c["tax_in"]),
            ))

    db.commit()

    print("-> Backdating SLA-breach timestamps for the demo...")
    for obj, field, days in backdate_jobs:
        _backdate(obj, field, days, db)

    print("-> Creating activities...")
    for i, a in enumerate(ACTIVITIES):
        db.add(Activity(
            activity_uid=f"ACT-{i+1:04d}",
            case_id=cases_by_uid[a["case"]].id,
            owner_id=users_by_name[a["owner"]].id,
            company_name=a["company"],
            activity_date=days_ago(a["date_ago"]),
            activity_type=ActivityType(a["type"]),
            status=ActivityStatus.COMPLETED,
            summary=a["summary"],
            outcome=a["outcome"],
            next_action=a["next"],
        ))
    db.commit()

    print("-> Seeding notifications...")
    notifications = [
        (users_by_name["Aisha Al Mansoori"].id, cases_by_uid["CASE-0004"], "docs_pending_overdue", "Case CASE-0004 (Crescent Trading LLC) has been awaiting client documents for 5 business days.", False),
        (users_by_name["David Kerr"].id, cases_by_uid["CASE-0005"], "cdd_awaiting_screening", "CDD/KYC for case CASE-0005 (Orion Consulting Group) has awaited screening for 3 days.", False),
        (users_by_name["Admin User"].id, cases_by_uid["CASE-0008"], "invoice_unpaid", "Invoice for case CASE-0008 (Vantage Insurance Brokers) has been unpaid for 10 days.", False),
        (users_by_name["Fatima Noor"].id, cases_by_uid["CASE-0013"], "compliance_filing_due", "Compliance filing for case CASE-0013 (Zenith Wealth Advisors) is due in 45 days.", False),
        (users_by_name["Imran Qureshi"].id, cases_by_uid["CASE-0013"], "renewal_due", "Renewal for case CASE-0013 (Zenith Wealth Advisors) is due in 20 days.", True),
    ]
    for user_id, case, ntype, message, read in notifications:
        db.add(Notification(
            user_id=user_id, case_id=case.id, notification_type=ntype, message=message, link=f"/cases/{case.id}",
            read_at=datetime.now(timezone.utc) - timedelta(hours=2) if read else None,
        ))
    db.commit()

    print("-> Refreshing account statistics...")
    for acc in accounts_by_uid.values():
        acc_cases = [c for c in cases_by_uid.values() if c.account_id == acc.id]
        acc.total_cases = len(acc_cases)
        acc.total_invoiced_amount = sum((Decimal(c.invoice_amount) for c in acc_cases), Decimal(0))
    db.commit()

    print(f"\nSeeded: {len(DEMO_USERS)} users, {len(ACCOUNTS)} accounts, {len(CASES)} cases, "
          f"{len(ACTIVITIES)} activities, {len(notifications)} notifications.")
    print("\nDemo login credentials:")
    for u in DEMO_USERS:
        print(f"  {u['role'].value:10s}  {u['email']:30s}  {u['password']}")


def seed_minimal(db: Session):
    """Create only the admin user — no dummy cases, accounts or activities.
    Used for production / client deployments so the CRM starts empty."""
    if db.query(User).count() > 0:
        print("Seed skipped: users already exist.")
        return
    admin = User(
        name="Admin User",
        email="admin@ezeetechgroup.com",
        hashed_password=hash_password("admin123"),
        role=UserRole.ADMIN,
        is_active=True,
    )
    db.add(admin)
    db.commit()
    print("Created admin user: admin@ezeetechgroup.com / admin123")


def main():
    import sys
    force = "--force" in sys.argv
    minimal = "--minimal" in sys.argv

    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        if minimal:
            seed_minimal(db)
        else:
            if force:
                print("-> Clearing existing data...")
                for model in (Notification, Activity, ComplianceSchedule, CaseDocument, CDDRecord, Case, Account, User):
                    db.query(model).delete()
                db.commit()
            seed(db, force=force)
    finally:
        db.close()


if __name__ == "__main__":
    main()
