"""L'API Réceptions de bout en bout, contre un vrai Postgres.

Les scénarios sont ceux du métier, pas des cas d'école : livraison complète,
partielle, refusée, produit remplacé, mauvais conditionnement, casse, et la
réception corrective qui rattrape la précédente.

Ce qui se vérifie ici et nulle part ailleurs : l'immutabilité d'une réception
validée, les mouvements de stock qu'elle engendre, et l'avancement d'une
commande livrée en plusieurs fois.
"""

import uuid
from decimal import Decimal

import pytest

from app.models.models import (
    Organization,
    Product,
    PurchaseOrder,
    PurchaseOrderLine,
    ReceiptLineIssue,
    ReceiptLinePhoto,
    StockMovement,
    Supplier,
    User,
)
from app.services.purchasing import order_service


def test_literal_routes_are_declared_before_the_dynamic_one():
    """Même piège que `/quotes/matrix` : déclarée après `/{receipt_id}`, une
    route littérale est avalée comme un identifiant."""
    from app.api.api_v1.endpoints.receipts import router

    paths = [r.path for r in router.routes if "GET" in getattr(r, "methods", set())]
    assert paths.index("/quality-checks") < paths.index("/{receipt_id}")
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

    user_id, supplier_id, product_id, other_product = (str(uuid.uuid4()) for _ in range(4))
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
    db.add(Product(id=other_product, tenant_id=tenant_id, name="Farine T65"))
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
        "other_product": other_product,
        "supplier_id": supplier_id,
        "user_id": user_id,
    }
    app.dependency_overrides.clear()


def _receipt(client, ctx, qty, issues=None, photos=None, **kw):
    line = {
        "order_line_id": ctx["line_id"],
        "product_id": ctx["product_id"],
        "description": "Farine T55",
        "qty_delivered": qty,
        "unit_price": kw.pop("price", 18.5),
        "pack_size": kw.pop("pack", "sac 25kg"),
        "issues": issues or [],
        "photos": photos or [],
    }
    if "substituted_product_id" in kw:
        line["substituted_product_id"] = kw.pop("substituted_product_id")

    body = {"order_id": ctx["order_id"], "received_at": "2026-07-23", "lines": [line]}
    body.update(kw)
    res = client.post("/api/v1/receipts/", json=body)
    assert res.status_code == 201, res.text
    return res.json()


def _control(client, receipt):
    return client.get(f"/api/v1/receipts/{receipt['id']}/control").json()


def _moves(db, ctx):
    return db.query(StockMovement).filter(StockMovement.tenant_id == ctx["tenant_id"]).all()


# --------------------------------------------------------------------------- #
# Scénario 1 — livraison complète
# --------------------------------------------------------------------------- #
def test_a_complete_delivery_closes_the_order_and_enters_stock(db, client_and_order):
    client, ctx = client_and_order
    r = _receipt(client, ctx, 10)

    assert _moves(db, ctx) == [], "un brouillon n'entre pas en stock"
    out = client.post(f"/api/v1/receipts/{r['id']}/validate").json()
    assert out["control"]["is_complete"] is True

    order = db.query(PurchaseOrder).filter(PurchaseOrder.id == ctx["order_id"]).one()
    assert order.status == order_service.RECEIVED

    moves = _moves(db, ctx)
    assert len(moves) == 1
    assert float(moves[0].qty) == 10.0, "quantité signée : + entrée"
    assert float(moves[0].unit_cost) == 18.5, "valorisation figée"


# --------------------------------------------------------------------------- #
# Scénario 2 — livraison partielle, puis le reste
# --------------------------------------------------------------------------- #
def test_a_partial_delivery_states_the_remainder(client_and_order):
    client, ctx = client_and_order
    r = _receipt(client, ctx, 6)
    line = _control(client, r)["lines"][0]
    assert line["status"] == "partial"
    assert line["qty_remaining"] == 4
    assert line["missing_value"] == 74.0


def test_the_prefill_proposes_only_what_is_still_due(client_and_order):
    client, ctx = client_and_order
    r = _receipt(client, ctx, 4)
    client.post(f"/api/v1/receipts/{r['id']}/validate")

    pre = client.get(f"/api/v1/receipts/from-order/{ctx['order_id']}").json()
    # Pré-remplir avec la quantité commandée re-proposerait du déjà reçu.
    assert pre["lines"][0]["qty_already_received"] == 4.0
    assert pre["lines"][0]["qty_delivered"] == 6.0


def test_two_deliveries_complete_the_order(db, client_and_order):
    client, ctx = client_and_order
    r1 = _receipt(client, ctx, 4)
    client.post(f"/api/v1/receipts/{r1['id']}/validate")
    order = db.query(PurchaseOrder).filter(PurchaseOrder.id == ctx["order_id"]).one()
    assert order.status == order_service.PARTIALLY_RECEIVED

    r2 = _receipt(client, ctx, 6)
    assert client.post(f"/api/v1/receipts/{r2['id']}/validate").json()["control"][
        "is_complete"
    ] is True
    db.refresh(order)
    assert order.status == order_service.RECEIVED
    assert len(_moves(db, ctx)) == 2


