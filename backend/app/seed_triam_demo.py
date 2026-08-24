"""Seed the database with real Triam BVI entity data for the client demo.

Pulls actual entity names, instruction types, dates, charges and invoice
numbers from the Instruction Tracker (Annexure 7) Triam shared, so the demo
shows their own book of business rather than generic placeholder companies.
Director/Shareholder personal details are illustrative placeholders — Triam
did not share actual UBO names, only the entity-level tracker and templates.

Usage:
    python -m app.seed_triam_demo [--force]
"""
from datetime import date
from decimal import Decimal
from sqlalchemy.orm import Session

from app.database import SessionLocal, engine, Base
from app.models import (
    User, UserRole, Account, Priority,
    Case, CaseStage, CaseStatus, CaseSource, InvoiceStatus,
    CDDRecord, CaseDocument, DocumentStatus,
    Director, Shareholder,
    Instruction, InstructionStatus,
    Invoice, InvoiceLedgerStatus,
)
from app.auth.security import hash_password
from app.utils.uid import next_uid
from app.services.case_service import STANDARD_CDD_DOCUMENTS
from app.services.cdd_service import generate_director_documents, generate_shareholder_documents

DEMO_USERS = [
    {"name": "Shirsendu Mukherjee", "email": "shirsendu@triam.ae", "password": "admin123", "role": UserRole.ADMIN},
    {"name": "Kalyan", "email": "kalyan@triam.ae", "password": "rm123", "role": UserRole.RM},
    {"name": "Ritu Sharma", "email": "ritu@triam.ae", "password": "ops123", "role": UserRole.OPS},
    {"name": "Swathi", "email": "swathi@triam.ae", "password": "screen123", "role": UserRole.SCREENING},
]

# Real BVI entities from Triam's Instruction Tracker (Annexure 7).
ENTITIES = [
    "NAV Holdings Limited",
    "Kelca Investments",
    "Axiom Investments",
    "Castle Noble Holdings Limited",
    "Bluegold Holdings Limited",
    "Horizon Investments DXB",
    "Shreenath Ji Holdings LTD",
    "Oxford Bridge Holdings Limited",
    "Al Tayseer Group",
    "Le Couche Soleil Holdings Limited",
    "DRS Investment Limited",
    "Century Capital Advisors Ltd",
    "Bisley Capital Ltd",
    "Vogacloset Shareholders Limited",
    "Melton Park Ltd",
]

# Entities still mid-pipeline (from the tracker's "On hold" / new-formation rows),
# shown at earlier CRM stages so the Cases Kanban isn't flat "all Active".
PIPELINE_ENTITIES = [
    ("Vaidant", CaseStage.DOCS_REQUESTED, CaseStatus.DOCS_PENDING, "New BVI formation — client has gone quiet, no response to document request."),
    ("Skyblue Caerulean Holdings", CaseStage.CDD_KYC_IN_REVIEW, CaseStatus.ACTIVE, "New BVI formation (1 of 2 for this client group) — CDD/KYC in review with screening."),
]

