"""Contrôle facture contre un vrai Postgres : le cycle commandé → livré →
facturé, bout à bout.

Ce qui se vérifie ici et nulle part ailleurs : le rattachement automatique de la
facture à la commande, l'avancement du cycle jusqu'à « facturée », et surtout la
colonne « livré » — celle qui distingue une sur-facturation d'une simple
facturation partielle. Un rapprochement au devis seul ne l'aurait jamais vue.
"""

import uuid
from decimal import Decimal

import pytest

from app.models.models import (
    Invoice,
    InvoiceLine,
    Organization,
    Product,
    PurchaseOrder,
    PurchaseOrderLine,
    Receipt,
    ReceiptLine,
    Supplier,
)
from app.services.purchasing import invoice_control, order_service


@pytest.fixture()
def shop(db):
    tenant_id = str(uuid.uuid4())
    db.add(Organization(id=tenant_id, name="Facture Test"))
    db.commit()
    metro, farine, beurre = (str(uuid.uuid4()) for _ in range(3))
    db.add(Supplier(id=metro, tenant_id=tenant_id, name="METRO"))
    db.add(Product(id=farine, tenant_id=tenant_id, name="Farine T55"))
    db.add(Product(id=beurre, tenant_id=tenant_id, name="Beurre doux"))
    db.commit()
    return {"tenant_id": tenant_id, "metro": metro, "farine": farine, "beurre": beurre}


def _order(db, shop, lines, status=order_service.RECEIVED):
    """lines: [(product_id, qty, price)]"""
    order_id = str(uuid.uuid4())
    db.add(
        PurchaseOrder(
            id=order_id,
            tenant_id=shop["tenant_id"],
            reference=f"CMD-T-{uuid.uuid4().hex[:4]}",
            supplier_id=shop["metro"],
            status=status,
        )
    )
    line_ids = {}
    for pid, qty, price in lines:
        lid = str(uuid.uuid4())
        line_ids[pid] = lid
        db.add(
            PurchaseOrderLine(
                id=lid,
                tenant_id=shop["tenant_id"],
                order_id=order_id,
                product_id=pid,
                description="ligne",
                qty_ordered=Decimal(str(qty)),
                unit_price=Decimal(str(price)),
            )
        )
    db.commit()
    return order_id, line_ids


def _receive(db, shop, order_id, line_ids, received):
    """received: {product_id: accepted_qty}"""
    receipt_id = str(uuid.uuid4())
    db.add(
        Receipt(
            id=receipt_id,
            tenant_id=shop["tenant_id"],
            reference=f"REC-T-{uuid.uuid4().hex[:4]}",
            order_id=order_id,
            supplier_id=shop["metro"],
            status="checked",
        )
    )
    for pid, qty in received.items():
        db.add(
            ReceiptLine(
                tenant_id=shop["tenant_id"],
                receipt_id=receipt_id,
                order_line_id=line_ids[pid],
                product_id=pid,
                qty_delivered=Decimal(str(qty)),
            )
        )
    db.commit()


def _invoice(db, shop, lines, order_id=None):
    """lines: [(product_id, qty, price)]"""
    invoice_id = str(uuid.uuid4())
    db.add(
        Invoice(
            id=invoice_id,
            tenant_id=shop["tenant_id"],
            supplier_id=shop["metro"],
            invoice_number=f"FA-{uuid.uuid4().hex[:4]}",
            order_id=order_id,
        )
    )
    for pid, qty, price in lines:
        db.add(
            InvoiceLine(
                id=str(uuid.uuid4()),
                invoice_id=invoice_id,
                product_id=pid,
                description="ligne",
                qty=Decimal(str(qty)),
                unit_price=Decimal(str(price)),
                line_total=Decimal(str(round(qty * price, 2))),
            )
        )
    db.commit()
    return db.query(Invoice).filter(Invoice.id == invoice_id).one()


# --- rattachement automatique ---------------------------------------------
def test_an_invoice_finds_its_order_by_supplier_and_products(db, shop):
    order_id, _ = _order(db, shop, [(shop["farine"], 10, 18.5)])
    invoice = _invoice(db, shop, [(shop["farine"], 10, 18.5)])  # pas de order_id

    matched = invoice_control.find_matching_order(db, shop["tenant_id"], invoice)
    assert matched is not None and str(matched.id) == order_id


