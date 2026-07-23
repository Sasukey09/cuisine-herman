"""Domaine Achats contre un vrai Postgres : commandes, réceptions, cascades.

Ce fichier existe parce que trois des choses qu'on veut vraiment garantir ne
sont pas vérifiables sans base : la migration, les ``ON DELETE`` et la
numérotation concurrente. Skippe hors CI, comme les autres ``*_real_db``.
"""

import uuid
from datetime import date
from decimal import Decimal

import pytest

from app.crud import crud_quote
from app.models.models import (
    PurchaseOrder,
    PurchaseOrderLine,
    Quote,
    QuoteLine,
    Receipt,
    ReceiptLine,
    StockLocation,
    StockMovement,
)
from app.services.purchasing import numbering, order_service


@pytest.fixture()
def shop(db):
    from app.models.models import Organization, Product, Supplier

    tenant_id = str(uuid.uuid4())
    db.add(Organization(id=tenant_id, name="Achats Test"))
    db.commit()

    metro, transgourmet = str(uuid.uuid4()), str(uuid.uuid4())
    farine, beurre = str(uuid.uuid4()), str(uuid.uuid4())
    db.add(Supplier(id=metro, tenant_id=tenant_id, name="METRO"))
    db.add(Supplier(id=transgourmet, tenant_id=tenant_id, name="TRANSGOURMET"))
    db.add(Product(id=farine, tenant_id=tenant_id, name="Farine T55"))
    db.add(Product(id=beurre, tenant_id=tenant_id, name="Beurre doux"))
    db.commit()
    return {
        "tenant_id": tenant_id,
        "metro": metro,
        "transgourmet": transgourmet,
        "farine": farine,
        "beurre": beurre,
    }


def _quote_with_line(db, shop, supplier_id, product_id, qty, price, **kw):
    quote_id = str(uuid.uuid4())
    db.add(
        Quote(
            id=quote_id,
            tenant_id=shop["tenant_id"],
            reference=f"DEV-TEST-{uuid.uuid4().hex[:4]}",
            supplier_id=supplier_id,
            status="draft",
            currency="EUR",
            delivery_fee=kw.get("delivery_fee"),
        )
    )
    line_id = str(uuid.uuid4())
    db.add(
        QuoteLine(
            id=line_id,
            tenant_id=shop["tenant_id"],
            quote_id=quote_id,
            product_id=product_id,
            supplier_id=supplier_id,
            description=kw.get("description", "ligne"),
            qty=Decimal(str(qty)),
            unit_price=Decimal(str(price)),
        )
    )
    db.commit()
    return quote_id, line_id


# --- la promesse centrale -------------------------------------------------
def test_the_comparator_verdict_becomes_two_real_orders(db, shop):
    """Le moins cher chez METRO pour la farine, chez TRANSGOURMET pour le
    beurre : deux commandes réelles, pas un devis marqué « commandé »."""
    _, l_farine = _quote_with_line(db, shop, shop["metro"], shop["farine"], 10, 18.5)
    _, l_beurre = _quote_with_line(
        db, shop, shop["transgourmet"], shop["beurre"], 4, 42.0
    )

    offers = order_service.offers_from_quote_lines(
        db, shop["tenant_id"], [l_farine, l_beurre]
    )
    assert len(offers) == 2
    orders = order_service.create_orders(
        db, shop["tenant_id"], order_service.plan_orders(offers)
    )

    assert len(orders) == 2
    by_supplier = {str(o.supplier_id): o for o in orders}
    assert float(by_supplier[shop["metro"]].total_amount) == 185.0
    assert float(by_supplier[shop["transgourmet"]].total_amount) == 168.0
    # Chaque commande a sa propre référence, séquentielle.
    refs = sorted(o.reference for o in orders)
    assert refs[0].startswith("CMD-") and refs[0] != refs[1]