# (entity, instruction_type, status, date_received, date_completed, charge, invoice_ref)
INSTRUCTIONS = [
    ("NAV Holdings Limited", "COI Issuance", "Completed", date(2023, 12, 19), date(2023, 12, 19), None, None),
    ("NAV Holdings Limited", "COI Issuance", "Completed", date(2024, 11, 14), date(2024, 11, 14), 130, None),
    ("Kelca Investments", "COI & COGS Issuance", "Completed", date(2024, 1, 24), date(2024, 1, 24), None, "2024-TCS-00035"),
    ("Kelca Investments", "Change in Directors", "Completed", date(2024, 9, 24), date(2024, 9, 24), None, "2024-TCS-00035"),
    ("Kelca Investments", "Notarization / Apostille", "Completed", date(2024, 9, 30), date(2024, 9, 30), 900, "2024-TCS-00035"),
    ("Kelca Investments", "Notarization / Apostille", "Completed", date(2024, 10, 1), date(2024, 11, 7), 7100, "2024-TCS-00035"),
    ("Axiom Investments", "COI & COGS Issuance", "Completed", date(2024, 1, 24), date(2024, 1, 24), None, "2024-TCS-00034"),
    ("Axiom Investments", "Change in Directors", "Completed", date(2024, 9, 24), date(2024, 9, 24), None, "2024-TCS-00034"),
    ("Axiom Investments", "Notarization / Apostille", "Completed", date(2024, 10, 1), date(2024, 11, 7), 7100, "2024-TCS-00034"),
    ("Castle Noble Holdings Limited", "LEI Renewal", "Completed", date(2024, 9, 17), date(2024, 9, 17), 60, None),
    ("Castle Noble Holdings Limited", "COGS Issuance", "Completed", date(2024, 9, 5), date(2024, 9, 13), 255, None),
    ("Castle Noble Holdings Limited", "ROM/RBO Filing", "Completed", date(2025, 11, 11), date(2025, 11, 11), 150, None),
    ("Bluegold Holdings Limited", "Notarization / Apostille", "Completed", date(2024, 7, 9), date(2024, 7, 9), None, "2024-TCS-00033"),
    ("Bluegold Holdings Limited", "Change in Shareholding", "Completed", None, None, None, None),
    ("Horizon Investments DXB", "New BVI Formation", "Completed", date(2024, 4, 1), date(2024, 6, 3), None, "2024-TCS-00017"),
    ("Horizon Investments DXB", "Change in Shareholding", "Completed", date(2025, 4, 7), date(2025, 7, 14), 355, None),
    ("Shreenath Ji Holdings LTD", "COI Issuance", "Completed", date(2024, 8, 5), date(2024, 8, 5), 130, "2024-TCS-00025"),
    ("Shreenath Ji Holdings LTD", "AR Filing", "Pending", None, None, 500, None),
    ("Oxford Bridge Holdings Limited", "COI Issuance", "Completed", date(2025, 4, 9), date(2025, 4, 10), 270, None),
    ("Al Tayseer Group", "COI Issuance", "Completed", date(2025, 4, 23), date(2025, 4, 23), 135, None),
    ("Al Tayseer Group", "ROM/RBO Filing", "Completed", date(2025, 11, 11), date(2025, 11, 11), 150, None),
    ("Le Couche Soleil Holdings Limited", "COI Issuance", "Completed", date(2025, 5, 4), date(2025, 5, 5), 135, None),
    ("Le Couche Soleil Holdings Limited", "COGS Issuance", "Completed", date(2025, 10, 29), date(2025, 10, 29), 265, None),
    ("DRS Investment Limited", "New BVI Formation", "Completed", None, None, None, "2024-TCS-00038"),
    ("DRS Investment Limited", "AR Filing", "Pending", None, None, None, None),
    ("Century Capital Advisors Ltd", "AR Filing", "Completed", None, None, 500, None),
    ("Century Capital Advisors Ltd", "ROM/RBO Filing", "Completed", date(2025, 11, 11), date(2025, 11, 11), 150, None),
    ("Bisley Capital Ltd", "AR Filing", "Completed", None, None, None, None),
    ("Bisley Capital Ltd", "ROM/RBO Filing", "Completed", date(2025, 11, 11), date(2025, 11, 11), 150, None),
    ("Vogacloset Shareholders Limited", "LEI Renewal", "Completed", date(2025, 1, 30), date(2025, 1, 30), 40, None),
    ("Vogacloset Shareholders Limited", "ROM/RBO Filing", "Pending", None, None, None, None),
    ("Melton Park Ltd", "Transfer & Restoration to Vistra", "Completed", None, None, 6825, None),
    ("Melton Park Ltd", "ESR Filings to be completed on Vistra portal", "Pending", None, None, None, None),
]

# (entity, invoice_number, description, amount, status, raised_date)
INVOICES = [
    ("Kelca Investments", "2024-TCS-00035", "Director change, notarization, apostille & legalization", 8000, "Paid", date(2024, 9, 30)),
    ("Axiom Investments", "2024-TCS-00034", "Director change, notarization, apostille & legalization", 7100, "Paid", date(2024, 9, 30)),
    ("Bluegold Holdings Limited", "2024-TCS-00033", "COI notarization and apostille", 500, "Paid", date(2024, 7, 9)),
    ("Horizon Investments DXB", "2024-TCS-00017", "New BVI company formation", 1895, "Paid", date(2024, 6, 3)),
    ("Shreenath Ji Holdings LTD", "2024-TCS-00025", "COI issuance", 130, "Paid", date(2024, 8, 5)),
    ("DRS Investment Limited", "2024-TCS-00038", "New BVI company formation", 1420, "Raised", date(2024, 11, 8)),
    ("Melton Park Ltd", None, "Transfer and restoration to Vistra", 6825, "Paid", date(2025, 6, 1)),
]

