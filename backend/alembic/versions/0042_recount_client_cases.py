"""Recount each client's cached case total and invoiced amount.

Cases imported in bulk, or moved to another client through an approved case amendment, did not
update these totals, so the Clients table could show 0 cases for a client that has some.

Revision ID: 0042_recount_client_cases
Revises: 0041_brd_yes_no_fields
Create Date: 2026-10-09
"""
from alembic import op

revision = "0042_recount_client_cases"
down_revision = "0041_brd_yes_no_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        UPDATE accounts SET
            total_cases = (SELECT COUNT(*) FROM cases WHERE cases.account_id = accounts.id),
            total_invoiced_amount = (SELECT COALESCE(SUM(invoice_amount), 0) FROM cases WHERE cases.account_id = accounts.id)
    """)


def downgrade() -> None:
    pass  # totals are derived data; nothing to undo