def test_the_source_quote_line_is_traceable_from_the_order(db, shop):
    """« D'où vient ce prix ? » doit avoir une réponse un an plus tard."""
    _, line_id = _quote_with_line(db, shop, shop["metro"], shop["farine"], 10, 18.5)
    offers = order_service.offers_from_quote_lines(db, shop["tenant_id"], [line_id])
    orders = order_service.create_orders(
        db, shop["tenant_id"], order_service.plan_orders(offers)
    )
    line = (
        db.query(PurchaseOrderLine)
        .filter(PurchaseOrderLine.order_id == orders[0].id)
        .one()
    )
    assert str(line.source_quote_line_id) == line_id


def test_ordering_leaves_the_quote_untouched(db, shop):
    """Une offre reçue est un fait daté. Le passage à la commande ne la
    réécrit pas — c'est la leçon du prix écrasé trouvé à l'audit."""
    quote_id, line_id = _quote_with_line(db, shop, shop["metro"], shop["farine"], 10, 18.5)
    offers = order_service.offers_from_quote_lines(db, shop["tenant_id"], [line_id])
    order_service.create_orders(db, shop["tenant_id"], order_service.plan_orders(offers))

    quote = db.query(Quote).filter(Quote.id == quote_id).one()
    line = db.query(QuoteLine).filter(QuoteLine.id == line_id).one()
    assert quote.status == "draft"
    assert float(line.unit_price) == 18.5


def test_a_line_from_another_tenant_is_never_ordered(db, shop):
    """Le garde-fou multi-organisation, au niveau du chargement des offres."""
    _, line_id = _quote_with_line(db, shop, shop["metro"], shop["farine"], 10, 18.5)
    assert order_service.offers_from_quote_lines(db, str(uuid.uuid4()), [line_id]) == []


# --- numérotation ---------------------------------------------------------
def test_references_are_sequential_per_tenant_and_year(db, shop):
    other = str(uuid.uuid4())
    from app.models.models import Organization

    db.add(Organization(id=other, name="Autre restaurant"))
    db.commit()

    first = numbering.next_reference(db, shop["tenant_id"], numbering.ORDER, PurchaseOrder)
    db.add(PurchaseOrder(tenant_id=shop["tenant_id"], reference=first, status="draft"))
    db.commit()
    second = numbering.next_reference(db, shop["tenant_id"], numbering.ORDER, PurchaseOrder)
    assert second.endswith("0002")

    # L'autre restaurant repart de 1 : ses numéros ne doivent rien dire du
    # volume d'affaires du premier.
    assert numbering.next_reference(db, other, numbering.ORDER, PurchaseOrder).endswith("0001")


def test_quote_numbering_still_uses_its_own_series(db, shop):
    ref = numbering.next_reference(db, shop["tenant_id"], numbering.QUOTE, Quote)
    assert ref.startswith("DEV-")


# --- réception ------------------------------------------------------------
def _order_with_line(db, shop, qty=10, price=18.5):
    _, line_id = _quote_with_line(db, shop, shop["metro"], shop["farine"], qty, price)
    offers = order_service.offers_from_quote_lines(db, shop["tenant_id"], [line_id])
    order = order_service.create_orders(
        db, shop["tenant_id"], order_service.plan_orders(offers)
    )[0]
    order_line = (
        db.query(PurchaseOrderLine).filter(PurchaseOrderLine.order_id == order.id).one()
    )
    return order, order_line


