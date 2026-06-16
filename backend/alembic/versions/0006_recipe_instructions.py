"""Add recipe_instructions (ordered preparation steps).

So a recipe imported from a video/PDF keeps its full procedure, like a manual
one. (Revision id kept <= 32 chars — alembic_version.version_num is varchar(32).)

Revision ID: 0006_recipe_instructions
Revises: 0005_purchase_tracking
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0006_recipe_instructions"
down_revision = "0005_purchase_tracking"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "recipe_instructions",
        sa.Column("id", UUID(as_uuid=False), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("recipe_id", UUID(as_uuid=False),
                  sa.ForeignKey("recipes.id", ondelete="CASCADE")),
        sa.Column("step_number", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.func.now()),
    )
    op.create_index("ix_recipe_instructions_recipe", "recipe_instructions", ["recipe_id"])


def downgrade():
    op.drop_index("ix_recipe_instructions_recipe", table_name="recipe_instructions")
    op.drop_table("recipe_instructions")