def test_a_draft_order_is_never_matched(db, shop):
    """Une commande jamais partie ne se facture pas."""
    _order(db, shop, [(shop["farine"], 10, 18.5)], status=order_service.DRAFT)
    invoice = _invoice(db, shop, [(shop["farine"], 10, 18.5)])
    assert invoice_control.find_matching_order(db, shop["tenant_id"], invoice) is None


def test_no_common_product_no_match(db, shop):
    _order(db, shop, [(shop["farine"], 10, 18.5)])
    invoice = _invoice(db, shop, [(shop["beurre"], 4, 42.0)])
    assert invoice_control.find_matching_order(db, shop["tenant_id"], invoice) is None


def test_an_already_linked_order_is_used_as_is(db, shop):
    order_id, _ = _order(db, shop, [(shop["farine"], 10, 18.5)])
    invoice = _invoice(db, shop, [(shop["farine"], 10, 18.5)], order_id=order_id)
    report = invoice_control.control_for_invoice(db, shop["tenant_id"], invoice)
    assert report["linked"] is True
    assert report["order_id"] == order_id


# --- le contrôle à trois colonnes, contre la base -------------------------
def test_a_faithful_invoice_is_conform(db, shop):
    order_id, line_ids = _order(db, shop, [(shop["farine"], 10, 18.5)])
    _receive(db, shop, order_id, line_ids, {shop["farine"]: 10})
    invoice = _invoice(db, shop, [(shop["farine"], 10, 18.5)], order_id=order_id)

    report = invoice_control.control_for_invoice(db, shop["tenant_id"], invoice)
    assert report["is_conform"] is True
    assert report["lines"][0]["description"] == "Farine T55"


def test_being_billed_for_what_was_never_received(db, shop):
    """Le cas central : commandé et facturé 10, rien de reçu. Sans la colonne
    livré, cette facture passerait pour conforme au devis."""
    order_id, line_ids = _order(db, shop, [(shop["farine"], 10, 18.5)])
    _receive(db, shop, order_id, line_ids, {shop["farine"]: 0})
    invoice = _invoice(db, shop, [(shop["farine"], 10, 18.5)], order_id=order_id)

    report = invoice_control.control_for_invoice(db, shop["tenant_id"], invoice)
    assert report["is_conform"] is False
    assert report["billed_not_received_count"] == 1
    assert report["lines"][0]["status"] == invoice_control.BILLED_NOT_RECEIVED


def test_a_partial_delivery_billed_for_what_arrived_is_conform(db, shop):
    """Commandé 10, reçu 6, facturé 6 : la facture suit la livraison. Le
    manquant est un problème de commande, pas de facture."""
    order_id, line_ids = _order(db, shop, [(shop["farine"], 10, 18.5)])
    _receive(db, shop, order_id, line_ids, {shop["farine"]: 6})
    invoice = _invoice(db, shop, [(shop["farine"], 6, 18.5)], order_id=order_id)

    report = invoice_control.control_for_invoice(db, shop["tenant_id"], invoice)
    assert report["is_conform"] is True


def test_a_price_rise_between_order_and_invoice(db, shop):
    order_id, line_ids = _order(db, shop, [(shop["farine"], 10, 18.5)])
    _receive(db, shop, order_id, line_ids, {shop["farine"]: 10})
    invoice = _invoice(db, shop, [(shop["farine"], 10, 21.0)], order_id=order_id)

    line = invoice_control.control_for_invoice(db, shop["tenant_id"], invoice)["lines"][0]
    assert invoice_control.PRICE_UP in line["flags"]
    assert line["price_delta"] == 2.5


# --- rétrocompat : /quote-variance sert le nouveau contrôle ---------------
def test_the_deprecated_quote_variance_serves_the_new_control(db, shop):
    """L'application iOS en production appelle encore `/quote-variance`. Elle
    doit recevoir le nouveau contrôle, pas un rapprochement mort."""
    from fastapi.testclient import TestClient

    from app.api.deps import get_current_tenant_id
    from app.db.session import get_db
    from app.main import app

    order_id, line_ids = _order(db, shop, [(shop["farine"], 10, 18.5)])
    _receive(db, shop, order_id, line_ids, {shop["farine"]: 0})
    invoice = _invoice(db, shop, [(shop["farine"], 10, 18.5)], order_id=order_id)

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_tenant_id] = lambda: shop["tenant_id"]
    try:
        client = TestClient(app)
        old = client.get(f"/api/v1/invoices/{invoice.id}/quote-variance").json()
        new = client.get(f"/api/v1/invoices/{invoice.id}/control").json()
        assert old == new
        assert old["billed_not_received_count"] == 1
    finally:
        app.dependency_overrides.clear()
