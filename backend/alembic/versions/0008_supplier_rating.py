"""Add suppliers.rating (0–5 stars).

Revision ID: 0008_supplier_rating
Revises: 0007_recipe_selling_price
"""
from alembic import op
import sqlalchemy as sa

revision = "0008_supplier_rating"
down_revision = "0007_recipe_selling_price"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("suppliers", sa.Column("rating", sa.Numeric(), nullable=True))


def downgrade():
    op.drop_column("suppliers", "rating")
