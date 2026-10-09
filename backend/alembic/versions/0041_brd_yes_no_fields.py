"""BRD v1.1 §5 alignment.

- "Is entity regulated", "Corporate Tax Registered" and "Introducer" are Mandatory Yes/No: they
  become nullable so "not answered yet" is different from "No". Clients still being prepared
  (New / WIP) are reset to "not answered", since the old checkbox could not record an answer;
  approved clients keep their values.
- "Current regulatory license expiry" (mandatory when regulated) is added.

Revision ID: 0041_brd_yes_no_fields
Revises: 0040_p7_security
Create Date: 2026-10-09
"""
from alembic import op
import sqlalchemy as sa

revision = "0041_brd_yes_no_fields"
down_revision = "0040_p7_security"
branch_labels = None
depends_on = None

FIELDS = ("is_regulated", "corp_tax_registered", "has_introducer")


def upgrade():
    with op.batch_alter_table("accounts") as t:
        for f in FIELDS:
            t.alter_column(f, existing_type=sa.Boolean(), nullable=True, server_default=None)
        t.add_column(sa.Column("regulatory_license_expiry_date", sa.Date(), nullable=True))
    op.execute("UPDATE accounts SET is_regulated = NULL, corp_tax_registered = NULL, has_introducer = NULL "
               "WHERE profile_status IN ('New', 'WIP') AND is_regulated = false AND corp_tax_registered = false "
               "AND has_introducer = false")


def downgrade():
    for f in FIELDS:
        op.execute(f"UPDATE accounts SET {f} = false WHERE {f} IS NULL")
    with op.batch_alter_table("accounts") as t:
        t.drop_column("regulatory_license_expiry_date")
        for f in FIELDS:
            t.alter_column(f, existing_type=sa.Boolean(), nullable=False)
