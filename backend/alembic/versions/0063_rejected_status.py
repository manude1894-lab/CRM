"""A client rejected by Compliance or the Approver shows as Rejected, not WIP (Triam UAT 05-11-2026).

Clients already returned to the RM are moved across: those in WIP whose latest onboarding request was
rejected. A withdrawn submission stays WIP. Status dates are left as they are.

Revision ID: 0063_rejected_status
Revises: 0062_rm_portfolio_permission
Create Date: 2026-11-07
"""
from alembic import op

revision = "0063_rejected_status"
down_revision = "0062_rm_portfolio_permission"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        UPDATE accounts SET profile_status = 'Rejected'
        WHERE profile_status = 'WIP' AND (
            SELECT r.status FROM approval_requests r
            WHERE r.account_id = accounts.id AND r.request_type = 'client_profile'
            ORDER BY r.id DESC LIMIT 1) = 'Rejected'
    """)


def downgrade():
    op.execute("UPDATE accounts SET profile_status = 'WIP' WHERE profile_status = 'Rejected'")
