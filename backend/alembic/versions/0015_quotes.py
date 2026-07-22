"""quotes + quote_lines (comparateur de devis)

Revision ID: 0015_quotes
Revises: 0014_supplier_catalog_vat
Create Date: 2026-07-22

Phase 4 — the quote comparator (#1). A `quote` is a named basket of products to
source; `quote_lines` hold the requested product/qty. The comparator prices the
basket per supplier at read time (no snapshot needed while drafting). Converting
a quote to an order sets `status='ordered'`, stamps `supplier_id`/`total_amount`
and snapshots each line's retained `unit_price`/`supplier_id` so the order stays
stable as future prices move.

NB: revision ids must stay <= 32 chars (alembic_version.version_num is
varchar(32)). "0015_quotes" = 11 chars.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0015_quotes"
down_revision = "0014_supplier_catalog_vat"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "quotes",
        sa.Column(
            "id",
            UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=False),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("reference", sa.Text(), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), server_default=sa.text("'draft'")),
        sa.Column(
            "supplier_id",
            UUID(as_uuid=False),
            sa.ForeignKey("suppliers.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("total_amount", sa.Numeric(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("ordered_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.func.now()),
    )
    op.create_index("ix_quotes_tenant_id", "quotes", ["tenant_id"])

    op.create_table(
        "quote_lines",
        sa.Column(
            "id",
            UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=False),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "quote_id",
            UUID(as_uuid=False),
            sa.ForeignKey("quotes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            UUID(as_uuid=False),
            sa.ForeignKey("products.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("qty", sa.Numeric(), nullable=True),
        sa.Column("unit_id", sa.Integer(), sa.ForeignKey("units.id"), nullable=True),
        sa.Column("unit_price", sa.Numeric(), nullable=True),
        sa.Column(
            "supplier_id",
            UUID(as_uuid=False),
            sa.ForeignKey("suppliers.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.func.now()),
    )
    op.create_index("ix_quote_lines_quote_id", "quote_lines", ["quote_id"])


def downgrade() -> None:
    op.drop_index("ix_quote_lines_quote_id", table_name="quote_lines")
    op.drop_table("quote_lines")
    op.drop_index("ix_quotes_tenant_id", table_name="quotes")
    op.drop_table("quotes")
