"""devis : marque, quantite minimale, frais de livraison (§5)

Revision ID: 0018_quote_commercial
Revises: 0017_quote_order_inv
Create Date: 2026-07-23

Trois conditions commerciales qui manquaient au comparateur :

- `quote_lines.brand` : la marque proposee (deux offres du meme produit ne sont
  pas equivalentes si l'une est une marque distributeur).
- `quote_lines.min_qty` : quantite minimale de commande. Une offre moins chere
  mais imposant 10x le besoin n'est pas la meilleure offre.
- `quotes.delivery_fee` : frais de livraison, au niveau du DEVIS et non de la
  ligne (ils s'appliquent a la commande entiere). Ils changent qui est
  reellement le moins cher : un fournisseur 2 % moins cher avec 50 EUR de port
  peut couter plus qu'un concurrent en franco.

NB: revision ids <= 32 chars. "0018_quote_commercial" = 21 chars.
"""
from alembic import op
import sqlalchemy as sa

revision = "0018_quote_commercial"
down_revision = "0017_quote_order_inv"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("quotes", sa.Column("delivery_fee", sa.Numeric(), nullable=True))
    op.add_column("quote_lines", sa.Column("brand", sa.Text(), nullable=True))
    op.add_column("quote_lines", sa.Column("min_qty", sa.Numeric(), nullable=True))


def downgrade() -> None:
    op.drop_column("quote_lines", "min_qty")
    op.drop_column("quote_lines", "brand")
    op.drop_column("quotes", "delivery_fee")
