"""Activate every registering authority (Triam, 02-11-2026).

The Licensing Authority field is now called Registering Authority, and every authority in the list
is to be available for selection.

Revision ID: 0061_activate_reg_authorities
Revises: 0060_country_code_and_risk
Create Date: 2026-11-02
"""
from alembic import op

revision = "0061_activate_reg_authorities"
down_revision = "0060_country_code_and_risk"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("UPDATE master_items SET is_active = true WHERE list_type = 'licensing_authority'")


def downgrade():
    pass  # which authorities were inactive before is not recorded