# --------------------------------------------------------------------------- #
# Scénario 3 — livraison refusée, puis réception corrective
# --------------------------------------------------------------------------- #
def test_a_refused_delivery_enters_nothing_and_leaves_the_order_due(db, client_and_order):
    client, ctx = client_and_order
    r = _receipt(
        client, ctx, 10,
        issues=[{"reason": "short_shelf_life", "outcome": "rejected"}],
    )
    out = client.post(f"/api/v1/receipts/{r['id']}/validate").json()

    assert out["control"]["is_complete"] is False
    assert out["control"]["rejected_count"] == 1
    assert _moves(db, ctx) == [], "ce qui repart n'entre jamais en stock"
    order = db.query(PurchaseOrder).filter(PurchaseOrder.id == ctx["order_id"]).one()
    assert order.status == order_service.CONFIRMED, "la commande reste due"


def test_a_corrective_receipt_settles_what_was_refused(db, client_and_order):
    """Le refus n'ayant rien apporté, la livraison suivante solde la commande."""
    client, ctx = client_and_order
    bad = _receipt(client, ctx, 10, issues=[{"reason": "breakage", "outcome": "rejected"}])
    client.post(f"/api/v1/receipts/{bad['id']}/validate")

    good = _receipt(client, ctx, 10)
    out = client.post(f"/api/v1/receipts/{good['id']}/validate").json()
    assert out["control"]["is_complete"] is True

    order = db.query(PurchaseOrder).filter(PurchaseOrder.id == ctx["order_id"]).one()
    assert order.status == order_service.RECEIVED
    # Les deux réceptions restent au dossier : la mauvaise n'est pas effacée.
    assert len(client.get("/api/v1/receipts/", params={"order_id": ctx["order_id"]}).json()) == 2


# --------------------------------------------------------------------------- #
# Scénario 4 — contrôle qualité fin
# --------------------------------------------------------------------------- #
def test_the_case_that_justified_the_model(db, client_and_order):
    """Sur 10 : 1 refusée DLC, 1 détruite casse, 3 gardées sous réserve.
    Le modèle précédent obligeait à choisir un seul motif."""
    client, ctx = client_and_order
    r = _receipt(
        client, ctx, 10,
        issues=[
            {"qty": 1, "reason": "short_shelf_life", "outcome": "rejected"},
            {"qty": 1, "reason": "breakage", "outcome": "destroyed"},
            {"qty": 3, "reason": "packaging_damaged", "outcome": "accepted"},
        ],
    )
    line = r["lines"][0]
    assert line["qty_delivered"] == 10.0
    assert line["qty_accepted"] == 8.0
    assert line["qty_rejected"] == 1.0
    assert line["qty_destroyed"] == 1.0
    assert line["state"] == "partiellement_conforme"
    assert line["state_label"] == "Partiellement conforme"
    assert len(line["issues"]) == 3
    assert {i["reason_label"] for i in line["issues"]} == {
        "DLC/DLUO trop courte",
        "Casse",
        "Emballage endommagé",
    }

    client.post(f"/api/v1/receipts/{r['id']}/validate")
    moves = _moves(db, ctx)
    assert len(moves) == 1
    assert float(moves[0].qty) == 8.0, "seul l'accepté entre en stock"


def test_several_photos_can_document_one_line(db, client_and_order):
    client, ctx = client_and_order
    r = _receipt(
        client, ctx, 10,
        issues=[{"qty": 2, "reason": "breakage", "outcome": "destroyed"}],
        photos=[
            {"url": "https://x/1.jpg", "caption": "carton éventré"},
            {"url": "https://x/2.jpg", "caption": "palette"},
        ],
    )
    assert len(r["lines"][0]["photos"]) == 2
    assert (
        db.query(ReceiptLinePhoto)
        .filter(ReceiptLinePhoto.tenant_id == ctx["tenant_id"])
        .count()
        == 2
    )


def test_a_substituted_product_is_reported(client_and_order):
    client, ctx = client_and_order
    r = _receipt(client, ctx, 10, substituted_product_id=ctx["other_product"])
    assert r["lines"][0]["state"] == "remplacee"
    assert r["lines"][0]["substituted_product_name"] == "Farine T65"
    assert "product" in _control(client, r)["lines"][0]["anomalies"]


def test_a_wrong_packaging_is_reported(client_and_order):
    client, ctx = client_and_order
    r = _receipt(client, ctx, 10, pack="sac 10kg")
    assert "pack_size" in _control(client, r)["lines"][0]["anomalies"]


def test_a_price_gap_on_the_delivery_note_is_reported(client_and_order):
    client, ctx = client_and_order
    r = _receipt(client, ctx, 10, price=21.0)
    assert "price" in _control(client, r)["lines"][0]["anomalies"]


