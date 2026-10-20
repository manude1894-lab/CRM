"""BRD alignment: remove everything outside Triam's BRD and Service Requests list.

The CRM started as Ezee Tech's DIFC onboarding tracker built around Cases. Triam's BRD defines the
flow as Prospect → Client (RM → Compliance (MLRO) → Approver) → Service Requests, so the case pipeline
and everything hanging off it goes:

- tables: cases and their additional RMs, CDD records and checklists, filing calendar, company profiles,
  entity lifecycle, formation records, per-case directors / shareholders / UBOs, AML and PEP
  assessments, action points, service subscriptions, client feedback;
- case links on documents, service requests, invoices, activities, approvals, notifications (now
  linked to the client) and prospects;
- service-request fields and unused request types of the old Excel tracker (Vistra dates, cost,
  free-text references);
- activity types other than Visit Report / Call Report; user types Ops and Screening.

Demo data only (not live), so rows that belonged to cases are deleted with them.

Revision ID: 0056_brd_alignment
Revises: 0055_super_admin
Create Date: 2026-10-20
"""
from alembic import op

revision = "0056_brd_alignment"
down_revision = "0055_super_admin"
branch_labels = None
depends_on = None

_DROPPED_TABLES = [
    "action_points", "aml_risk_assessments", "pep_assessments", "case_documents", "cdd_records",
    "company_profiles", "entity_lifecycle", "formation_records", "compliance_schedules",
    "service_feedback", "service_subscriptions", "directors", "shareholders", "ubos",
    "case_relationship_managers", "cases",
]
_DROPPED_TYPES = ["case_source", "case_stage", "case_status", "document_status", "invoice_status", "risk_level"]


def upgrade():
    ex = op.execute

    # Rows that only existed for a case.
    ex("DELETE FROM documents WHERE account_id IS NULL")
    ex("DELETE FROM instructions WHERE account_id IS NULL")
    ex("UPDATE instructions SET invoice_id = NULL WHERE invoice_id IN (SELECT id FROM invoices WHERE account_id IS NULL)")
    ex("DELETE FROM invoices WHERE account_id IS NULL")
    ex("DELETE FROM approval_requests WHERE request_type NOT IN ('client_profile', 'client_amendment')")

    # Notifications point at the client instead of a case.
    ex("ALTER TABLE notifications ADD COLUMN account_id INTEGER REFERENCES accounts(id) ON DELETE CASCADE")
    ex("CREATE INDEX ix_notifications_account_id ON notifications (account_id)")
    ex("UPDATE notifications n SET account_id = c.account_id FROM cases c WHERE n.case_id = c.id")

    for table, columns in {
        "notifications": ["case_id"],
        "documents": ["case_id", "case_document_id", "generated_from"],
        "instructions": ["case_id", "document_shared", "date_sent_to_vistra", "date_received_from_vistra",
                         "cost_amount", "invoice_reference"],
        "invoices": ["case_id"],
        "activities": ["case_id"],
        "approval_requests": ["case_id"],
        "prospects": ["converted_case_id"],
    }.items():
        for column in columns:
            ex(f"ALTER TABLE {table} DROP COLUMN IF EXISTS {column}")
    for table in ("documents", "instructions", "invoices"):
        ex(f"ALTER TABLE {table} ALTER COLUMN account_id SET NOT NULL")

    for table in _DROPPED_TABLES:
        ex(f"DROP TABLE IF EXISTS {table} CASCADE")

    # Activities: Visit Reports and Call Reports only (BRD §15).
    ex("ALTER TABLE activities ALTER COLUMN activity_type TYPE VARCHAR(30) USING activity_type::text")
    ex("UPDATE activities SET activity_type = 'Visit Report' WHERE activity_type IN ('Meeting', 'Demo')")
    ex("UPDATE activities SET activity_type = 'Call Report' WHERE activity_type NOT IN ('Visit Report', 'Call Report')")
    ex("DROP TYPE IF EXISTS activity_type")
    ex("CREATE TYPE activity_type AS ENUM ('Visit Report', 'Call Report')")
    ex("ALTER TABLE activities ALTER COLUMN activity_type TYPE activity_type USING activity_type::activity_type")

    # User types: Administrator or staff user; access comes from business roles (BRD §13).
    ex("ALTER TABLE users ALTER COLUMN role DROP DEFAULT")
    ex("ALTER TABLE users ALTER COLUMN role TYPE VARCHAR(20) USING role::text")
    ex("UPDATE users SET role = 'rm' WHERE role NOT IN ('admin', 'rm')")
    ex("DROP TYPE IF EXISTS user_role")
    ex("CREATE TYPE user_role AS ENUM ('admin', 'rm')")
    ex("ALTER TABLE users ALTER COLUMN role TYPE user_role USING role::user_role")

    # Enum types used only by the dropped tables.
    for t in _DROPPED_TYPES:
        ex(f"DROP TYPE IF EXISTS {t}")

    # Request types of the old Excel tracker, switched off when Triam's Service Requests list was loaded
    # (0052) and not used by any request.
    ex("DELETE FROM master_items WHERE list_type = 'service_request_type' AND is_active = false "
       "AND code NOT IN (SELECT instruction_type FROM instructions)")


def downgrade():
    raise NotImplementedError("The case pipeline was removed for good; restore from a backup taken before 0056.")
