"""L'API Réceptions de bout en bout, contre un vrai Postgres.

Ce qui se vérifie ici et nulle part ailleurs : l'immutabilité d'une réception
validée, les mouvements de stock qu'elle engendre, et l'avancement d'une
commande livrée en deux fois.
"""

import uuid
from decimal import Decimal

import pytest

from app.models.models import (
    Organization,
    Product,
    PurchaseOrder,
    PurchaseOrderLine,
    StockMovement,
    Supplier,
    User,
)
from app.services.purchasing import order_service, reception_service


def test_literal_routes_are_declared_before_the_dynamic_one():
    """Même piège que `/quotes/matrix` : déclarée après `/{receipt_id}`, une
    route littérale est avalée comme un identifiant."""
    from app.api.api_v1.endpoints.receipts import router

    paths = [r.path for r in router.routes if "GET" in getattr(r, "methods", set())]
    assert paths.index("/conditions") < paths.index("/{receipt_id}")
    assert paths.index("/from-order/{order_id}") < paths.index("/{receipt_id}")


@pytest.fixture()
def client_and_order(db):
    from fastapi.testclient import TestClient

    from app.api.deps import get_current_tenant_id, get_current_user, require_writer
    from app.db.session import get_db
    from app.main import app

    tenant_id = str(uuid.uuid4())
    db.add(Organization(id=tenant_id, name="Réception Test"))
    db.commit()

    user_id, supplier_id, product_id = (str(uuid.uuid4()) for _ in range(3))
    db.add(
        User(
            id=user_id,
            tenant_id=tenant_id,
            email=f"chef-{user_id[:8]}@test.fr",
            name="Chef Réception",
            password_hash="x",
        )
    )
    db.add(Supplier(id=supplier_id, tenant_id=tenant_id, name="METRO"))
    db.add(Product(id=product_id, tenant_id=tenant_id, name="Farine T55"))
    db.commit()

    order_id, line_id = str(uuid.uuid4()), str(uuid.uuid4())
    db.add(
        PurchaseOrder(
            id=order_id,
            tenant_id=tenant_id,
            reference="CMD-TEST-0001",
            supplier_id=supplier_id,
            status=order_service.CONFIRMED,
            total_amount=Decimal("185"),
        )
    )
    db.add(
        PurchaseOrderLine(
            id=line_id,
            tenant_id=tenant_id,
            order_id=order_id,
            product_id=product_id,
            description="Farine T55",
            qty_ordered=Decimal("10"),
            unit_price=Decimal("18.5"),
            pack_size="sac 25kg",
        )
    )
    db.commit()

    user = db.query(User).filter(User.id == user_id).one()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_current_tenant_id] = lambda: tenant_id
    app.dependency_overrides[require_writer] = lambda: []
    client = TestClient(app)
    yield client, {
        "tenant_id": tenant_id,
        "order_id": order_id,
        "line_id": line_id,
        "product_id": product_id,
        "supplier_id": supplier_id,
        "user_id": user_id,
    }
    app.dependency_overrides.clear()


def _receipt(client, ctx, qty, condition="ok", **kw):
    body = {
        "order_id": ctx["order_id"],
        "received_at": "2026-07-23",
        "lines": [
            {
                "order_line_id": ctx["line_id"],
                "product_id": ctx["product_id"],
                "description": "Farine T55",
                "qty_received": qty,
                "unit_price": kw.get("price", 18.5),
                "pack_size": kw.get("pack", "sac 25kg"),
                "condition": condition,
            }
        ],
    }
    body.update({k: v for k, v in kw.items() if k in ("supplier_id", "delivery_note_number")})
    res = client.post("/api/v1/receipts/", json=body)
    assert res.status_code == 201, res.text
    return res.json()