# Illustrative placeholder register data (Triam did not share real UBO names).
DIRECTORS = {
    "Kelca Investments": [
        {"director_type": "Individual", "first_name": "Rajesh", "last_name": "Kumar", "nationality": "Indian",
         "appointment_date": date(2023, 6, 1), "residential_country": "India", "residential_city": "Mumbai"},
        {"director_type": "Corporate", "corporate_name": "Kelca Nominee Services Ltd", "country_of_incorporation": "BVI",
         "appointment_date": date(2023, 6, 1)},
    ],
    "Castle Noble Holdings Limited": [
        {"director_type": "Individual", "first_name": "Elena", "last_name": "Volkova", "nationality": "Russian",
         "appointment_date": date(2019, 5, 6), "residential_country": "UAE", "residential_city": "Dubai"},
    ],
    "NAV Holdings Limited": [
        {"director_type": "Individual", "first_name": "Vikram", "last_name": "Nair", "nationality": "Indian",
         "appointment_date": date(2022, 3, 15), "residential_country": "UAE", "residential_city": "Dubai"},
    ],
}

SHAREHOLDERS = {
    "Kelca Investments": [
        {"identification_type": "Individual", "name": "Rajesh Kumar", "number_of_shares": 100,
         "share_class": "Ordinary", "shareholding_percent": 100, "date_entered": date(2023, 6, 1)},
    ],
    "Castle Noble Holdings Limited": [
        {"identification_type": "Individual", "name": "Elena Volkova", "number_of_shares": 8500,
         "share_class": "Ordinary", "shareholding_percent": 85, "date_entered": date(2019, 5, 6)},
        {"identification_type": "Individual", "name": "Minor Holder — under review", "number_of_shares": 1500,
         "share_class": "Ordinary", "shareholding_percent": 15, "date_entered": date(2019, 5, 6)},
    ],
    "NAV Holdings Limited": [
        {"identification_type": "BC Company", "name": "NAV Family Trust Holdings Ltd", "country_of_incorporation": "BVI",
         "number_of_shares": 5000, "share_class": "Ordinary", "shareholding_percent": 100, "date_entered": date(2022, 3, 15)},
    ],
}