def test_a_delivery_by_another_supplier_is_reported(db, client_and_order):
    client, ctx = client_and_order
    other = str(uuid.uuid4())
    db.add(Supplier(id=other, tenant_id=ctx["tenant_id"], name="AUTRE"))
    db.commit()
    r = _receipt(client, ctx, 10, supplier_id=other)
    assert "supplier" in _control(client, r)["document_anomalies"]


# --------------------------------------------------------------------------- #
# Immutabilité et traçabilité
# --------------------------------------------------------------------------- #
def test_validating_freezes_the_receipt(client_and_order):
    """Une réception validée est un constat daté et signé. La modifier
    réécrirait ce qui avait été relevé à la livraison."""
    client, ctx = client_and_order
    r = _receipt(client, ctx, 10)
    assert client.patch(f"/api/v1/receipts/{r['id']}", json={"notes": "ok"}).status_code == 200

    body = client.post(f"/api/v1/receipts/{r['id']}/validate").json()
    assert body["receipt"]["status_label"] == "Contrôlée"
    assert body["receipt"]["checked_by_name"] == "Chef Réception"
    assert body["receipt"]["checked_at"] is not None

    assert client.patch(f"/api/v1/receipts/{r['id']}", json={"notes": "non"}).status_code == 409
    assert client.delete(f"/api/v1/receipts/{r['id']}").status_code == 409
    assert client.post(f"/api/v1/receipts/{r['id']}/validate").status_code == 409


def test_who_received_and_on_which_device_is_recorded(client_and_order):
    """« Qui a signé ce bon de livraison, et sur quoi ? » — les questions posées
    trois semaines après, quand le fournisseur conteste un manquant."""
    client, ctx = client_and_order
    r = _receipt(client, ctx, 10, device_info="Android · Pixel 6")
    assert r["received_by_name"] == "Chef Réception"
    assert r["device_info"] == "Android · Pixel 6"


def test_editing_a_draft_replaces_its_issues(db, client_and_order):
    """Une réception en brouillon est un travail en cours : elle se réécrit
    entièrement, sans laisser d'anomalies orphelines."""
    client, ctx = client_and_order
    r = _receipt(client, ctx, 10, issues=[{"qty": 2, "reason": "breakage", "outcome": "destroyed"}])
    assert db.query(ReceiptLineIssue).filter(
        ReceiptLineIssue.tenant_id == ctx["tenant_id"]
    ).count() == 1

    client.patch(
        f"/api/v1/receipts/{r['id']}",
        json={
            "lines": [
                {
                    "order_line_id": ctx["line_id"],
                    "product_id": ctx["product_id"],
                    "qty_delivered": 10,
                    "issues": [],
                }
            ]
        },
    )
    assert db.query(ReceiptLineIssue).filter(
        ReceiptLineIssue.tenant_id == ctx["tenant_id"]
    ).count() == 0


def test_a_draft_receipt_can_still_be_deleted(client_and_order):
    client, ctx = client_and_order
    r = _receipt(client, ctx, 10)
    assert client.delete(f"/api/v1/receipts/{r['id']}").status_code == 204


def test_deleting_a_receipt_takes_its_issues_and_photos_with_it(db, client_and_order):
    client, ctx = client_and_order
    r = _receipt(
        client, ctx, 10,
        issues=[{"qty": 1, "reason": "breakage", "outcome": "destroyed"}],
        photos=[{"url": "https://x/1.jpg"}],
    )
    client.delete(f"/api/v1/receipts/{r['id']}")
    assert db.query(ReceiptLineIssue).filter(
        ReceiptLineIssue.tenant_id == ctx["tenant_id"]
    ).count() == 0
    assert db.query(ReceiptLinePhoto).filter(
        ReceiptLinePhoto.tenant_id == ctx["tenant_id"]
    ).count() == 0


# --------------------------------------------------------------------------- #
# Vocabulaire servi par l'API
# --------------------------------------------------------------------------- #
def test_the_quality_vocabulary_is_served_in_french(client_and_order):
    client, _ = client_and_order
    vocab = client.get("/api/v1/receipts/quality-checks").json()
    reasons = {r["value"] for r in vocab["reasons"]}
    assert {
        "packaging_damaged", "product_damaged", "short_shelf_life", "wrong_grade",
        "wrong_temperature", "wrong_packaging", "substituted", "breakage",
    } <= reasons
    assert {o["value"] for o in vocab["outcomes"]} == {"accepted", "rejected", "destroyed"}
    assert all(r["label"] for r in vocab["reasons"])
    assert all(s["label"] for s in vocab["line_states"])


def test_an_unknown_receipt_answers_404(client_and_order):
    client, _ = client_and_order
    assert client.get(f"/api/v1/receipts/{uuid.uuid4()}").status_code == 404
