"""ISD (dialling) code on the Countries master, kept by Admin (Triam UAT 09/11-11-2026).

Filled from each country's ISO code using the list the forms used until now (app/data/dial_codes.json).
A country without a code, or one Admin already filled, is left alone.

Revision ID: 0065_country_dial_code
Revises: 0064_screening_date
Create Date: 2026-11-11
"""
import json
from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision = "0065_country_dial_code"
down_revision = "0064_screening_date"
branch_labels = None
depends_on = None

_CODES = json.loads((Path(__file__).resolve().parents[2] / "app" / "data" / "dial_codes.json").read_text(encoding="utf-8"))


def upgrade():
    op.add_column("country_risk", sa.Column("dial_code", sa.String(8), nullable=True))
    bind = op.get_bind()
    for iso, dial in _CODES.items():
        bind.execute(sa.text("UPDATE country_risk SET dial_code = :d WHERE UPPER(code) = :c AND dial_code IS NULL"), {"d": dial, "c": iso})


def downgrade():
    op.drop_column("country_risk", "dial_code")
