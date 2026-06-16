"""Add recipe_import_jobs + recipe_import_results (import a recipe from a PDF).

Stores an import run (OCR -> AI extraction -> preview) and its structured
result so the upload/poll/validate flow survives a page reload and is auditable.

Revision ID: 0004_recipe_import_jobs
Revises: 0003_recipe_ingredient_name
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "0004_recipe_import_jobs"
down_revision = "0003_recipe_ingredient_name"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "recipe_import_jobs",
        sa.Column("id", UUID(as_uuid=False), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", UUID(as_uuid=False),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE")),
        sa.Column("filename", sa.Text()),
        sa.Column("content_type", sa.Text()),
        sa.Column("status", sa.Text(), server_default=sa.text("'queued'")),
        sa.Column("error", sa.Text()),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_recipe_import_jobs_tenant", "recipe_import_jobs", ["tenant_id"]
    )

    op.create_table(
        "recipe_import_results",
        sa.Column("id", UUID(as_uuid=False), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("job_id", UUID(as_uuid=False),
                  sa.ForeignKey("recipe_import_jobs.id", ondelete="CASCADE")),
        sa.Column("tenant_id", UUID(as_uuid=False),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE")),
        sa.Column("raw_text", sa.Text()),
        sa.Column("recipe_name", sa.Text()),
        sa.Column("servings", sa.Numeric()),
        sa.Column("data", JSONB()),
        sa.Column("recipe_id", UUID(as_uuid=False),
                  sa.ForeignKey("recipes.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_recipe_import_results_job", "recipe_import_results", ["job_id"]
    )


def downgrade():
    op.drop_index("ix_recipe_import_results_job", table_name="recipe_import_results")
    op.drop_table("recipe_import_results")
    op.drop_index("ix_recipe_import_jobs_tenant", table_name="recipe_import_jobs")
    op.drop_table("recipe_import_jobs")
