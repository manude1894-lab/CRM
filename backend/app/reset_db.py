"""Wipe all operational data, leaving a clean CRM ready for a manual walkthrough.

KEEPS: users, departments, roles, master lists and the country list.
REMOVES: prospects, clients and everything attached to them (parties, documents, approvals,
service requests, invoices, activities), notifications and the audit trail.

Usage:
    python -m app.reset_db
"""
from sqlalchemy import text

from app.database import SessionLocal

# Child-before-parent so plain DELETEs never trip a foreign-key check.
_TABLES_TO_CLEAR = [
    "documents",
    "instructions",
    "invoices",
    "activities",
    "notifications",
    "approval_requests",
    "account_parties",
    "audit_log",
    "prospects",
    "accounts",
    "client_id_sequences",
]


def main():
    db = SessionLocal()
    try:
        print("-> Clearing operational tables...")
        db.execute(text("UPDATE prospects SET converted_account_id = NULL"))
        for table in _TABLES_TO_CLEAR:
            db.execute(text(f"DELETE FROM {table}"))
        db.commit()
        print("CRM reset complete: no prospects or clients. Users and master data kept.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
