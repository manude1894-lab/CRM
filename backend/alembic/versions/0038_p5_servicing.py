"""P5 Servicing (BRD v1.1 §17): client-linked activities with Visit / Call Reports, client-level
service requests, and a mobile number on users for SMS notifications.

- activities: account_id (backfilled from the case), case_id optional, report fields
  (client_contact, attendees, location, purpose); activity_type gains Visit Report / Call Report.
- instructions (Service Requests): account_id (backfilled from the case), case_id optional.
- users.mobile.
- master list service_request_type, seeded from the values that were hardcoded in the app.

Revision ID: 0038_p5_servicing
Revises: 0037_p3_compliance
Create Date: 2026-10-05
"""
from alembic import op
import sqlalchemy as sa

revision = "0038_p5_servicing"
down_revision = "0037_p3_compliance"
branch_labels = None
depends_on = None

REQUEST_TYPES = [
    "COI Issuance", "COGS Issuance", "COI & COGS Issuance", "New BVI Formation", "Change in Directors",
    "Change in Shareholding", "LEI Renewal", "AR Filing", "ESR Filing", "ROM/RBO Filing",
    "Notarization / Apostille", "Transfer & Restoration to Vistra", "Company Closure / Strike Off",
    "Change of Address", "Licence Renewal", "Other",
]


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # New enum values must be committed before they can be used.
        with op.get_context().autocommit_block():
            op.execute("ALTER TYPE activity_type ADD VALUE IF NOT EXISTS 'Visit Report'")
            op.execute("ALTER TYPE activity_type ADD VALUE IF NOT EXISTS 'Call Report'")

    with op.batch_alter_table("activities") as t:
        t.add_column(sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=True))
        t.alter_column("case_id", existing_type=sa.Integer(), nullable=True)
        t.add_column(sa.Column("client_contact", sa.String(150), nullable=True))
        t.add_column(sa.Column("attendees", sa.Text(), nullable=True))
        t.add_column(sa.Column("location", sa.String(200), nullable=True))
        t.add_column(sa.Column("purpose", sa.String(200), nullable=True))
    op.create_index("ix_activities_account_id", "activities", ["account_id"])
    op.execute("UPDATE activities SET account_id = (SELECT cases.account_id FROM cases WHERE cases.id = activities.case_id) "
               "WHERE account_id IS NULL AND case_id IS NOT NULL")

    with op.batch_alter_table("instructions") as t:
        t.add_column(sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=True))
        t.alter_column("case_id", existing_type=sa.Integer(), nullable=True)
    op.create_index("ix_instructions_account_id", "instructions", ["account_id"])
    op.execute("UPDATE instructions SET account_id = (SELECT cases.account_id FROM cases WHERE cases.id = instructions.case_id) "
               "WHERE account_id IS NULL AND case_id IS NOT NULL")

    op.add_column("users", sa.Column("mobile", sa.String(20), nullable=True))

    master = sa.table("master_items", sa.column("list_type", sa.String), sa.column("code", sa.String),
                      sa.column("label", sa.String), sa.column("sort_order", sa.Integer),
                      sa.column("is_active", sa.Boolean), sa.column("meta", sa.JSON))
    op.bulk_insert(master, [{"list_type": "service_request_type", "code": v, "label": v, "sort_order": (i + 1) * 10,
                             "is_active": True, "meta": None} for i, v in enumerate(REQUEST_TYPES)])


def downgrade():
    op.execute("DELETE FROM master_items WHERE list_type = 'service_request_type'")
    op.drop_column("users", "mobile")
    op.execute("DELETE FROM instructions WHERE case_id IS NULL")
    op.drop_index("ix_instructions_account_id", table_name="instructions")
    with op.batch_alter_table("instructions") as t:
        t.alter_column("case_id", existing_type=sa.Integer(), nullable=False)
        t.drop_column("account_id")
    op.execute("DELETE FROM activities WHERE case_id IS NULL")
    op.execute("UPDATE activities SET activity_type = 'Meeting' WHERE activity_type::text = 'Visit Report'"
               if op.get_bind().dialect.name == "postgresql" else "UPDATE activities SET activity_type = 'Meeting' WHERE activity_type = 'Visit Report'")
    op.execute("UPDATE activities SET activity_type = 'Call' WHERE activity_type::text = 'Call Report'"
               if op.get_bind().dialect.name == "postgresql" else "UPDATE activities SET activity_type = 'Call' WHERE activity_type = 'Call Report'")
    op.drop_index("ix_activities_account_id", table_name="activities")
    with op.batch_alter_table("activities") as t:
        t.drop_column("purpose")
        t.drop_column("location")
        t.drop_column("attendees")
        t.drop_column("client_contact")
        t.alter_column("case_id", existing_type=sa.Integer(), nullable=False)
        t.drop_column("account_id")
    # Postgres can't drop enum values; Visit Report / Call Report stay unused in activity_type.
