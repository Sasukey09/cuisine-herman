"""Add recipes.selling_price (menu price per portion, for margin).

Revision ID: 0007_recipe_selling_price
Revises: 0006_recipe_instructions
"""
from alembic import op
import sqlalchemy as sa

revision = "0007_recipe_selling_price"
down_revision = "0006_recipe_instructions"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("recipes", sa.Column("selling_price", sa.Numeric(), nullable=True))


def downgrade():
    op.drop_column("recipes", "selling_price")
