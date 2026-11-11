"""Columns that hold a master-list code take its full length (60).

Triam UAT 09/10-11-2026 (row 14): Admin's category "Screening & Search Results - Non-Individuals" is 44
characters, and documents.category held 40, so every upload under it failed (the Individuals one is
exactly 40, which is why that one worked). The other columns filled from master lists are widened too.

Revision ID: 0066_master_code_lengths
Revises: 0065_country_dial_code
Create Date: 2026-11-11
"""
import sqlalchemy as sa
from alembic import op

revision = "0066_master_code_lengths"
down_revision = "0065_country_dial_code"
branch_labels = None
depends_on = None

# (table, column, old length)
COLUMNS = (
    ("documents", "category", 40),
    ("accounts", "anchor_entity", 10),
    ("accounts", "regulator_name", 50),
    ("instructions", "triam_entity", 20),
    ("instructions", "status", 40),
)


def upgrade():
    for table, column, old in COLUMNS:
        op.alter_column(table, column, type_=sa.String(60), existing_type=sa.String(old))


def downgrade():
    for table, column, old in COLUMNS:
        op.alter_column(table, column, type_=sa.String(old), existing_type=sa.String(60))
