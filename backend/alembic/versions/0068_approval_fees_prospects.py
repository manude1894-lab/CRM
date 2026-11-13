"""Approval date on the client, the registry / government fee on a service request, fewer prospect statuses.

- accounts.approved_at: when the Final approval was given, so approved clients can be listed newest first
  and filtered by approval date (Triam 13-11-2026). Filled from each client's approved request; a client
  that was imported or approved before this column takes its last status change, else its creation date.
- instructions.govt_authority_amount / _currency: "Amount payable to Reg./Govt Auth" (Invoice Box template,
  revised 13-11-2026).
- Prospects (Triam UAT 13-11-2026): New and Proposal Sent are merged into New, Negotiating is removed,
  Lost is renamed Dropped.

Revision ID: 0068_approval_fees_prospects
Revises: 0067_service_request_invoicing
Create Date: 2026-11-13
"""
import sqlalchemy as sa
from alembic import op

revision = "0068_approval_fees_prospects"
down_revision = "0067_service_request_invoicing"
branch_labels = None
depends_on = None

SERVICED = "('Approved', 'Active', 'Inactive', 'Marked for Exit', 'Exited')"


def upgrade():
    op.add_column("accounts", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_accounts_approved_at", "accounts", ["approved_at"])
    op.execute("""
        UPDATE accounts a SET approved_at = r.decided_at
        FROM (SELECT account_id, MAX(decided_at) AS decided_at FROM approval_requests
              WHERE request_type = 'client_profile' AND status = 'Approved' GROUP BY account_id) r
        WHERE r.account_id = a.id
    """)
    op.execute(f"UPDATE accounts SET approved_at = COALESCE(status_updated_at, created_at) "
               f"WHERE approved_at IS NULL AND profile_status IN {SERVICED}")

    op.add_column("instructions", sa.Column("govt_authority_amount", sa.Numeric(12, 2), nullable=True))
    op.add_column("instructions", sa.Column("govt_authority_currency", sa.String(3), nullable=True))

    op.execute("UPDATE prospects SET status = 'New' WHERE status IN ('Proposal Sent', 'Negotiating')")
    op.execute("UPDATE prospects SET status = 'Dropped' WHERE status = 'Lost'")


def downgrade():
    op.execute("UPDATE prospects SET status = 'Lost' WHERE status = 'Dropped'")
    op.drop_column("instructions", "govt_authority_currency")
    op.drop_column("instructions", "govt_authority_amount")
    op.drop_index("ix_accounts_approved_at", table_name="accounts")
    op.drop_column("accounts", "approved_at")
