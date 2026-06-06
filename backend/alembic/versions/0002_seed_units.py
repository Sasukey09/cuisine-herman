"""Seed canonical units (idempotent).

Categories & bases:
- mass   : base = kg
- volume : base = L
- count  : base = pièce (caisse/carton/palette are default pack sizes, overridable)

Revision ID: 0002_seed_units
Revises: 0001_initial_schema
"""
from alembic import op

revision = "0002_seed_units"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None

_UNITS = [
    ("mass", "kg", "Kilogramme", "1"),
    ("mass", "g", "Gramme", "0.001"),
    ("volume", "L", "Litre", "1"),
    ("volume", "ml", "Millilitre", "0.001"),
    ("count", "piece", "Pièce", "1"),
    ("count", "portion", "Portion", "1"),
    ("count", "caisse", "Caisse", "12"),
    ("count", "carton", "Carton", "24"),
    ("count", "palette", "Palette", "480"),
]


def upgrade():
    values = ", ".join(
        f"('{cat}', '{code}', '{name}', {ratio})" for cat, code, name, ratio in _UNITS
    )
    op.execute(
        f"INSERT INTO units (category, code, name, ratio_to_base) VALUES {values} "
        "ON CONFLICT (category, code) DO NOTHING;"
    )


def downgrade():
    codes = ", ".join(f"'{code}'" for _, code, _, _ in _UNITS)
    op.execute(f"DELETE FROM units WHERE code IN ({codes});")
