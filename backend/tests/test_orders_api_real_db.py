"""L'API Commandes de bout en bout, contre un vrai Postgres.

Ce qui est vérifié ici ne l'est nulle part ailleurs : la traversée complète
comparateur → plan → commandes, les règles de refus (transitions interdites,
suppression d'un engagement déjà pris) et le cloisonnement entre organisations.
"""

import uuid
from decimal import Decimal

import pytest

from app.models.models import Organization, Product, PurchaseOrder, Quote, QuoteLine, Supplier
from app.services.purchasing import order_service


# --- garde-fou d'ordre de routes (pur, tourne partout) --------------------
def test_literal_routes_are_declared_before_the_dynamic_one():
    """Même piège que `/quotes/matrix` en production : déclarée après
    `/{order_id}`, une route littérale est avalée comme un identifiant et
    Postgres reçoit « statuses » en guise d'UUID."""
    from app.api.api_v1.endpoints.orders import router

    get_paths = [r.path for r in router.routes if "GET" in getattr(r, "methods", set())]
    assert get_paths.index("/statuses") < get_paths.index("/{order_id}")

    post_paths = [r.path for r in router.routes if "POST" in getattr(r, "methods", set())]
    assert "/plan" in post_paths and "/from-quote-lines" in post_paths


def test_every_status_has_a_french_label():
    """Les libellés sont servis par l'API pour que web et mobile n'entretiennent
    pas chacun leur traduction. Un état sans libellé s'afficherait en anglais
    sur les deux surfaces."""
    for status in order_service.STATUSES:
        assert order_service.STATUS_LABELS.get(status), status


# --- API contre une vraie base --------------------------------------------
@pytest.fixture()
def client_and_shop(db):
    """Un client HTTP authentifié comme admin d'une organisation neuve."""
    from fastapi.testclient import TestClient

    from app.api.deps import get_current_tenant_id, require_writer
    from app.db.session import get_db
    from app.main import app

    tenant_id = str(uuid.uuid4())
    db.add(Organization(id=tenant_id, name="Achats API"))
    db.commit()

    metro, transgourmet = str(uuid.uuid4()), str(uuid.uuid4())
    farine, beurre = str(uuid.uuid4()), str(uuid.uuid4())
    db.add(Supplier(id=metro, tenant_id=tenant_id, name="METRO"))
    db.add(Supplier(id=transgourmet, tenant_id=tenant_id, name="TRANSGOURMET"))
    db.add(Product(id=farine, tenant_id=tenant_id, name="Farine T55"))
    db.add(Product(id=beurre, tenant_id=tenant_id, name="Beurre doux"))
    db.commit()

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_tenant_id] = lambda: tenant_id
    app.dependency_overrides[require_writer] = lambda: []
    client = TestClient(app)
    yield client, {
        "tenant_id": tenant_id,
        "metro": metro,
        "transgourmet": transgourmet,
        "farine": farine,
        "beurre": beurre,
    }
    app.dependency_overrides.clear()


def _quote_line(db, shop, supplier_id, product_id, qty, price, delivery_fee=None):
    quote_id, line_id = str(uuid.uuid4()), str(uuid.uuid4())
    db.add(
        Quote(
            id=quote_id,
            tenant_id=shop["tenant_id"],
            reference=f"DEV-API-{uuid.uuid4().hex[:4]}",
            supplier_id=supplier_id,
            status="draft",
            currency="EUR",
            delivery_fee=Decimal(str(delivery_fee)) if delivery_fee is not None else None,
        )
    )
    db.add(
        QuoteLine(
            id=line_id,
            tenant_id=shop["tenant_id"],
            quote_id=quote_id,
            product_id=product_id,
            supplier_id=supplier_id,
            description="ligne",
            qty=Decimal(str(qty)),
            unit_price=Decimal(str(price)),
        )
    )
    db.commit()
    return line_id