# --- pré-remplissage -------------------------------------------------------
def test_prefill_proposes_the_remaining_quantity(client_and_order):
    client, ctx = client_and_order
    pre = client.get(f"/api/v1/receipts/from-order/{ctx['order_id']}").json()
    assert pre["lines"][0]["qty_received"] == 10.0
    assert pre["lines"][0]["qty_already_received"] == 0.0

    _receipt(client, ctx, 4)
    pre2 = client.get(f"/api/v1/receipts/from-order/{ctx['order_id']}").json()
    # Pré-remplir avec la quantité commandée re-proposerait du déjà reçu.
    assert pre2["lines"][0]["qty_already_received"] == 4.0
    assert pre2["lines"][0]["qty_received"] == 6.0


# --- le contrôle -----------------------------------------------------------
def test_a_partial_delivery_reports_what_is_owed(client_and_order):
    client, ctx = client_and_order
    r = _receipt(client, ctx, 6)
    control = client.get(f"/api/v1/receipts/{r['id']}/control").json()
    line = control["lines"][0]
    assert line["status"] == "partial"
    assert line["qty_remaining"] == 4
    assert line["missing_value"] == 74.0
    assert control["suggested_status"] == order_service.PARTIALLY_RECEIVED


def test_a_price_gap_on_the_delivery_note_is_reported(client_and_order):
    client, ctx = client_and_order
    r = _receipt(client, ctx, 10, price=21.0)
    control = client.get(f"/api/v1/receipts/{r['id']}/control").json()
    assert "price" in control["lines"][0]["anomalies"]


def test_a_packaging_gap_is_reported(client_and_order):
    client, ctx = client_and_order
    r = _receipt(client, ctx, 10, pack="sac 10kg")
    control = client.get(f"/api/v1/receipts/{r['id']}/control").json()
    assert "pack_size" in control["lines"][0]["anomalies"]


def test_a_delivery_by_another_supplier_is_reported(db, client_and_order):
    client, ctx = client_and_order
    other = str(uuid.uuid4())
    db.add(Supplier(id=other, tenant_id=ctx["tenant_id"], name="AUTRE"))
    db.commit()
    r = _receipt(client, ctx, 10, supplier_id=other)
    control = client.get(f"/api/v1/receipts/{r['id']}/control").json()
    assert "supplier" in control["document_anomalies"]


# --- validation : ce qu'elle fige et ce qu'elle écrit ----------------------
def test_validating_freezes_the_receipt(client_and_order):
    """Une réception validée est un constat daté et signé. La modifier
    réécrirait ce qui avait été relevé à la livraison."""
    client, ctx = client_and_order
    r = _receipt(client, ctx, 10)

    # Modifiable tant qu'elle est en brouillon.
    assert client.patch(f"/api/v1/receipts/{r['id']}", json={"notes": "ok"}).status_code == 200

    out = client.post(f"/api/v1/receipts/{r['id']}/validate")
    assert out.status_code == 200
    body = out.json()
    assert body["receipt"]["status"] == "checked"
    assert body["receipt"]["status_label"] == "Contrôlée"
    assert body["receipt"]["checked_at"] is not None
    assert body["receipt"]["checked_by_name"] == "Chef Réception"

    # Après : plus rien.
    assert client.patch(f"/api/v1/receipts/{r['id']}", json={"notes": "non"}).status_code == 409
    assert client.delete(f"/api/v1/receipts/{r['id']}").status_code == 409
    assert client.post(f"/api/v1/receipts/{r['id']}/validate").status_code == 409


def test_the_receiver_is_recorded(client_and_order):
    """« Qui a signé ce bon de livraison ? » — la question posée trois semaines
    plus tard, quand le fournisseur conteste un manquant."""
    client, ctx = client_and_order
    r = _receipt(client, ctx, 10)
    assert r["received_by_name"] == "Chef Réception"


def test_validating_moves_the_order_forward(db, client_and_order):
    client, ctx = client_and_order
    r = _receipt(client, ctx, 10)
    client.post(f"/api/v1/receipts/{r['id']}/validate")
    order = db.query(PurchaseOrder).filter(PurchaseOrder.id == ctx["order_id"]).one()
    assert order.status == order_service.RECEIVED