def _receive(db, shop, order, order_line, qty, issue=None):
    """Une réception. ``issue`` est un ``{qty, reason, outcome}`` optionnel —
    la qualité vit dans des lignes filles, plus dans une colonne d'état."""
    receipt_id, line_id = str(uuid.uuid4()), str(uuid.uuid4())
    db.add(
        Receipt(
            id=receipt_id,
            tenant_id=shop["tenant_id"],
            reference=numbering.next_reference(
                db, shop["tenant_id"], numbering.RECEIPT, Receipt
            ),
            order_id=order.id,
            supplier_id=order.supplier_id,
            received_at=date(2026, 7, 23),
        )
    )
    db.add(
        ReceiptLine(
            id=line_id,
            tenant_id=shop["tenant_id"],
            receipt_id=receipt_id,
            order_line_id=order_line.id,
            product_id=order_line.product_id,
            qty_delivered=Decimal(str(qty)),
        )
    )
    if issue:
        from app.models.models import ReceiptLineIssue

        db.add(
            ReceiptLineIssue(
                tenant_id=shop["tenant_id"],
                receipt_line_id=line_id,
                qty=Decimal(str(issue["qty"])) if issue.get("qty") is not None else None,
                reason=issue.get("reason", "other"),
                outcome=issue.get("outcome", "rejected"),
            )
        )
    db.commit()
    return receipt_id


def test_progress_reads_the_receipts_not_a_stored_counter(db, shop):
    """La quantité reçue n'est dénormalisée nulle part : elle se calcule, donc
    elle ne peut pas diverger."""
    order, line = _order_with_line(db, shop, qty=10, price=18.5)
    _receive(db, shop, order, line, 6)

    p = order_service.progress_for_order(db, shop["tenant_id"], str(order.id))
    assert p["lines"][0]["status"] == "partial"
    assert p["missing_value"] == 74.0
    assert p["suggested_status"] == order_service.PARTIALLY_RECEIVED


def test_two_deliveries_complete_the_order(db, shop):
    order, line = _order_with_line(db, shop, qty=10)
    _receive(db, shop, order, line, 4)
    _receive(db, shop, order, line, 6)

    p = order_service.progress_for_order(db, shop["tenant_id"], str(order.id))
    assert p["is_complete"] is True
    assert p["suggested_status"] == order_service.RECEIVED


def test_deleting_an_order_removes_its_lines(db, shop):
    """Même piège que sur les devis : ``order_id`` est NOT NULL, donc laisser
    l'ORM annuler les enfants violerait la contrainte et renverrait un 500."""
    order, _ = _order_with_line(db, shop)
    order_id = str(order.id)
    db.delete(order)
    db.commit()
    assert (
        db.query(PurchaseOrderLine)
        .filter(PurchaseOrderLine.order_id == order_id)
        .count()
        == 0
    )


def test_deleting_a_receipt_removes_its_lines(db, shop):
    order, line = _order_with_line(db, shop)
    receipt_id = _receive(db, shop, order, line, 10)
    db.delete(db.query(Receipt).filter(Receipt.id == receipt_id).one())
    db.commit()
    assert db.query(ReceiptLine).filter(ReceiptLine.receipt_id == receipt_id).count() == 0


def test_deleting_a_quote_does_not_destroy_the_order_it_produced(db, shop):
    """``source_quote_line_id`` est en SET NULL : archiver un vieux devis ne
    doit pas effacer l'engagement qui en est né."""
    quote_id, line_id = _quote_with_line(db, shop, shop["metro"], shop["farine"], 10, 18.5)
    offers = order_service.offers_from_quote_lines(db, shop["tenant_id"], [line_id])
    order = order_service.create_orders(
        db, shop["tenant_id"], order_service.plan_orders(offers)
    )[0]

    crud_quote.delete_quote(db, db.query(Quote).filter(Quote.id == quote_id).one())

    kept = db.query(PurchaseOrder).filter(PurchaseOrder.id == order.id).one()
    kept_line = (
        db.query(PurchaseOrderLine).filter(PurchaseOrderLine.order_id == kept.id).one()
    )
    assert float(kept_line.unit_price) == 18.5
    assert kept_line.source_quote_line_id is None


