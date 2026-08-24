"""Add directors and shareholders registers (per Case / BVI entity).

Revision ID: 0004_directors_shareholders
Revises: 0003_triam_fields
Create Date: 2026-08-24
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_directors_shareholders"
down_revision = "0003_triam_fields"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "directors",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("director_type", sa.String(20), nullable=False, server_default="Individual"),
        sa.Column("first_name", sa.String(150), nullable=True),
        sa.Column("middle_name", sa.String(150), nullable=True),
        sa.Column("last_name", sa.String(150), nullable=True),
        sa.Column("former_name", sa.String(255), nullable=True),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("place_of_birth", sa.String(150), nullable=True),
        sa.Column("nationality", sa.String(100), nullable=True),
        sa.Column("passport_number", sa.String(50), nullable=True),
        sa.Column("corporate_name", sa.String(255), nullable=True),
        sa.Column("corporate_number", sa.String(100), nullable=True),
        sa.Column("country_of_incorporation", sa.String(100), nullable=True),
        sa.Column("corporate_date_of_incorporation", sa.Date(), nullable=True),
        sa.Column("service_address", sa.String(255), nullable=True),
        sa.Column("service_city", sa.String(100), nullable=True),
        sa.Column("service_country", sa.String(100), nullable=True),
        sa.Column("residential_address", sa.String(255), nullable=True),
        sa.Column("residential_city", sa.String(100), nullable=True),
        sa.Column("residential_country", sa.String(100), nullable=True),
        sa.Column("appointment_date", sa.Date(), nullable=True),
        sa.Column("cessation_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_directors_case_id", "directors", ["case_id"])

    op.create_table(
        "shareholders",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("identification_type", sa.String(30), nullable=False, server_default="Individual"),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("corporate_number", sa.String(100), nullable=True),
        sa.Column("country_of_incorporation", sa.String(100), nullable=True),
        sa.Column("registered_address", sa.String(255), nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("country", sa.String(100), nullable=True),
        sa.Column("certificate_no", sa.String(50), nullable=True),
        sa.Column("number_of_shares", sa.Integer(), nullable=True),
        sa.Column("share_class", sa.String(50), nullable=True),
        sa.Column("shareholding_percent", sa.Numeric(5, 2), nullable=True),
        sa.Column("is_joint_shareholder", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_nominee", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("nominee_holds_for", sa.String(255), nullable=True),
        sa.Column("date_entered", sa.Date(), nullable=True),
        sa.Column("date_ceased", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_shareholders_case_id", "shareholders", ["case_id"])


def downgrade():
    op.drop_index("ix_shareholders_case_id", table_name="shareholders")
    op.drop_table("shareholders")
    op.drop_index("ix_directors_case_id", table_name="directors")
    op.drop_table("directors")
