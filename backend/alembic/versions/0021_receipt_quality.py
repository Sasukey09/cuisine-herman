"""reception : controle qualite — anomalies et photos en lignes filles

Revision ID: 0021_receipt_qc
Revises: 0020_reception
Create Date: 2026-07-23

Le modele pose en 0019/0020 disait : une ligne = une quantite + un etat. Le
metier dit autre chose. Sur 10 unites livrees, un receptionnaire constate
couramment : 8 conformes, 1 refusee pour DLC trop courte, 1 detruite pour
casse — et il photographie les deux.

Trois choses etaient donc inexprimables :

- une ligne ne portait qu'UN seul motif ;
- `qty_received` confondait ce qui est ARRIVE et ce qui est ACCEPTE ;
- `photo_url` etait au singulier.

D'ou ce decoupage, qui suit la doctrine deja retenue pour les ecarts et pour
les quantites recues : **ce qui se deduit ne se stocke pas**.

- `receipt_lines.qty_delivered` : le fait physique, ce qui est descendu du
  camion. Une seule quantite saisie, donc rien a reconcilier.
- `receipt_line_issues` : une anomalie = une ligne, avec sa quantite, son motif
  et son ISSUE (accepte sous reserve / refuse / detruit).
- `receipt_line_photos` : autant de photos que necessaire, rattachables a une
  anomalie precise.

Accepte, refuse, detruit et l'etat de la ligne se CALCULENT depuis ces
anomalies. C'est aussi pourquoi `condition` disparait : il faisait double
emploi avec le motif d'anomalie, et deux concepts qui se recouvrent finissent
par se contredire.

Suppression franche plutot qu'expand/contract : la table est vide (aucune
reception n'existe encore) et l'endpoint vient d'etre livre. Garder une colonne
morte pour un cycle de deploiement aurait laisse une dette sans contrepartie.

NB: revision ids <= 32 chars. "0021_receipt_qc" = 15.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0021_receipt_qc"
down_revision = "0020_reception"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- ce qui est arrive, distinct de ce qui est accepte ----------------
    op.alter_column("receipt_lines", "qty_received", new_column_name="qty_delivered")

    # Remplaces par les anomalies et les photos filles.
    op.drop_column("receipt_lines", "condition")
    op.drop_column("receipt_lines", "photo_url")

    # --- anomalies --------------------------------------------------------
    op.create_table(
        "receipt_line_issues",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE")),
        sa.Column("receipt_line_id", postgresql.UUID(as_uuid=False),
                  sa.ForeignKey("receipt_lines.id", ondelete="CASCADE"), nullable=False),
        # Sur combien d'unites porte l'anomalie. Le reste de la ligne reste
        # conforme : c'est tout l'interet de ne pas etiqueter la ligne entiere.
        sa.Column("qty", sa.Numeric()),
        # packaging_damaged | product_damaged | short_shelf_life | wrong_grade |
        # wrong_temperature | wrong_packaging | substituted | breakage |
        # missing | other
        sa.Column("reason", sa.Text()),
        # accepted : gardee sous reserve · rejected : repartie ·
        # destroyed : detruite sur place. Les deux dernieres ne comptent ni pour
        # la commande ni pour le stock — on ne les a pas.
        sa.Column("outcome", sa.Text(), server_default=sa.text("'rejected'")),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.func.now()),
    )
    op.create_index("ix_receipt_issues_line", "receipt_line_issues", ["receipt_line_id"])
    op.create_index("ix_receipt_issues_reason", "receipt_line_issues", ["tenant_id", "reason"])

    # --- photos -----------------------------------------------------------
    op.create_table(
        "receipt_line_photos",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE")),
        sa.Column("receipt_line_id", postgresql.UUID(as_uuid=False),
                  sa.ForeignKey("receipt_lines.id", ondelete="CASCADE"), nullable=False),
        # Nullable : une photo peut documenter la ligne en general (la palette)
        # ou une anomalie precise (le carton eventre).
        sa.Column("issue_id", postgresql.UUID(as_uuid=False),
                  sa.ForeignKey("receipt_line_issues.id", ondelete="SET NULL")),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("caption", sa.Text()),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.func.now()),
    )
    op.create_index("ix_receipt_photos_line", "receipt_line_photos", ["receipt_line_id"])

    # --- tracabilite : l'appareil qui a servi -----------------------------
    # « Sur quoi a-t-elle ete saisie ? » aide a expliquer une saisie douteuse :
    # un telephone en chambre froide et un poste en bureau ne racontent pas la
    # meme histoire.
    op.add_column("receipts", sa.Column("device_info", sa.Text()))


def downgrade() -> None:
    op.drop_column("receipts", "device_info")
    op.drop_table("receipt_line_photos")
    op.drop_table("receipt_line_issues")
    op.add_column("receipt_lines", sa.Column("photo_url", sa.Text()))
    op.add_column(
        "receipt_lines",
        sa.Column("condition", sa.Text(), server_default=sa.text("'ok'")),
    )
    op.alter_column("receipt_lines", "qty_delivered", new_column_name="qty_received")
