"""supplier_products catalog + VAT columns

Revision ID: 0014_supplier_catalog_vat
Revises: 0013_password_reset_tokens
Create Date: 2026-07-22

Foundation for the ERP work:
- `supplier_products`: a first-class product↔supplier catalog link carrying what
  a price row cannot (availability, preferred flag, supplier reference, lead
  time). Per-supplier prices stay in product_prices.
- `vat_rate` on invoice_lines and products (VAT was modeled nowhere), so the
  smart invoice import and the invoice detail can hold TVA.

NB: revision ids must stay <= 32 chars (alembic_version.version_num is
varchar(32)). "0014_supplier_catalog_vat" = 25 chars.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0014_supplier_catalog_vat"
down_revision = "0013_password_reset_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "supplier_products",
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
            "product_id",
            UUID(as_uuid=False),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "supplier_id",
            UUID(as_uuid=False),
            sa.ForeignKey("suppliers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("supplier_sku", sa.Text(), nullable=True),
        sa.Column("pack_size", sa.Text(), nullable=True),
        sa.Column("available", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("preferred", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("lead_time_days", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "tenant_id", "product_id", "supplier_id", name="uq_supplier_product"
        ),
    )
    op.create_index(
        "ix_supplier_products_product_id", "supplier_products", ["product_id"]
    )
    op.create_index(
        "ix_supplier_products_supplier_id", "supplier_products", ["supplier_id"]
    )

    op.add_column("invoice_lines", sa.Column("vat_rate", sa.Numeric(), nullable=True))
    op.add_column("products", sa.Column("vat_rate", sa.Numeric(), nullable=True))


def downgrade() -> None:
    op.drop_column("products", "vat_rate")
    op.drop_column("invoice_lines", "vat_rate")
    op.drop_index("ix_supplier_products_supplier_id", table_name="supplier_products")
    op.drop_index("ix_supplier_products_product_id", table_name="supplier_products")
    op.drop_table("supplier_products")
