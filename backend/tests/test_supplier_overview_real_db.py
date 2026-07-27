"""Fiche fournisseur 360° contre un vrai Postgres.

Ce qui se vérifie ici et nulle part ailleurs : l'assemblage réel depuis toutes
les tables du domaine (commandes, réceptions validées, factures, historique),
et le fait que seules les réceptions VALIDÉES pèsent dans le score.
"""

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.models.models import (
    Invoice,
    Organization,
    Product,
    PurchaseHistory,
    PurchaseOrder,
    Receipt,
    ReceiptLine,
    ReceiptLineIssue,
    Supplier,
)


@pytest.fixture()
def client_and_supplier(db):
    from fastapi.testclient import TestClient

    from app.api.deps import get_current_tenant_id
    from app.db.session import get_db
    from app.main import app

    tenant_id, sid, pid = (str(uuid.uuid4()) for _ in range(3))
    db.add(Organization(id=tenant_id, name="Fournisseur 360"))
    db.commit()
    db.add(Supplier(id=sid, tenant_id=tenant_id, name="METRO", rating=Decimal("4")))
    db.add(Product(id=pid, tenant_id=tenant_id, name="Farine T55"))
    db.commit()

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_tenant_id] = lambda: tenant_id
    client = TestClient(app)
    yield client, {"tenant_id": tenant_id, "supplier_id": sid, "product_id": pid}
    app.dependency_overrides.clear()


def _overview(client, sid):
    r = client.get(f"/api/v1/suppliers/{sid}/overview")
    assert r.status_code == 200, r.text
    return r.json()


def test_a_fresh_supplier_has_volumes_at_zero_and_no_score(client_and_supplier):
    client, ctx = client_and_supplier
    o = _overview(client, ctx["supplier_id"])
    assert o["supplier_name"] == "METRO"
    assert o["rating"] == 4.0  # note manuelle, distincte du score calculé
    assert o["score"] is None
    assert o["order_count"] == 0
    assert o["annual_amount"] == 0


def test_the_overview_assembles_every_domain_table(db, client_and_supplier):
    client, ctx = client_and_supplier
    tid, sid, pid = ctx["tenant_id"], ctx["supplier_id"], ctx["product_id"]

    db.add(PurchaseOrder(tenant_id=tid, reference="CMD-1", supplier_id=sid,
                         status="received", total_amount=Decimal("185")))
    db.add(PurchaseOrder(tenant_id=tid, reference="CMD-2", supplier_id=sid,
                         status="cancelled", total_amount=Decimal("999")))
    db.add(Invoice(tenant_id=tid, supplier_id=sid, invoice_number="FA-1",
                   total_amount=Decimal("185"), date=date.today()))
    db.add(PurchaseHistory(id=str(uuid.uuid4()), tenant_id=tid, supplier_id=sid,
                           product_id=pid, purchase_date=date.today(),
                           total_price=Decimal("185"), unit_cost_standard=Decimal("18.5")))
    db.commit()

    o = _overview(client, sid)
    assert o["order_count"] == 1, "la commande annulée ne compte pas"
    assert o["orders_by_status"]["cancelled"] == 1
    assert o["invoice_count"] == 1
    assert o["annual_amount"] == 185.0
    assert o["top_products"][0]["product_name"] == "Farine T55"


def test_only_checked_receptions_weigh_in_the_score(db, client_and_supplier):
    """Un brouillon de réception n'engage pas le fournisseur : il ne doit pas
    entrer dans sa conformité."""
    client, ctx = client_and_supplier
    tid, sid, pid = ctx["tenant_id"], ctx["supplier_id"], ctx["product_id"]

    # Une réception validée conforme…
    good = str(uuid.uuid4())
    db.add(Receipt(id=good, tenant_id=tid, reference="REC-1", supplier_id=sid,
                   status="checked", received_at=date.today()))
    db.add(ReceiptLine(tenant_id=tid, receipt_id=good, product_id=pid,
                       qty_delivered=Decimal("10")))
    # …et un brouillon avec une anomalie, qui ne doit PAS compter.
    draft = str(uuid.uuid4())
    db.add(Receipt(id=draft, tenant_id=tid, reference="REC-2", supplier_id=sid,
                   status="draft", received_at=date.today()))
    draft_line = str(uuid.uuid4())
    db.add(ReceiptLine(id=draft_line, tenant_id=tid, receipt_id=draft, product_id=pid,
                       qty_delivered=Decimal("5")))
    db.add(ReceiptLineIssue(tenant_id=tid, receipt_line_id=draft_line,
                            reason="breakage", outcome="rejected"))
    db.commit()

    o = _overview(client, sid)
    assert o["receipt_count"] == 1, "seule la réception validée compte"
    assert o["conformity_rate"] == 1.0
    assert o["score"] == 100


def test_a_reception_with_an_issue_lowers_conformity(db, client_and_supplier):
    client, ctx = client_and_supplier
    tid, sid, pid = ctx["tenant_id"], ctx["supplier_id"], ctx["product_id"]

    for i, has_issue in enumerate([False, True]):
        rid, lid = str(uuid.uuid4()), str(uuid.uuid4())
        db.add(Receipt(id=rid, tenant_id=tid, reference=f"REC-{i}", supplier_id=sid,
                       status="checked", received_at=date.today()))
        db.add(ReceiptLine(id=lid, tenant_id=tid, receipt_id=rid, product_id=pid,
                           qty_delivered=Decimal("10")))
        if has_issue:
            db.add(ReceiptLineIssue(tenant_id=tid, receipt_line_id=lid,
                                    reason="short_shelf_life", outcome="rejected"))
    db.commit()

    o = _overview(client, sid)
    assert o["conformity_rate"] == 0.5


def test_a_late_reception_is_counted_against_punctuality(db, client_and_supplier):
    client, ctx = client_and_supplier
    tid, sid, pid = ctx["tenant_id"], ctx["supplier_id"], ctx["product_id"]

    order_id = str(uuid.uuid4())
    db.add(PurchaseOrder(id=order_id, tenant_id=tid, reference="CMD-L", supplier_id=sid,
                         status="received", expected_date=date.today() - timedelta(days=3)))
    rid = str(uuid.uuid4())
    db.add(Receipt(id=rid, tenant_id=tid, reference="REC-L", supplier_id=sid, order_id=order_id,
                   status="checked", received_at=date.today()))  # 3 jours de retard
    db.add(ReceiptLine(tenant_id=tid, receipt_id=rid, product_id=pid, qty_delivered=Decimal("10")))
    db.commit()

    o = _overview(client, sid)
    assert o["late_count"] == 1
    assert o["on_time_rate"] == 0.0


def test_an_unknown_supplier_answers_404(client_and_supplier):
    client, _ = client_and_supplier
    assert client.get(f"/api/v1/suppliers/{uuid.uuid4()}/overview").status_code == 404
