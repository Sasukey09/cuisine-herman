"""Missing indexes: tenant scoping and the hot foreign keys

Revision ID: 0010_perf_indexes
Revises: 0009_user_token_version
Create Date: 2026-07-13

`recipes`, `suppliers`, `invoices` and `users` had NO index on tenant_id, so
listing one restaurant's recipes was a sequential scan over every restaurant's
recipes. `recipe_ingredients(recipe_version_id)` and `recipe_costs
(recipe_version_id)` had none either, so costing walked the whole table.

`product_prices` already had (tenant_id, product_id, supplier_id, effective_date)
— but with supplier_id in the middle, Postgres cannot use it to satisfy the
ORDER BY effective_date DESC of the "latest price" lookup, so it sorted every
time. The narrower (tenant_id, product_id, effective_date DESC) makes that read
an ordered index scan.

NB: revision ids must stay <= 32 chars (alembic_version.version_num is varchar(32)).
"""
from alembic import op

revision = "0010_perf_indexes"
down_revision = "0009_user_token_version"
branch_labels = None
depends_on = None

# (name, table, columns) — created IF NOT EXISTS so a hand-made index is not a conflict.
_INDEXES = [
    ("ix_recipes_tenant", "recipes", "tenant_id"),
    ("ix_suppliers_tenant", "suppliers", "tenant_id"),
    ("ix_invoices_tenant", "invoices", "tenant_id"),
    ("ix_users_tenant", "users", "tenant_id"),
    ("ix_recipe_ingredients_version", "recipe_ingredients", "recipe_version_id"),
    ("ix_recipe_costs_version", "recipe_costs", "recipe_version_id"),
    ("ix_invoice_lines_invoice", "invoice_lines", "invoice_id"),
    ("ix_product_prices_latest", "product_prices", "tenant_id, product_id, effective_date DESC"),
]


def upgrade() -> None:
    for name, table, cols in _INDEXES:
        op.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({cols})")


def downgrade() -> None:
    for name, _table, _cols in _INDEXES:
        op.execute(f"DROP INDEX IF EXISTS {name}")
