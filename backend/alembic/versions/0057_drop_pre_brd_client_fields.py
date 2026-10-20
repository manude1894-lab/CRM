"""Drop client fields that are not in the BRD.

Left over from the original sales CRM: industry (BRD §22 item 7: dropped), strategic priority
(item 8: dropped), company size, website, key contacts, existing relationship, KYC status (the
approval workflow is the status now), the case and invoice totals, and on Individual clients the
passport number, occupation, source of funds / wealth (BRD §14: documents) and the old single mobile
field on clients and their parties (replaced by country code + number).

Revision ID: 0057_drop_pre_brd_client_fields
Revises: 0056_brd_alignment
Create Date: 2026-10-20
"""
from alembic import op

revision = "0057_drop_pre_brd_client_fields"
down_revision = "0056_brd_alignment"
branch_labels = None
depends_on = None

_COLUMNS = ["industry", "company_size", "website", "key_contacts", "strategic_priority", "existing_relationship",
            "kyc_status", "total_cases", "total_invoiced_amount", "passport_number", "occupation", "source_of_funds",
            "source_of_wealth", "individual_mobile"]


def upgrade():
    for column in _COLUMNS:
        op.execute(f"ALTER TABLE accounts DROP COLUMN IF EXISTS {column}")
    op.execute("ALTER TABLE account_parties DROP COLUMN IF EXISTS mobile")
    op.execute("DROP TYPE IF EXISTS priority")


def downgrade():
    raise NotImplementedError("Restore from a backup taken before 0057.")
