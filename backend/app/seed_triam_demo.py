"""Seed the database with real Triam BVI entity data for the client demo.

Pulls actual entity names, instruction types, dates, charges and invoice
numbers from the Instruction Tracker (Annexure 7) Triam shared, so the demo
shows their own book of business rather than generic placeholder companies.
Director/Shareholder personal details are illustrative placeholders — Triam
did not share actual UBO names, only the entity-level tracker and templates.

Usage:
    python -m app.seed_triam_demo [--force]
"""
from datetime import date, datetime, timezone
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
    AMLRiskAssessment, AMLSubjectType,
    CompanyProfile, ComplianceSchedule,
    EntityLifecycle, RestorationStatus, new_restoration_checklist,
    FormationRecord,
    ActionPoint, PEPAssessment,
)
from app.auth.security import hash_password
from app.utils.uid import next_uid
from app.services.case_service import STANDARD_CDD_DOCUMENTS
from app.services.cdd_service import generate_director_documents, generate_shareholder_documents
from app.services import aml_matrix, aml_service, compliance_service

DEMO_USERS = [
    {"name": "Shirsendu Mukherjee", "email": "shirsendu@triam.ae", "password": "admin123", "role": UserRole.ADMIN},
    {"name": "Kalyan", "email": "kalyan@triam.ae", "password": "rm123", "role": UserRole.RM},
    {"name": "Ritu Sharma", "email": "ritu@triam.ae", "password": "ops123", "role": UserRole.OPS},
    {"name": "Swathi", "email": "swathi@triam.ae", "password": "screen123", "role": UserRole.SCREENING},
]

# Real BVI entities from Triam's Instruction Tracker (Annexure 7), with the actual
# incorporation dates from the "Active RELs" sheet.
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

INCORP_DATES = {
    "NAV Holdings Limited": date(2020, 10, 6),
    "Kelca Investments": date(2021, 5, 31),
    "Axiom Investments": date(2021, 4, 29),
    "Castle Noble Holdings Limited": date(2017, 4, 28),
    "Bluegold Holdings Limited": date(2019, 9, 9),
    "Horizon Investments DXB": date(2024, 5, 21),
    "Shreenath Ji Holdings LTD": date(2019, 6, 20),
    "Oxford Bridge Holdings Limited": date(2019, 7, 23),
    "Al Tayseer Group": date(2022, 5, 17),
    "Le Couche Soleil Holdings Limited": date(2021, 11, 16),
    "DRS Investment Limited": date(2024, 10, 3),
    "Century Capital Advisors Ltd": date(2023, 2, 16),
    "Bisley Capital Ltd": date(2019, 5, 6),
    "Vogacloset Shareholders Limited": date(2021, 3, 23),
    "Melton Park Ltd": date(2013, 9, 24),
}

REGISTERED_AGENTS = {
    "Melton Park Ltd": "ILS Fiduciary",  # Mr Soltan's entities — transferring to Vistra
}

# Who introduced each entity to Triam (tracker's "introduced-by" column).
INTRODUCERS = {
    "Melton Park Ltd": "Mr Soltan (direct)",
    "Horizon Investments DXB": "Patton, Moreno & Asvat",
    "DRS Investment Limited": "Rosemont",
    "Vogacloset Shareholders Limited": "Client referral",
}

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
_APPX_A = lambda occ, emp, tax: {  # noqa: E731 — compact seed helper
    "occupation": occ, "employer_name": emp, "tax_residency_country": tax,
    "source_of_funds": "Salary and dividends", "source_of_wealth": "Accumulated employment income and business dividends.",
    "is_pep": False,
}

DIRECTORS = {
    "Kelca Investments": [
        {"director_type": "Individual", "first_name": "Rajesh", "last_name": "Kumar", "nationality": "Indian",
         "appointment_date": date(2023, 6, 1), "residential_country": "India", "residential_city": "Mumbai",
         "email": "rajesh.kumar@example.com", "mobile": "+91 98200 11223",
         **_APPX_A("Company director", "Kumar Textiles Pvt Ltd", "India")},
        {"director_type": "Corporate", "corporate_name": "Kelca Nominee Services Ltd", "country_of_incorporation": "BVI",
         "appointment_date": date(2023, 6, 1),
         "entity_details": {"entity_type": "Company", "regulated": False, "listed": False,
                            "ownership_summary": "Wholly owned by the Kelca group holding company.",
                            "directors_summary": "2 individual directors (group officers)."}},
    ],
    "Castle Noble Holdings Limited": [
        {"director_type": "Individual", "first_name": "Elena", "last_name": "Volkova", "nationality": "Russian",
         "appointment_date": date(2019, 5, 6), "residential_country": "UAE", "residential_city": "Dubai",
         "email": "elena.volkova@example.com", "mobile": "+971 50 111 2233",
         **_APPX_A("Business owner", "Volkova Trading FZE", "United Arab Emirates")},
    ],
    "NAV Holdings Limited": [
        {"director_type": "Individual", "first_name": "Vikram", "last_name": "Nair", "nationality": "Indian",
         "appointment_date": date(2022, 3, 15), "residential_country": "UAE", "residential_city": "Dubai",
         "email": "vikram.nair@example.com", "mobile": "+971 50 444 5566",
         **_APPX_A("Investment manager", "NAV Family Office", "United Arab Emirates")},
    ],
}