def seed(db: Session, force: bool = False):
    if not force and db.query(User).filter(User.email.like("%@triam.ae")).count() > 0:
        print("Triam demo seed skipped: already seeded. Pass --force to re-seed.")
        return

    print("-> Creating Triam team users...")
    users_by_name: dict[str, User] = {}
    for u in DEMO_USERS:
        existing = db.query(User).filter(User.email == u["email"]).first()
        if existing:
            users_by_name[u["name"]] = existing
            continue
        user = User(name=u["name"], email=u["email"], hashed_password=hash_password(u["password"]), role=u["role"], is_active=True)
        db.add(user)
        db.flush()
        users_by_name[u["name"]] = user

    rm = users_by_name["Kalyan"]

    print("-> Creating BVI entities (accounts + cases)...")
    cases_by_name: dict[str, Case] = {}
    for name in ENTITIES:
        acc = Account(
            account_uid=next_uid(db, Account, "account_uid", "ACC"),
            company_name=name, industry="Holding Company", country="BVI",
            strategic_priority=Priority.MEDIUM, existing_relationship="Yes",
            key_contacts="Managed via Vistra (Registered Agent)",
            owner_id=rm.id,
        )
        db.add(acc)
        db.flush()

        case = Case(
            case_uid=next_uid(db, Case, "case_uid", "CASE"),
            account_id=acc.id, rm_id=rm.id, ops_owner_id=users_by_name["Ritu Sharma"].id,
            company_name=name, source=CaseSource.REFERRAL,
            jurisdiction="BVI", service_type="Company Formation",
            stage=CaseStage.ACTIVE, status=CaseStatus.ACTIVE,
            # These are already-formed, active entities — their one-time formation
            # invoice (this legacy field, distinct from the ongoing Invoice ledger
            # below) was settled long ago.
            invoice_status=InvoiceStatus.PAID, invoice_amount=Decimal("1895"),
            invoice_raised_date=date(2022, 1, 15), invoice_paid_date=date(2022, 1, 20),
            license_received_date=date(2022, 1, 20),
        )
        db.add(case)
        db.flush()
        cases_by_name[name] = case

        # Entities with a director/shareholder register are shown as mid periodic-
        # CDD-refresh (a real, recurring obligation per the process manual) so the
        # per-party checklist grouping is actually reachable from the CDD queue.
        has_register = name in DIRECTORS or name in SHAREHOLDERS
        cdd = CDDRecord(
            case_id=case.id,
            cdd_form_status=DocumentStatus.SUBMITTED if has_register else DocumentStatus.NOT_STARTED,
            kyc_verification_status=DocumentStatus.UNDER_REVIEW if has_register else DocumentStatus.NOT_STARTED,
        )
        db.add(cdd)
        db.flush()
        for doc_type in STANDARD_CDD_DOCUMENTS:
            db.add(CaseDocument(cdd_record_id=cdd.id, doc_type=doc_type, received=True, received_date=date(2023, 1, 1)))
    db.commit()

    print("-> Adding mid-pipeline entities (Kanban variety)...")
    for name, stage, status, notes in PIPELINE_ENTITIES:
        acc = Account(
            account_uid=next_uid(db, Account, "account_uid", "ACC"),
            company_name=name, industry="Holding Company", country="BVI",
            strategic_priority=Priority.MEDIUM, existing_relationship="No",
            key_contacts="New formation — introduced to Vistra",
            owner_id=rm.id,
        )
        db.add(acc)
        db.flush()
        case = Case(
            case_uid=next_uid(db, Case, "case_uid", "CASE"),
            account_id=acc.id, rm_id=rm.id,
            company_name=name, source=CaseSource.REFERRAL,
            jurisdiction="BVI", service_type="Company Formation",
            stage=stage, status=status, notes=notes,
        )
        db.add(case)
        db.flush()
        cases_by_name[name] = case
        cdd = CDDRecord(case_id=case.id)
        db.add(cdd)
        db.flush()
        for doc_type in STANDARD_CDD_DOCUMENTS:
            db.add(CaseDocument(cdd_record_id=cdd.id, doc_type=doc_type, received=False))
    db.commit()

    print("-> Adding director & shareholder registers (illustrative)...")
    for entity, directors in DIRECTORS.items():
        case = cases_by_name[entity]
        for d in directors:
            director = Director(case_id=case.id, **d)
            db.add(director)
            db.flush()
            generate_director_documents(db, director)
    for entity, shareholders in SHAREHOLDERS.items():
        case = cases_by_name[entity]
        for s in shareholders:
            shareholder = Shareholder(case_id=case.id, **s)
            db.add(shareholder)
            db.flush()
            generate_shareholder_documents(db, shareholder)
    db.commit()

    print("-> Raising invoices...")
    invoices_by_key: dict[str, Invoice] = {}
    for entity, inv_num, desc, amount, status, raised in INVOICES:
        case = cases_by_name[entity]
        inv = Invoice(
            case_id=case.id, invoice_number=inv_num, description=desc,
            amount=Decimal(str(amount)), status=status, raised_date=raised,
            paid_date=raised if status == "Paid" else None,
        )
        db.add(inv)
        db.flush()
        invoices_by_key[f"{entity}|{inv_num}"] = inv
    db.commit()

    print("-> Logging instructions from the real tracker...")
    for entity, itype, status, received, completed, charge, inv_ref in INSTRUCTIONS:
        case = cases_by_name[entity]
        linked_invoice = invoices_by_key.get(f"{entity}|{inv_ref}") if inv_ref else None
        db.add(Instruction(
            case_id=case.id, instruction_type=itype, status=status,
            date_received=received, date_completed=completed,
            charge_amount=Decimal(str(charge)) if charge is not None else None,
            invoice_reference=inv_ref, invoice_id=linked_invoice.id if linked_invoice else None,
        ))
    db.commit()

    print(f"\nSeeded: {len(DEMO_USERS)} Triam users, {len(ENTITIES)} BVI entities, "
          f"{sum(len(v) for v in DIRECTORS.values())} directors, {sum(len(v) for v in SHAREHOLDERS.values())} shareholders, "
          f"{len(INSTRUCTIONS)} instructions, {len(INVOICES)} invoices.")
    print("\nDemo login credentials:")
    for u in DEMO_USERS:
        print(f"  {u['role'].value:10s}  {u['email']:30s}  {u['password']}")


def main():
    import sys
    force = "--force" in sys.argv
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed(db, force=force)
    finally:
        db.close()


if __name__ == "__main__":
    main()