def test_the_whole_trip_from_comparator_to_orders(db, client_and_shop):
    """Le parcours que le remaniement rend possible : deux offres retenues chez
    deux fournisseurs différents deviennent deux commandes."""
    client, shop = client_and_shop
    l1 = _quote_line(db, shop, shop["metro"], shop["farine"], 10, 18.5)
    l2 = _quote_line(db, shop, shop["transgourmet"], shop["beurre"], 4, 42.0)

    # 1. L'aperçu ne crée rien.
    plan = client.post("/api/v1/orders/plan", json={"quote_line_ids": [l1, l2]})
    assert plan.status_code == 200
    assert len(plan.json()) == 2
    assert db.query(PurchaseOrder).filter(
        PurchaseOrder.tenant_id == shop["tenant_id"]
    ).count() == 0, "l'aperçu ne doit rien engager"

    # 2. La commande, elle, crée.
    res = client.post("/api/v1/orders/from-quote-lines", json={"quote_line_ids": [l1, l2]})
    assert res.status_code == 201
    body = res.json()
    assert body["order_count"] == 2
    assert body["supplier_count"] == 2
    assert body["total_amount"] == 353.0  # 185 + 168

    listed = client.get("/api/v1/orders/").json()
    assert len(listed) == 2
    assert all(o["status"] == "draft" for o in listed)
    assert all(o["status_label"] == "Brouillon" for o in listed)


def test_an_order_carries_its_lines_and_their_origin(db, client_and_shop):
    client, shop = client_and_shop
    line_id = _quote_line(db, shop, shop["metro"], shop["farine"], 10, 18.5)
    order = client.post(
        "/api/v1/orders/from-quote-lines", json={"quote_line_ids": [line_id]}
    ).json()["orders"][0]

    detail = client.get(f"/api/v1/orders/{order['id']}").json()
    assert detail["line_count"] == 1
    line = detail["lines"][0]
    assert line["product_name"] == "Farine T55"
    assert line["unit_price"] == 18.5
    assert line["source_quote_line_id"] == line_id
    assert line["qty_received"] == 0.0


def test_the_shipping_cost_reaches_the_order(db, client_and_shop):
    client, shop = client_and_shop
    line_id = _quote_line(db, shop, shop["metro"], shop["farine"], 10, 10.0, delivery_fee=50)
    body = client.post(
        "/api/v1/orders/from-quote-lines", json={"quote_line_ids": [line_id]}
    ).json()
    assert body["orders"][0]["delivery_fee"] == 50.0
    assert body["total_amount"] == 150.0


def test_ordering_nothing_is_refused(client_and_shop):
    client, _ = client_and_shop
    res = client.post(
        "/api/v1/orders/from-quote-lines", json={"quote_line_ids": [str(uuid.uuid4())]}
    )
    assert res.status_code == 404


def test_an_order_cannot_be_born_already_delivered(db, client_and_shop):
    client, shop = client_and_shop
    line_id = _quote_line(db, shop, shop["metro"], shop["farine"], 10, 18.5)
    res = client.post(
        "/api/v1/orders/from-quote-lines",
        json={"quote_line_ids": [line_id], "status": "received"},
    )
    assert res.status_code == 400


# --- cycle de vie ---------------------------------------------------------
def test_an_impossible_transition_is_refused_with_a_readable_reason(db, client_and_shop):
    client, shop = client_and_shop
    line_id = _quote_line(db, shop, shop["metro"], shop["farine"], 10, 18.5)
    order = client.post(
        "/api/v1/orders/from-quote-lines", json={"quote_line_ids": [line_id]}
    ).json()["orders"][0]

    ok = client.patch(f"/api/v1/orders/{order['id']}", json={"status": "sent"})
    assert ok.status_code == 200
    assert ok.json()["status_label"] == "Envoyée"

    # Brouillon → Terminée directement : non.
    ko = client.patch(f"/api/v1/orders/{order['id']}", json={"status": "closed"})
    assert ko.status_code == 409
    assert "Envoyée" in ko.json()["detail"], "le message doit nommer l'état courant"


