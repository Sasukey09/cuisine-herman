"""quotes: champs d'import OCR (en-tete + lignes)

Revision ID: 0016_quote_import
Revises: 0015_quotes
Create Date: 2026-07-23

Le module Devis passe de la saisie manuelle a l'import de document, via le MEME
pipeline que les factures (OCR -> apercu -> validation -> confirmation). Ces
colonnes portent ce que le document dit :

- `quotes` : numero du fournisseur (distinct de notre `reference`), date,
  validite de l'offre, devise, fichier importe, statut OCR, remise globale,
  conditions.
- `quote_lines` : TVA, total ligne, remise, conditionnement.

NB volontaire : ces prix restent dans quote_lines et n'alimentent PAS
product_prices / purchase_history — un devis est une offre, pas un achat ;
sinon le cout matiere des recettes serait calcule sur des prix jamais payes.

NB: revision ids <= 32 chars (alembic_version.version_num est varchar(32)).
"0016_quote_import" = 17 chars.
"""
from alembic import op
import sqlalchemy as sa

revision = "0016_quote_import"
down_revision = "0015_quotes"
branch_labels = None
depends_on = None


_QUOTE_COLS = (
    ("quote_number", sa.Text()),
    ("date", sa.Date()),
    ("valid_until", sa.Date()),
    ("currency", sa.Text()),
    ("file_url", sa.Text()),
    ("ocr_status", sa.Text()),
    ("discount_total", sa.Numeric()),
    ("conditions", sa.Text()),
)

_LINE_COLS = (
    ("vat_rate", sa.Numeric()),
    ("line_total", sa.Numeric()),
    ("discount_pct", sa.Numeric()),
    ("pack_size", sa.Text()),
)


def upgrade() -> None:
    for name, type_ in _QUOTE_COLS:
        op.add_column("quotes", sa.Column(name, type_, nullable=True))
    op.add_column(
        "quotes",
        sa.Column("parsed", sa.Boolean(), server_default=sa.text("false")),
    )
    for name, type_ in _LINE_COLS:
        op.add_column("quote_lines", sa.Column(name, type_, nullable=True))


def downgrade() -> None:
    for name, _ in _LINE_COLS:
        op.drop_column("quote_lines", name)
    op.drop_column("quotes", "parsed")
    for name, _ in _QUOTE_COLS:
        op.drop_column("quotes", name)
