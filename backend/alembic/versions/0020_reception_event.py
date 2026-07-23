"""reception : tracabilite, refus, conditionnement, preuve photo

Revision ID: 0020_reception
Revises: 0019_purchasing
Create Date: 2026-07-23

Les tables `receipts` / `receipt_lines` posees en 0019 etaient la charpente.
La relecture d'architecture avant la Phase 3 a montre cinq manques par rapport
a ce qu'une reception doit vraiment porter. Rien n'ecrit encore dans ces tables,
donc les corriger maintenant ne coute rien — plus tard, il aurait fallu migrer
des donnees.

1. QUI a receptionne, et QUI a valide. Une reception est un evenement : sans
   auteur, elle n'est pas opposable. « Qui a signe ce bon de livraison ? » est
   exactement la question qu'on pose trois semaines apres, quand le fournisseur
   conteste un manquant.

2. `checked_at` / `checked_by` bornent l'IMMUTABILITE. Une reception en
   brouillon se corrige librement ; une fois validee elle est figee, et une
   correction ulterieure prend la forme d'une NOUVELLE reception corrective.
   C'est ainsi qu'un ERP evite de reecrire l'histoire.

3. `condition` gagne `rejected`. Refuser une marchandise et la recevoir abimee
   sont deux faits distincts : dans un cas elle est repartie, dans l'autre elle
   est en reserve. Les confondre fausserait le stock le jour ou on le branche.

4. `pack_size` sur la ligne recue : sans lui, l'ecart de CONDITIONNEMENT est
   indetectable. Recevoir 10 sacs de 10 kg au lieu de 10 sacs de 25 kg, c'est
   la meme quantite de lignes et 150 kg de moins.

5. `photo_url` par ligne. Le fichier deja present sur `receipts` est le bon de
   livraison ; une casse ou un refus se prouve par une photo DE LA LIGNE.

NB: revision ids <= 32 chars. "0020_reception" = 14.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0020_reception"
down_revision = "0019_purchasing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- 1 & 2 : qui, et jusqu'ou c'est modifiable ------------------------
    op.add_column(
        "receipts",
        sa.Column(
            "received_by",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
    )
    op.add_column(
        "receipts",
        sa.Column(
            "checked_by",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
    )
    # La date de validation EST la frontiere d'immutabilite : tant qu'elle est
    # nulle, la reception se corrige ; une fois posee, elle est figee.
    op.add_column("receipts", sa.Column("checked_at", sa.TIMESTAMP()))

    # --- 4 & 5 : ce qu'il manquait pour comparer et pour prouver ----------
    op.add_column("receipt_lines", sa.Column("pack_size", sa.Text()))
    op.add_column("receipt_lines", sa.Column("photo_url", sa.Text()))

    # --- Index de lecture -------------------------------------------------
    # La question posee en boucle par la fiche produit et par les KPI :
    # « qu'a-t-on reellement recu de ce produit ? »
    op.create_index(
        "ix_receipt_lines_product", "receipt_lines", ["tenant_id", "product_id"]
    )
    op.create_index("ix_receipts_supplier", "receipts", ["tenant_id", "supplier_id"])


def downgrade() -> None:
    op.drop_index("ix_receipts_supplier", table_name="receipts")
    op.drop_index("ix_receipt_lines_product", table_name="receipt_lines")
    op.drop_column("receipt_lines", "photo_url")
    op.drop_column("receipt_lines", "pack_size")
    op.drop_column("receipts", "checked_at")
    op.drop_column("receipts", "checked_by")
    op.drop_column("receipts", "received_by")