def test_sending_an_order_timestamps_it(db, client_and_shop):
    """« Envoyée quand ? » et « confirmée quand ? » sont les deux questions
    qu'on pose à un fournisseur en retard."""
    client, shop = client_and_shop
    line_id = _quote_line(db, shop, shop["metro"], shop["farine"], 10, 18.5)
    order_id = client.post(
        "/api/v1/orders/from-quote-lines", json={"quote_line_ids": [line_id]}
    ).json()["orders"][0]["id"]

    client.patch(f"/api/v1/orders/{order_id}", json={"status": "sent"})
    client.patch(f"/api/v1/orders/{order_id}", json={"status": "confirmed"})
    row = db.query(PurchaseOrder).filter(PurchaseOrder.id == order_id).one()
    assert row.sent_at is not None
    assert row.confirmed_at is not None


def test_a_committed_order_is_cancelled_not_deleted(db, client_and_shop):
    """Effacer la trace d'un engagement pris réécrirait l'histoire — c'est
    exactement ce qu'un ERP doit empêcher."""
    client, shop = client_and_shop
    line_id = _quote_line(db, shop, shop["metro"], shop["farine"], 10, 18.5)
    order_id = client.post(
        "/api/v1/orders/from-quote-lines", json={"quote_line_ids": [line_id]}
    ).json()["orders"][0]["id"]

    client.patch(f"/api/v1/orders/{order_id}", json={"status": "sent"})
    assert client.delete(f"/api/v1/orders/{order_id}").status_code == 409

    client.patch(f"/api/v1/orders/{order_id}", json={"status": "cancelled"})
    assert client.delete(f"/api/v1/orders/{order_id}").status_code == 204


def test_a_draft_order_can_still_be_deleted(db, client_and_shop):
    client, shop = client_and_shop
    line_id = _quote_line(db, shop, shop["metro"], shop["farine"], 10, 18.5)
    order_id = client.post(
        "/api/v1/orders/from-quote-lines", json={"quote_line_ids": [line_id]}
    ).json()["orders"][0]["id"]
    assert client.delete(f"/api/v1/orders/{order_id}").status_code == 204


def test_an_unknown_order_answers_404_not_500(client_and_shop):
    """La route littérale `/statuses` ne doit pas non plus être prise pour un
    identifiant."""
    client, _ = client_and_shop
    assert client.get(f"/api/v1/orders/{uuid.uuid4()}").status_code == 404
    assert client.get("/api/v1/orders/statuses").status_code == 200


def test_progress_starts_at_nothing_received(db, client_and_shop):
    client, shop = client_and_shop
    line_id = _quote_line(db, shop, shop["metro"], shop["farine"], 10, 18.5)
    order_id = client.post(
        "/api/v1/orders/from-quote-lines", json={"quote_line_ids": [line_id]}
    ).json()["orders"][0]["id"]

    p = client.get(f"/api/v1/orders/{order_id}/progress").json()
    assert p["nothing_received"] is True
    assert p["lines"][0]["status"] == "pending"
    assert p["suggested_status"] is None


def test_an_order_with_receipts_cannot_be_deleted(db, client_and_shop):
    """Incohérence trouvée au nettoyage des données de test : une réception
    validée est indestructible, mais la commande qui la porte pouvait, elle,
    disparaître — laissant un constat signé qui référence une commande
    inexistante, donc invérifiable. La contrainte doit tenir des deux côtés."""
    from app.models.models import Receipt

    client, shop = client_and_shop
    line_id = _quote_line(db, shop, shop["metro"], shop["farine"], 10, 18.5)
    order_id = client.post(
        "/api/v1/orders/from-quote-lines", json={"quote_line_ids": [line_id]}
    ).json()["orders"][0]["id"]

    db.add(
        Receipt(
            tenant_id=shop["tenant_id"],
            reference="REC-TEST-0001",
            order_id=order_id,
            status="checked",
        )
    )
    db.commit()

    res = client.delete(f"/api/v1/orders/{order_id}")
    assert res.status_code == 409
    assert "réception" in res.json()["detail"].lower()