def test_two_deliveries_complete_the_order(db, client_and_order):
    client, ctx = client_and_order
    r1 = _receipt(client, ctx, 4)
    client.post(f"/api/v1/receipts/{r1['id']}/validate")
    order = db.query(PurchaseOrder).filter(PurchaseOrder.id == ctx["order_id"]).one()
    assert order.status == order_service.PARTIALLY_RECEIVED

    r2 = _receipt(client, ctx, 6)
    control = client.post(f"/api/v1/receipts/{r2['id']}/validate").json()["control"]
    assert control["is_complete"] is True
    db.refresh(order)
    assert order.status == order_service.RECEIVED


# --- stock : la fondation se remplit --------------------------------------
def test_validating_writes_one_stock_movement_per_line(db, client_and_order):
    client, ctx = client_and_order
    r = _receipt(client, ctx, 10)
    assert (
        db.query(StockMovement)
        .filter(StockMovement.tenant_id == ctx["tenant_id"])
        .count()
        == 0
    ), "un brouillon n'entre pas en stock"

    client.post(f"/api/v1/receipts/{r['id']}/validate")
    moves = (
        db.query(StockMovement).filter(StockMovement.tenant_id == ctx["tenant_id"]).all()
    )
    assert len(moves) == 1
    m = moves[0]
    assert float(m.qty) == 10.0, "quantité signée : + entrée"
    assert m.movement_type == "receipt"
    assert m.source_type == "receipt_line"
    assert float(m.unit_cost) == 18.5, "valorisation figée au moment du mouvement"


def test_a_rejected_line_never_enters_stock(db, client_and_order):
    """Refusée, la marchandise repart. L'entrer puis la sortir laisserait deux
    mouvements pour un fait qui n'a pas eu lieu."""
    client, ctx = client_and_order
    r = _receipt(client, ctx, 10, condition="rejected")
    client.post(f"/api/v1/receipts/{r['id']}/validate")
    assert (
        db.query(StockMovement)
        .filter(StockMovement.tenant_id == ctx["tenant_id"])
        .count()
        == 0
    )
    order = db.query(PurchaseOrder).filter(PurchaseOrder.id == ctx["order_id"]).one()
    assert order.status == order_service.CONFIRMED, "la commande reste due"


def test_a_damaged_line_does_enter_stock(db, client_and_order):
    """Abîmée, elle est bien en réserve : c'est une perte à venir, pas un
    manquant."""
    client, ctx = client_and_order
    r = _receipt(client, ctx, 10, condition="damaged")
    client.post(f"/api/v1/receipts/{r['id']}/validate")
    assert (
        db.query(StockMovement)
        .filter(StockMovement.tenant_id == ctx["tenant_id"])
        .count()
        == 1
    )


# --- listing et suppression ------------------------------------------------
def test_receipts_can_be_listed_for_an_order(client_and_order):
    client, ctx = client_and_order
    _receipt(client, ctx, 4)
    _receipt(client, ctx, 6)
    listed = client.get("/api/v1/receipts/", params={"order_id": ctx["order_id"]}).json()
    assert len(listed) == 2
    assert all(r["order_reference"] == "CMD-TEST-0001" for r in listed)


def test_a_draft_receipt_can_still_be_deleted(client_and_order):
    client, ctx = client_and_order
    r = _receipt(client, ctx, 10)
    assert client.delete(f"/api/v1/receipts/{r['id']}").status_code == 204


def test_conditions_are_served_with_french_labels(client_and_order):
    client, _ = client_and_order
    conditions = client.get("/api/v1/receipts/conditions").json()
    values = {c["value"] for c in conditions}
    assert {"ok", "missing", "extra", "substituted", "damaged", "rejected"} == values
    assert all(c["label"] for c in conditions)


def test_an_unknown_receipt_answers_404(client_and_order):
    client, _ = client_and_order
    assert client.get(f"/api/v1/receipts/{uuid.uuid4()}").status_code == 404