SHAREHOLDERS = {
    "Kelca Investments": [
        {"identification_type": "Individual", "name": "Rajesh Kumar", "number_of_shares": 100,
         "share_class": "Ordinary", "shareholding_percent": 100, "date_entered": date(2023, 6, 1),
         "email": "rajesh.kumar@example.com", **_APPX_A("Company director", "Kumar Textiles Pvt Ltd", "India")},
    ],
    "Castle Noble Holdings Limited": [
        {"identification_type": "Individual", "name": "Elena Volkova", "number_of_shares": 8500,
         "share_class": "Ordinary", "shareholding_percent": 85, "date_entered": date(2019, 5, 6),
         **_APPX_A("Business owner", "Volkova Trading FZE", "United Arab Emirates"),
         "charges": [{"chargee": "Emirates NBD Bank PJSC", "amount": "1500000", "currency": "USD",
                      "date_created": "2021-03-10", "date_satisfied": None, "status": "Outstanding"}]},
        {"identification_type": "Individual", "name": "Minor Holder — under review", "number_of_shares": 1500,
         "share_class": "Ordinary", "shareholding_percent": 15, "date_entered": date(2019, 5, 6)},
    ],
    "NAV Holdings Limited": [
        {"identification_type": "BC Company", "name": "NAV Family Trust Holdings Ltd", "country_of_incorporation": "BVI",
         "number_of_shares": 5000, "share_class": "Ordinary", "shareholding_percent": 100, "date_entered": date(2022, 3, 15),
         "is_nominee": True, "nominee_holds_for": "The Nair Family Trust",
         "nominator_name": "The Nair Family Trust (Vikram Nair, settlor)",
         "nominator_address": "DIFC, Dubai, United Arab Emirates",
         "nominator_relationship": "Trustee holding on behalf of the trust",
         "nominee_agreement_date": date(2022, 3, 15),
         "entity_details": {"entity_type": "Trust", "trust_name": "The Nair Family Trust", "trust_type": "Discretionary",
                            "trustee": "NAV Fiduciary Services Ltd", "settlor": "Vikram Nair",
                            "protector": "R. Menon", "governing_law": "DIFC",
                            "date_established": "2018-11-02",
                            "beneficiaries": ["Vikram Nair", "Anjali Nair", "Children of Vikram Nair"]}},
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
            introducer=INTRODUCERS.get(name, "Vistra"),
            onboarding_date=INCORP_DATES.get(name),
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

        incorp = INCORP_DATES.get(name)
        db.add(CompanyProfile(
            case_id=case.id,
            registered_agent=REGISTERED_AGENTS.get(name, "Vistra"),
            incorporation_date=incorp,
            company_number=None,
            name_check_status="Name Confirmed",
            authorised_shares=50000, par_value=Decimal("1.0000"), share_currency="USD",
            source_of_funds="Ultimate Beneficial Owner",
            nature_of_business="Investment holding - financial assets",
            business_countries="United Arab Emirates; United Kingdom; Singapore",
            key_counterparties="Private banks and licensed brokers; no cash-intensive counterparties.",
            asset_types="Listed equities, bonds, managed funds; one UAE residential property.",
            expected_annual_turnover="USD 250k - 1m (investment income)",
            expected_active_transactions="< 20 per year",
            company_secretary="None",
            es_financial_year_end="12-31", accounting_financial_year_end="12-31",
            act_certificate_of_incorporation=True, act_memorandum_articles=True,
            act_register_of_members=True, act_register_of_directors_stamped=True,
            act_company_stamp=True,
            activation_docs_received_date=incorp,
        ))
        db.flush()

        # Anchored compliance schedule (these entities are already Active).
        base = incorp or case.license_received_date
        db.add(ComplianceSchedule(
            case_id=case.id,
            renewal_due_date=compliance_service.next_anniversary(incorp) if incorp else None,
            esr_filing_due_date=compliance_service.next_30_september(),
            ar_filing_due_date=compliance_service.next_30_september(),
        ))
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

    print("-> Adding a sample UBO register...")
    from app.services.cdd_service import generate_ubo_documents
    from app.models import UBO
    cnh_ubo = None
    cnh_case = cases_by_name["Castle Noble Holdings Limited"]
    cnh_ubo = UBO(
        case_id=cnh_case.id, first_name="Elena", last_name="Volkova",
        nationality="Russian Federation (the)", country_of_residence="United Arab Emirates (the)",
        residential_city="Dubai", residential_country="UAE",
        percentage_interest=Decimal("100"), ownership_nature="Direct",
        nature_of_control="Sole shareholder and director",
        is_pep=False, employer_name="Volkova Trading FZE", job_title="Owner", sector="Trading",
        years_employed="8+ years",
        source_of_wealth_category="Business owner / entrepreneur",
        source_of_wealth_details="Founder and 100% owner of Volkova Trading FZE (Dubai) since 2016; "
                                 "dividends and accumulated profits from the trading business.",
        appointment_date=date(2019, 5, 6),
    )
    db.add(cnh_ubo)
    db.flush()
    generate_ubo_documents(db, cnh_ubo)
    db.commit()

    print("-> Attaching a sample document...")
    from app.models import Document, CaseDocument as _CD
    _sample = (
        b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[]/Count 0>>endobj\n"
        b"trailer<</Root 1 0 R>>\n%%EOF\n"
    )
    _ubo_passport_item = (
        db.query(_CD)
        .filter(_CD.ubo_id == cnh_ubo.id, _CD.doc_type.like("Passport%"))
        .first()
    )
    if _ubo_passport_item:
        db.add(Document(
            case_id=cnh_case.id, case_document_id=_ubo_passport_item.id,
            category="CDD", filename="Elena_Volkova_passport.pdf",
            content_type="application/pdf", size_bytes=len(_sample), content=_sample,
            uploaded_by_id=users_by_name["Swathi"].id,
            notes="Certified true copy — certified by Kalyan S., 2024-01-10",
        ))
        _ubo_passport_item.received = True
        _ubo_passport_item.received_date = date(2024, 1, 10)
        db.commit()

    print("-> Adding sample AML risk assessments...")
    _country_lu = aml_service._country_lookup(db)
    screening_user = users_by_name["Swathi"]

    def _add_assessment(case, subject_type, subject_name, selections, when, director=None, ubo=None):
        result = aml_matrix.calculate(subject_type, selections, _country_lu)
        db.add(AMLRiskAssessment(
            case_id=case.id, subject_type=subject_type, subject_name=subject_name,
            director_id=director.id if director else None,
            ubo_id=ubo.id if ubo else None,
            assessment_date=when, completed_by_id=screening_user.id,
            matrix_version=aml_matrix.AML_MATRIX_VERSION,
            factors=result.factors, total_weighted_score=result.total_weighted_score,
            calculated_rating=result.calculated_rating, override_reason=result.override_reason,
            onboarding_blocked=result.onboarding_blocked,
        ))
        return result

    cnh = cases_by_name["Castle Noble Holdings Limited"]
    entity_sel = {
        "country_incorporation": "British Virgin Islands",
        "country_operations": "United Arab Emirates (the)",
        "ubo_nationality": "Russian Federation (the)",
        "ubo_residence": "United Arab Emirates (the)",
        "customer_type": "Private limited company",
        "business_activity": "Non-cash intensive business",
        "customer_interface": "Face-to-Face KYC (Physical meeting)",
        "products_services": "Trust & Secretarial Services",
        "pep_risk": "Client/UBO is not a PEP",
        "proliferation_risk": "Client confirmed that he does not deal in any dual-use products as per UAE control list",
        "customer_introduction": "Known to the Firm or one of its employees for more than 3 yrs",
        "tax_crime_risk": "Customer does not fall into one of the medium or high risk factors",
        "reputational_risk": "No adverse information found",
        "business_risk": "Most recent AML Business Risk Assessment concluded overall risk as low",
    }
    r1 = _add_assessment(cnh, AMLSubjectType.ENTITY.value, cnh.company_name, entity_sel, date(2024, 1, 15))

    cnh_director = db.query(Director).filter(Director.case_id == cnh.id).first()
    if cnh_director:
        indiv_sel = {
            "country_nationality": "Russian Federation (the)",
            "country_residence": "United Arab Emirates (the)",
            "business_sector": "Business",
            "customer_interface": "Face-to-Face KYC (Physical meeting)",
            "products_services": "Management Consulting",
            "pep_risk": "Client/UBO is not a PEP",
            "proliferation_risk": "Client confirmed that he does not deal in any dual-use products as per UAE control list",
            "customer_introduction": "Known to the Firm or one of its employees for more than 3 yrs",
            "tax_crime_risk": "Customer does not fall into one of the medium or high risk factors",
            "reputational_risk": "No adverse information found",
            "business_risk": "Most recent AML Business Risk Assessment concluded overall risk as low",
        }
        _add_assessment(cnh, AMLSubjectType.INDIVIDUAL.value,
                        "Elena Volkova", indiv_sel, date(2024, 1, 15),
                        director=cnh_director, ubo=cnh_ubo)
    db.commit()
    aml_service._sync_cdd_rating(db, cnh.id)

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
            # Illustrative: Triam's cost to the registered agent ~65% of the client charge.
            cost_amount=(Decimal(str(charge)) * Decimal("0.65")).quantize(Decimal("1.00")) if charge is not None else None,
            invoice_reference=inv_ref, invoice_id=linked_invoice.id if linked_invoice else None,
        ))
    db.commit()

    print("-> Setting up entity-lifecycle demo states...")
    # Melton Park — lapsed under its prior agent (ILS), now being restored and
    # transferred to Vistra (matches the tracker's live "Transfer & Restoration" row).
    mp_case = cases_by_name["Melton Park Ltd"]
    mp_checklist = new_restoration_checklist()
    for item in mp_checklist:
        if item["key"] in ("ci", "rom", "rod", "moa", "indemnity_letter"):
            item["status"] = "Received"
    db.add(EntityLifecycle(
        case_id=mp_case.id,
        closure_method="Lapse by Non-Payment",
        closure_initiated_date=date(2024, 5, 1),
        closure_reason="Annual Licence Fee not paid by the prior registered agent.",
        outstanding_filings_cleared=False,
        strike_off_date=date(2024, 6, 30),
        expected_dissolution_date=date(2031, 6, 30),
        restoration_status=RestorationStatus.IN_PROGRESS.value,
        restoration_initiated_date=date(2025, 3, 1),
        strike_off_cause="Agent-related",
        restoration_checklist=mp_checklist,
        transfer_from_agent="ILS Fiduciary",
        transfer_to_agent="Vistra",
        transfer_initiated_date=date(2025, 3, 1),
        transfer_ends_administration=False,
        transfer_notes="Restoration application filed; RA transfer to Vistra to complete on restoration.",
    ))
    mp_case.status = CaseStatus.STRUCK_OFF.value

    # Oxford Bridge — client moved administration elsewhere (a "Closed REL").
    ob_case = cases_by_name["Oxford Bridge Holdings Limited"]
    db.add(EntityLifecycle(
        case_id=ob_case.id,
        restoration_checklist=new_restoration_checklist(),
        transfer_from_agent="Vistra",
        transfer_to_agent="Other",
        transfer_initiated_date=date(2025, 7, 1),
        transfer_completed_date=date(2025, 8, 15),
        transfer_ends_administration=True,
        transfer_notes="Client appointed an in-house administrator; Triam engagement closed.",
    ))
    ob_case.status = CaseStatus.TRANSFERRED_OUT.value
    db.commit()

    print("-> Setting up formation / Vistra-loop demo records...")
    screener = users_by_name["Swathi"]
    admin_user = users_by_name["Shirsendu Mukherjee"]

    # Skyblue — internal screening + MLRO done, file just went to Vistra.
    db.add(FormationRecord(
        case_id=cases_by_name["Skyblue Caerulean Holdings"].id,
        screening_status="Cleared", screening_date=date(2026, 8, 20),
        screened_by_id=screener.id, screening_tool="World-Check One",
        world_check_reference="WC1-2026-08-0417",
        screening_findings="No sanctions or adverse media. One low-relevance name match discounted (different DOB).",
        mlro_signoff_status="Signed Off", mlro_signoff_by_id=admin_user.id,
        mlro_signoff_at=datetime(2026, 8, 22, 9, 30, tzinfo=timezone.utc),
        mlro_signoff_notes="Standard-risk holding company. Cleared for submission to Vistra.",
        vistra_status="Submitted", vistra_submitted_date=date(2026, 8, 23),
        vistra_officer="Vistra BVI Compliance",
        kyc_pack_sent_date=date(2026, 8, 23),
    ))

    # Vaidant — screening under way, Vistra has come back with a query.
    db.add(FormationRecord(
        case_id=cases_by_name["Vaidant"].id,
        screening_status="In Progress", screening_date=date(2026, 8, 28),
        screened_by_id=screener.id, screening_tool="World-Check One",
        mlro_signoff_status="Pending",
        vistra_status="Query Raised",
        vistra_submitted_date=date(2026, 8, 25),
        vistra_query_text="Vistra requires a certified copy of the UBO passport and an updated structure chart showing the intermediate holding entity.",
        vistra_query_raised_date=date(2026, 8, 29),
        vistra_officer="Vistra BVI Compliance",
        kyc_pack_sent_date=date(2026, 8, 25),
    ))

    # Horizon Investments DXB — a completed formation (incorporated 2024-05-21).
    db.add(FormationRecord(
        case_id=cases_by_name["Horizon Investments DXB"].id,
        screening_status="Cleared", screening_date=date(2024, 4, 5),
        screened_by_id=screener.id, screening_tool="World-Check One",
        world_check_reference="WC1-2024-04-0088",
        screening_findings="No hits.",
        mlro_signoff_status="Signed Off", mlro_signoff_by_id=admin_user.id,
        mlro_signoff_at=datetime(2024, 4, 8, 10, 0, tzinfo=timezone.utc),
        vistra_status="Approved",
        vistra_submitted_date=date(2024, 4, 9), vistra_approved_date=date(2024, 4, 22),
        vistra_officer="Vistra BVI Compliance",
        kyc_pack_sent_date=date(2024, 4, 1),
        data_input_sheet_sent_date=date(2024, 4, 23),
        incorporation_submitted_date=date(2024, 5, 10),
        rod_filed_date=date(2024, 5, 28),
        registers_completed_date=date(2024, 6, 1),
        formation_completed_date=date(2024, 6, 3),
    ))
    db.commit()

    print("-> Adding Action Points (WIP board) + a PEP assessment + AR sub-workflow states...")
    ops_user = users_by_name["Ritu Sharma"]
    _ap = [
        ("Chase Vistra on Melton Park restoration filing", "In Progress", "High",
         "Melton Park Ltd", ops_user.id, date(2026, 9, 15)),
        ("Collect 2024 AR data for Century Capital", "Open", "Medium",
         "Century Capital Advisors Ltd", ops_user.id, date(2026, 9, 20)),
        ("Renew office lease — internal", "Open", "Low", None, admin_user.id, date(2026, 10, 1)),
        ("Draft revised fee schedule for 2027", "Open", "Medium", None, admin_user.id, None),
        ("File ROM/RBO for Vogacloset", "Done", "High", "Vogacloset Shareholders Limited",
         ops_user.id, date(2026, 8, 30)),
    ]
    for title, status, priority, entity, owner_id, due in _ap:
        db.add(ActionPoint(
            title=title, status=status, priority=priority,
            case_id=cases_by_name[entity].id if entity else None,
            owner_id=owner_id, created_by_id=admin_user.id, due_date=due,
            completed_date=date(2026, 8, 30) if status == "Done" else None,
        ))

    # Illustrative PEP assessment on the Castle Noble UBO.
    db.add(PEPAssessment(
        case_id=cnh_case.id, ubo_id=cnh_ubo.id, subject_name="Elena Volkova",
        pep_type="Family Member",
        position="Immediate family member of a former regional minister (illustrative)",
        pep_jurisdiction="Russian Federation (the)", still_in_office=False,
        family_and_associates="Spouse: business owner (Dubai). No other PEP connections identified.",
        source_of_wealth_scrutiny="SoW corroborated: 100% ownership of Volkova Trading FZE since 2016; "
                                  "audited accounts and dividend history reviewed.",
        edd_measures="Enhanced screening (World-Check + adverse-media), senior-management approval, "
                     "annual review cadence, source-of-funds evidence on each material transfer.",
        adverse_media_findings="None.",
        risk_conclusion="Proceed with EDD", senior_management_approved=True,
        approved_by_id=admin_user.id, approved_at=datetime(2024, 1, 16, 11, 0, tzinfo=timezone.utc),
        assessed_by_id=screener.id, assessment_date=date(2024, 1, 15),
    ))

    # AR sub-workflow: put two entities mid-cycle.
    for entity, ar_status in (("Century Capital Advisors Ltd", "Data Prepared"),
                              ("Bisley Capital Ltd", "Submitted to Vistra")):
        sched = db.query(ComplianceSchedule).filter(
            ComplianceSchedule.case_id == cases_by_name[entity].id).first()
        if sched:
            sched.ar_filing_status = ar_status
            sched.ar_reference_year = 2025
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
        n = aml_service.seed_country_risk(db)
        if n:
            print(f"-> Seeded AML country-risk table ({n} countries)")
        seed(db, force=force)
    finally:
        db.close()


if __name__ == "__main__":
    main()
