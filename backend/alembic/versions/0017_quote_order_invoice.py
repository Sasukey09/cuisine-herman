"""devis -> commande -> facture : reference de commande + lien facture/devis

Revision ID: 0017_quote_order_inv
Revises: 0016_quote_import
Create Date: 2026-07-23

Referme la boucle achats (§8-§9) :
- `quotes.order_reference` : la commande issue d'un devis retenu recoit sa
  propre reference (CMD-AAAA-NNNN), distincte de la reference du devis.
- `invoices.quote_id` : la facture recue est rattachee au devis commande, ce
  qui permet de confronter prix/quantites/TVA prevus et factures.

NB: revision ids <= 32 chars. "0017_quote_order_inv" = 20 chars.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0017_quote_order_inv"
down_revision = "0016_quote_import"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("quotes", sa.Column("order_reference", sa.Text(), nullable=True))
    op.add_column(
        "invoices",
        sa.Column(
            "quote_id",
            UUID(as_uuid=False),
            sa.ForeignKey("quotes.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_invoices_quote_id", "invoices", ["quote_id"])


def downgrade() -> None:
    op.drop_index("ix_invoices_quote_id", table_name="invoices")
    op.drop_column("invoices", "quote_id")
    op.drop_column("quotes", "order_reference")
