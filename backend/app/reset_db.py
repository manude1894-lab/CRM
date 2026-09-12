"""Wipe all operational data, leaving a clean CRM ready for a manual walkthrough.

KEEPS:
  - the 4 TRIAM login users (creates them if missing)
  - the AML country-risk reference table (re-seeds it if empty)

REMOVES everything else: accounts, cases, directors, shareholders, UBOs,
CDD records + document checklists, company profiles, compliance schedules,
AML risk assessments, instructions, invoices, activities, notifications.

Usage:
    python -m app.reset_db
"""
from sqlalchemy import text

from app.database import SessionLocal, engine, Base
import app.models  # noqa: F401 — register every table on Base.metadata
from app.models import User, UserRole
from app.auth.security import hash_password
from app.services.aml_service import seed_country_risk

TRIAM_USERS = [
    ("Shirsendu Mukherjee", "shirsendu@triam.ae", "admin123", UserRole.ADMIN),
    ("Kalyan", "kalyan@triam.ae", "rm123", UserRole.RM),
    ("Ritu Sharma", "ritu@triam.ae", "ops123", UserRole.OPS),
    ("Swathi", "swathi@triam.ae", "screen123", UserRole.SCREENING),
]

# Child-before-parent so plain DELETEs never trip a foreign-key check.
_TABLES_TO_CLEAR = [
    "documents",
    "aml_risk_assessments",
    "pep_assessments",
    "action_points",
    "case_documents",
    "cdd_records",
    "company_profiles",
    "entity_lifecycle",
    "formation_records",
    "compliance_schedules",
    "service_feedback",
    "service_subscriptions",
    "instructions",
    "invoices",
    "directors",
    "shareholders",
    "ubos",
    "activities",
    "notifications",
    "case_relationship_managers",
    "prospects",
    "cases",
    "accounts",
]


def main():
    Base.metadata.create_all(bind=engine)  # no-op if migrations already ran
    db = SessionLocal()
    try:
        print("-> Clearing operational tables...")
        for table in _TABLES_TO_CLEAR:
            try:
                db.execute(text(f"DELETE FROM {table}"))
            except Exception as exc:  # table may not exist on an older schema
                print(f"   (skipped {table}: {exc.__class__.__name__})")
        db.commit()

        n = seed_country_risk(db)
        print(f"-> AML country-risk table: {'seeded ' + str(n) + ' rows' if n else 'already present'}")

        print("-> Ensuring TRIAM login users...")
        existing = {u.email for u in db.query(User).all()}
        for name, email, pw, role in TRIAM_USERS:
            if email in existing:
                continue
            db.add(User(name=name, email=email, hashed_password=hash_password(pw), role=role, is_active=True))
        db.commit()

        print("\nCRM reset complete - 0 accounts / cases.")
        print("Login accounts retained:")
        for name, email, pw, role in TRIAM_USERS:
            print(f"  {role.value:10s}  {email:24s}  {pw}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
