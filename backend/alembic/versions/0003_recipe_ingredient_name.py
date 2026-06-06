"""Add recipe_ingredients.ingredient_name (free-text ingredient label).

Lets a recipe ingredient keep the name it was created with even when it isn't
(yet) mapped to a catalog product — needed to re-match dangling ingredients to
products after the fact.

Revision ID: 0003_recipe_ingredient_name
Revises: 0002_seed_units
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_recipe_ingredient_name"
down_revision = "0002_seed_units"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "recipe_ingredients",
        sa.Column("ingredient_name", sa.Text(), nullable=True),
    )


def downgrade():
    op.drop_column("recipe_ingredients", "ingredient_name")
