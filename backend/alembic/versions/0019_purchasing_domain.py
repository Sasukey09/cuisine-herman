"""domaine Achats : commande, reception, mouvements de stock

Revision ID: 0019_purchasing
Revises: 0018_quote_commercial
Create Date: 2026-07-23

La commande n'existait pas : elle squattait le devis (`quotes.status='ordered'`,
`order_reference`, `ordered_at`). Trois consequences, de la plus grave a la
moins grave :

1. La sortie du comparateur etait inexploitable. Il designe le moins cher
   PRODUIT PAR PRODUIT, donc potentiellement plusieurs fournisseurs — mais
   commander marquait le devis entier comme commande chez UN fournisseur. On ne
   pouvait pas agir sur le conseil qu'on venait de donner.
2. Une commande a dix etats (brouillon → envoyee → confirmee → … → cloturee).
   Un devis en a trois. Les empiler sur la meme colonne etait intenable.
3. Commander MUTAIT le devis (cf. le correctif d'audit sur les prix ecrases).
   Une offre recue est un fait date : elle ne se reecrit pas.

D'ou ce decoupage :

- `purchase_orders` / `purchase_order_lines` : l'engagement. Une commande = un
  fournisseur ; une ligne porte `source_quote_line_id`, donc une commande peut
  tirer ses lignes de PLUSIEURS devis. C'est exactement ce que produit le
  comparateur.
- `receipts` / `receipt_lines` : la reception. Document separe et non drapeau sur
  la commande, parce qu'une commande peut etre livree en plusieurs fois. La
  quantite recue se CALCULE depuis les lignes de reception ; elle n'est pas
  denormalisee sur la commande, pour qu'il n'existe qu'une seule verite.
- `stock_locations` / `stock_movements` : prepares, sans logique metier pour
  l'instant. Les poser maintenant evite d'avoir a rouvrir la base plus tard :
  reception → entree, recette → consommation, inventaire, perte, valorisation.
- `invoices.order_id` : la facture se rattache desormais a la COMMANDE, et
  atteint le devis a travers elle. `quote_id` est conserve le temps de la
  bascule (expand/contract : cette revision etend, une revision ulterieure
  retirera les colonnes devenues inutiles une fois le code bascule — on ne
  supprime pas une colonne encore lue par la version en production).

Suppression au passage : `purchases`, table morte. Jamais ecrite, jamais lue,
remplacee par `purchase_history` sans avoir ete retiree.

NB: revision ids <= 32 chars. "0019_purchasing" = 15.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0019_purchasing"
down_revision = "0018_quote_commercial"
branch_labels = None
depends_on = None


def _uuid_fk(target, ondelete):
    return sa.ForeignKey(target, ondelete=ondelete)


def upgrade() -> None:
    # --- Commandes ---------------------------------------------------------
    op.create_table(
        "purchase_orders",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False),
                  _uuid_fk("organizations.id", "CASCADE")),
        sa.Column("reference", sa.Text()),          # CMD-2026-0001
        sa.Column("supplier_id", postgresql.UUID(as_uuid=False),
                  _uuid_fk("suppliers.id", "SET NULL")),
        # brouillon | envoyee | confirmee | en_preparation | expediee |
        # partiellement_livree | livree | facturee | terminee | annulee
        sa.Column("status", sa.Text(), server_default=sa.text("'draft'")),
        sa.Column("expected_date", sa.Date()),      # livraison annoncee
        sa.Column("ordered_at", sa.TIMESTAMP()),
        sa.Column("sent_at", sa.TIMESTAMP()),
        sa.Column("confirmed_at", sa.TIMESTAMP()),
        sa.Column("closed_at", sa.TIMESTAMP()),
        sa.Column("total_amount", sa.Numeric()),
        sa.Column("currency", sa.Text()),
        # Reprises du devis retenu : elles portent sur la commande entiere.
        sa.Column("delivery_fee", sa.Numeric()),
        sa.Column("discount_total", sa.Numeric()),
        sa.Column("conditions", sa.Text()),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.func.now()),
    )
    op.create_index("ix_purchase_orders_tenant", "purchase_orders", ["tenant_id"])
    op.create_index("ix_purchase_orders_supplier", "purchase_orders", ["tenant_id", "supplier_id"])
    op.create_index("ix_purchase_orders_status", "purchase_orders", ["tenant_id", "status"])

    op.create_table(
        "purchase_order_lines",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False),
                  _uuid_fk("organizations.id", "CASCADE")),
        sa.Column("order_id", postgresql.UUID(as_uuid=False),
                  _uuid_fk("purchase_orders.id", "CASCADE"), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=False),
                  _uuid_fk("products.id", "SET NULL")),
        sa.Column("description", sa.Text()),
        sa.Column("qty_ordered", sa.Numeric()),
        sa.Column("unit_id", sa.Integer(), sa.ForeignKey("units.id")),
        sa.Column("unit_price", sa.Numeric()),
        sa.Column("vat_rate", sa.Numeric()),
        sa.Column("discount_pct", sa.Numeric()),
        sa.Column("line_total", sa.Numeric()),
        sa.Column("pack_size", sa.Text()),
        sa.Column("brand", sa.Text()),
        # La tracabilite offre → engagement. SET NULL : supprimer un vieux devis
        # ne doit pas effacer la commande qui en est nee.
        sa.Column("source_quote_line_id", postgresql.UUID(as_uuid=False),
                  _uuid_fk("quote_lines.id", "SET NULL")),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.func.now()),
    )
    op.create_index("ix_po_lines_order", "purchase_order_lines", ["order_id"])
    op.create_index("ix_po_lines_product", "purchase_order_lines", ["tenant_id", "product_id"])

    # --- Receptions --------------------------------------------------------
    op.create_table(
        "receipts",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False),
                  _uuid_fk("organizations.id", "CASCADE")),
        sa.Column("reference", sa.Text()),          # REC-2026-0001
        # Nullable : on peut recevoir une livraison sans commande enregistree.
        sa.Column("order_id", postgresql.UUID(as_uuid=False),
                  _uuid_fk("purchase_orders.id", "SET NULL")),
        sa.Column("supplier_id", postgresql.UUID(as_uuid=False),
                  _uuid_fk("suppliers.id", "SET NULL")),
        sa.Column("received_at", sa.Date()),
        sa.Column("delivery_note_number", sa.Text()),  # numero du BL fournisseur
        sa.Column("status", sa.Text(), server_default=sa.text("'draft'")),  # draft | checked
        sa.Column("notes", sa.Text()),
        # Le bon de livraison photographie : meme pipeline OCR que factures et
        # devis, le jour ou on le branchera.
        sa.Column("file_url", sa.Text()),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.func.now()),
    )
    op.create_index("ix_receipts_tenant", "receipts", ["tenant_id"])
    op.create_index("ix_receipts_order", "receipts", ["order_id"])

    op.create_table(
        "receipt_lines",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False),
                  _uuid_fk("organizations.id", "CASCADE")),
        sa.Column("receipt_id", postgresql.UUID(as_uuid=False),
                  _uuid_fk("receipts.id", "CASCADE"), nullable=False),
        # Nullable : une ligne livree HORS commande est justement l'anomalie
        # qu'on veut pouvoir enregistrer.
        sa.Column("order_line_id", postgresql.UUID(as_uuid=False),
                  _uuid_fk("purchase_order_lines.id", "SET NULL")),
        sa.Column("product_id", postgresql.UUID(as_uuid=False),
                  _uuid_fk("products.id", "SET NULL")),
        sa.Column("description", sa.Text()),
        sa.Column("qty_received", sa.Numeric()),
        sa.Column("unit_id", sa.Integer(), sa.ForeignKey("units.id")),
        sa.Column("unit_price", sa.Numeric()),
        # ok | missing | extra | substituted | damaged
        sa.Column("condition", sa.Text(), server_default=sa.text("'ok'")),
        sa.Column("substituted_product_id", postgresql.UUID(as_uuid=False),
                  _uuid_fk("products.id", "SET NULL")),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.func.now()),
    )
    op.create_index("ix_receipt_lines_receipt", "receipt_lines", ["receipt_id"])
    op.create_index("ix_receipt_lines_order_line", "receipt_lines", ["order_line_id"])

    # --- Stock : pose des fondations, sans logique metier ------------------
    op.create_table(
        "stock_locations",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False),
                  _uuid_fk("organizations.id", "CASCADE")),
        sa.Column("name", sa.Text()),
        sa.Column("kind", sa.Text()),  # reserve | chambre_froide | congelateur | bar
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.func.now()),
    )
    op.create_index("ix_stock_locations_tenant", "stock_locations", ["tenant_id"])

    op.create_table(
        "stock_movements",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False),
                  _uuid_fk("organizations.id", "CASCADE")),
        sa.Column("product_id", postgresql.UUID(as_uuid=False),
                  _uuid_fk("products.id", "CASCADE")),
        sa.Column("location_id", postgresql.UUID(as_uuid=False),
                  _uuid_fk("stock_locations.id", "SET NULL")),
        # Quantite SIGNEE : + entree, − sortie. Un seul champ, donc pas de
        # colonne "sens" a tenir coherente avec le signe.
        sa.Column("qty", sa.Numeric()),
        sa.Column("unit_id", sa.Integer(), sa.ForeignKey("units.id")),
        # receipt | consumption | inventory | loss | adjustment | transfer
        sa.Column("movement_type", sa.Text()),
        # Origine du mouvement, sans FK dure : la source peut etre une ligne de
        # reception, une version de recette, un inventaire… Une FK par type
        # aurait ajoute six colonnes toujours nulles sauf une.
        sa.Column("source_type", sa.Text()),
        sa.Column("source_id", postgresql.UUID(as_uuid=False)),
        # Valorisation au moment du mouvement : le cout d'un produit bouge, la
        # valeur d'un mouvement passe est figee.
        sa.Column("unit_cost", sa.Numeric()),
        sa.Column("moved_at", sa.TIMESTAMP(), server_default=sa.func.now()),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.func.now()),
    )
    op.create_index("ix_stock_moves_product", "stock_movements", ["tenant_id", "product_id"])
    op.create_index("ix_stock_moves_source", "stock_movements", ["source_type", "source_id"])

    # --- La facture se rattache a la COMMANDE ------------------------------
    op.add_column(
        "invoices",
        sa.Column("order_id", postgresql.UUID(as_uuid=False),
                  _uuid_fk("purchase_orders.id", "SET NULL")),
    )
    op.create_index("ix_invoices_order", "invoices", ["order_id"])

    # --- Reprise des commandes qui vivaient dans les devis ------------------
    # Chaque devis marque "ordered" devient une vraie commande, lignes comprises,
    # et les factures qui pointaient sur le devis pointent desormais sur elle.
    # Sans cette reprise, l'historique des commandes deja passees disparaitrait.
    # L'id de la commande reprise EST celui du devis d'origine. Deux tables
    # distinctes, donc aucun conflit — et surtout un rattachement exact pour les
    # deux requetes suivantes. Se joindre sur un libelle de notes aurait croise
    # toutes les commandes entre elles des que deux devis auraient porte la meme
    # reference, ou aucune.
    op.execute(
        """
        INSERT INTO purchase_orders
            (id, tenant_id, reference, supplier_id, status, ordered_at,
             total_amount, currency, delivery_fee, discount_total, conditions,
             notes, created_at)
        SELECT q.id, q.tenant_id,
               COALESCE(
                   q.order_reference,
                   -- Le suffixe R marque une reprise et ne peut pas entrer en
                   -- collision avec la serie normale CMD-AAAA-NNNN.
                   'CMD-' || TO_CHAR(COALESCE(q.ordered_at, q.created_at, NOW()), 'YYYY') ||
                   '-R' || LPAD(CAST(ROW_NUMBER() OVER (
                       PARTITION BY q.tenant_id
                       ORDER BY COALESCE(q.ordered_at, q.created_at)) AS TEXT), 3, '0')),
               q.supplier_id, 'confirmed', COALESCE(q.ordered_at, q.created_at),
               q.total_amount, q.currency, q.delivery_fee, q.discount_total,
               q.conditions,
               'Commande reprise du devis ' || COALESCE(q.reference, '(sans reference)'),
               COALESCE(q.ordered_at, q.created_at)
        FROM quotes q
        WHERE q.status = 'ordered'
        """
    )
    op.execute(
        """
        INSERT INTO purchase_order_lines
            (id, tenant_id, order_id, product_id, description, qty_ordered,
             unit_id, unit_price, vat_rate, discount_pct, line_total, pack_size,
             brand, source_quote_line_id, created_at)
        SELECT gen_random_uuid(), ql.tenant_id, ql.quote_id, ql.product_id,
               ql.description, ql.qty, ql.unit_id, ql.unit_price, ql.vat_rate,
               ql.discount_pct, ql.line_total, ql.pack_size, ql.brand,
               ql.id, ql.created_at
        FROM quote_lines ql
        JOIN purchase_orders po ON po.id = ql.quote_id
        """
    )
    op.execute(
        """
        UPDATE invoices
        SET order_id = quote_id
        WHERE quote_id IS NOT NULL
          AND order_id IS NULL
          AND EXISTS (SELECT 1 FROM purchase_orders po WHERE po.id = invoices.quote_id)
        """
    )

    # --- Table morte -------------------------------------------------------
    # `purchases` n'a jamais ete ecrite ni lue : `purchase_history` la remplace
    # depuis le module Achats. Seule la purge RGPD la citait encore.
    op.execute("DROP TABLE IF EXISTS purchases")


def downgrade() -> None:
    op.create_table(
        "purchases",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False),
                  _uuid_fk("organizations.id", "CASCADE")),
        sa.Column("product_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("products.id")),
        sa.Column("supplier_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("suppliers.id")),
        sa.Column("invoice_line_id", postgresql.UUID(as_uuid=False),
                  _uuid_fk("invoice_lines.id", "SET NULL")),
        sa.Column("qty", sa.Numeric()),
        sa.Column("unit_id", sa.Integer(), sa.ForeignKey("units.id")),
        sa.Column("price", sa.Numeric()),
        sa.Column("currency", sa.Text()),
        sa.Column("purchased_at", sa.TIMESTAMP(), server_default=sa.func.now()),
    )
    op.drop_index("ix_invoices_order", table_name="invoices")
    op.drop_column("invoices", "order_id")
    op.drop_table("stock_movements")
    op.drop_table("stock_locations")
    op.drop_table("receipt_lines")
    op.drop_table("receipts")
    op.drop_table("purchase_order_lines")
    op.drop_table("purchase_orders")
