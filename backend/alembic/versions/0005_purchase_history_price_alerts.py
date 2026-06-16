"""Add purchase_history + price_alerts (supplier purchase & price tracking).

PurchaseHistory is the analytics ledger written on invoice import (qty/total,
standardized unit cost, variation vs previous purchase). PriceAlert persists the
price-move / margin alerts. SupplierPriceHistory from the spec is intentionally a
query over purchase_history (supplier_id is on it) — no redundant table.

Revision ID: 0005_purchase_history_price_alerts
Revises: 0004_recipe_import_jobs
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0005_purchase_history_price_alerts"
down_revision = "0004_recipe_import_jobs"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "purchase_history",
        sa.Column("id", UUID(as_uuid=False), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", UUID(as_uuid=False),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE")),
        sa.Column("product_id", UUID(as_uuid=False),
                  sa.ForeignKey("products.id", ondelete="SET NULL")),
        sa.Column("supplier_id", UUID(as_uuid=False),
                  sa.ForeignKey("suppliers.id", ondelete="SET NULL")),
        sa.Column("invoice_id", UUID(as_uuid=False),
                  sa.ForeignKey("invoices.id", ondelete="SET NULL")),
        sa.Column("invoice_line_id", UUID(as_uuid=False),
                  sa.ForeignKey("invoice_lines.id", ondelete="SET NULL")),
        sa.Column("invoice_number", sa.Text()),
        sa.Column("purchase_date", sa.Date()),
        sa.Column("qty", sa.Numeric()),
        sa.Column("unit_id", sa.Integer(), sa.ForeignKey("units.id")),
        sa.Column("unit_code", sa.Text()),
        sa.Column("unit_price", sa.Numeric()),
        sa.Column("total_price", sa.Numeric()),
        sa.Column("unit_cost_standard", sa.Numeric()),
        sa.Column("currency", sa.Text()),
        sa.Column("variation_pct", sa.Numeric()),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.func.now()),
    )
    op.create_index("ix_purchase_history_tenant_product", "purchase_history",
                    ["tenant_id", "product_id"])
    op.create_index("ix_purchase_history_tenant_supplier", "purchase_history",
                    ["tenant_id", "supplier_id"])

    op.create_table(
        "price_alerts",
        sa.Column("id", UUID(as_uuid=False), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", UUID(as_uuid=False),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE")),
        sa.Column("type", sa.Text()),
        sa.Column("product_id", UUID(as_uuid=False),
                  sa.ForeignKey("products.id", ondelete="CASCADE")),
        sa.Column("supplier_id", UUID(as_uuid=False),
                  sa.ForeignKey("suppliers.id", ondelete="SET NULL")),
        sa.Column("recipe_id", UUID(as_uuid=False),
                  sa.ForeignKey("recipes.id", ondelete="CASCADE")),
        sa.Column("old_value", sa.Numeric()),
        sa.Column("new_value", sa.Numeric()),
        sa.Column("change_pct", sa.Numeric()),
        sa.Column("message", sa.Text()),
        sa.Column("is_read", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.func.now()),
    )
    op.create_index("ix_price_alerts_tenant", "price_alerts", ["tenant_id"])


def downgrade():
    op.drop_index("ix_price_alerts_tenant", table_name="price_alerts")
    op.drop_table("price_alerts")
    op.drop_index("ix_purchase_history_tenant_supplier", table_name="purchase_history")
    op.drop_index("ix_purchase_history_tenant_product", table_name="purchase_history")
    op.drop_table("purchase_history")