# --- fondations du stock : posées, inertes --------------------------------
def test_stock_tables_exist_and_accept_a_movement(db, shop):
    """Rien n'écrit encore ici. Le test vérifie seulement que la fondation
    tient, pour qu'on n'ait pas à rouvrir la base le jour où on la branche."""
    location_id = str(uuid.uuid4())
    db.add(
        StockLocation(
            id=location_id, tenant_id=shop["tenant_id"], name="Réserve", kind="reserve"
        )
    )
    db.add(
        StockMovement(
            tenant_id=shop["tenant_id"],
            product_id=shop["farine"],
            location_id=location_id,
            qty=Decimal("10"),          # + entrée
            movement_type="receipt",
            source_type="receipt_line",
            source_id=str(uuid.uuid4()),
            unit_cost=Decimal("18.5"),
        )
    )
    db.commit()
    moves = db.query(StockMovement).filter(
        StockMovement.tenant_id == shop["tenant_id"]
    ).all()
    assert len(moves) == 1 and float(moves[0].qty) == 10.0


def test_the_dead_purchases_table_is_gone(db):
    """La table `purchases` doublonnait `purchase_history` sans jamais être
    écrite ni lue."""
    from sqlalchemy import inspect

    assert "purchases" not in inspect(db.get_bind()).get_table_names()


def test_every_model_matches_the_migrated_schema(db):
    """Garde-fou de dérive : un modèle et sa migration peuvent diverger sans
    qu'aucun test ne s'en aperçoive — jusqu'au jour où la requête part en
    production. On compare les colonnes déclarées et les colonnes réelles.

    Vaut pour tout le schéma, pas seulement pour le domaine Achats.
    """
    from sqlalchemy import inspect

    from app.models.models import Base

    inspector = inspect(db.get_bind())
    existing = set(inspector.get_table_names())
    problems = []

    for table in Base.metadata.sorted_tables:
        if table.name not in existing:
            problems.append(f"{table.name} : déclarée dans les modèles, absente de la base")
            continue
        in_db = {c["name"] for c in inspector.get_columns(table.name)}
        declared = {c.name for c in table.columns}
        missing = declared - in_db
        if missing:
            problems.append(
                f"{table.name} : colonne(s) déclarée(s) mais jamais migrée(s) — "
                f"{', '.join(sorted(missing))}"
            )

    assert not problems, "\n".join(problems)


def test_an_already_ordered_quote_was_migrated_into_a_real_order(db, shop):
    """La reprise de données de la migration 0019, rejouée à la main : un devis
    marqué « ordered » devait devenir une vraie commande, lignes comprises,
    sans que l'historique déjà passé disparaisse.

    On vérifie la propriété qui rend la reprise fiable — l'id de la commande est
    celui du devis — parce que c'est elle qui remplace une jointure sur un
    libellé de notes, laquelle croisait toutes les commandes entre elles dès que
    deux devis portaient la même référence, ou aucune.
    """
    from sqlalchemy import text

    quote_id, line_id = _quote_with_line(db, shop, shop["metro"], shop["farine"], 10, 18.5)
    db.execute(
        text("UPDATE quotes SET status = 'ordered', order_reference = NULL WHERE id = :i"),
        {"i": quote_id},
    )
    db.commit()

    # Le fragment exact de la migration.
    db.execute(
        text(
            """
            INSERT INTO purchase_orders
                (id, tenant_id, reference, supplier_id, status, ordered_at,
                 total_amount, currency, notes, created_at)
            SELECT q.id, q.tenant_id,
                   COALESCE(q.order_reference,
                            'CMD-' || TO_CHAR(COALESCE(q.ordered_at, q.created_at, NOW()), 'YYYY')
                            || '-R001'),
                   q.supplier_id, 'confirmed', COALESCE(q.ordered_at, q.created_at),
                   q.total_amount, q.currency, 'reprise', COALESCE(q.ordered_at, q.created_at)
            FROM quotes q WHERE q.id = :i AND q.status = 'ordered'
            """
        ),
        {"i": quote_id},
    )
    db.commit()

    order = db.query(PurchaseOrder).filter(PurchaseOrder.id == quote_id).one()
    assert order.status == "confirmed"
    assert order.reference.endswith("-R001"), (
        "le suffixe R doit distinguer une reprise de la série normale"
    )
