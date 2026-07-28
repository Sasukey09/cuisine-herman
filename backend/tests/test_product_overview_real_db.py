"""Fiche produit 360° contre un vrai Postgres, via GET /products/{id}/overview.
Skip en local sans DATABASE_URL, tourne en CI."""
import uuid
from datetime import date, datetime
from decimal import Decimal

import pytest

from app.models.models import (
    Organization, Product, Supplier, PurchaseHistory, PurchaseOrder,
    PurchaseOrderLine, Quote, QuoteLine, Recipe, RecipeVersion, RecipeIngredient,
)


@pytest.fixture()
def client_ctx(db):
    from fastapi.testclient import TestClient
    from app.api.deps import get_current_tenant_id
    from app.db.session import get_db
    from app.main import app
    from app.services.costing import cost_engine

    cost_engine.reset_unit_cache()
    tid, metro, transg, pid = (str(uuid.uuid4()) for _ in range(4))
    db.add(Organization(id=tid, name="Produit 360"))
    db.commit()
    db.add(Supplier(id=metro, tenant_id=tid, name="METRO"))
    db.add(Supplier(id=transg, tenant_id=tid, name="TRANSGOURMET"))
    db.add(Product(id=pid, tenant_id=tid, name="Beurre"))
    db.commit()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_tenant_id] = lambda: tid
    client = TestClient(app)
    yield client, {"tenant_id": tid, "metro": metro, "transg": transg, "product": pid}
    app.dependency_overrides.clear()
    cost_engine.reset_unit_cache()


def _ov(client, pid):
    r = client.get(f"/api/v1/products/{pid}/overview")
    assert r.status_code == 200, r.text
    return r.json()


def test_a_fresh_product_is_zeros(client_ctx):
    client, c = client_ctx
    o = _ov(client, c["product"])
    assert o["product_name"] == "Beurre"
    assert o["annual_amount"] == 0 and o["top_suppliers"] == [] and o["offers"] is None
    assert "score" not in o and "conformity_rate" not in o   # produit-centré


def test_overview_assembles_spend_offers_and_recipes(db, client_ctx):
    client, c = client_ctx
    tid, metro, transg, pid = c["tenant_id"], c["metro"], c["transg"], c["product"]
    today = date.today()
    # achats des deux fournisseurs
    for sid, tot, cost in [(metro, Decimal("185"), Decimal("18.5")), (transg, Decimal("200"), Decimal("20"))]:
        db.add(PurchaseHistory(id=str(uuid.uuid4()), tenant_id=tid, supplier_id=sid, product_id=pid,
                               purchase_date=today, total_price=tot, unit_cost_standard=cost))
    # une offre (devis)
    qid = str(uuid.uuid4())
    db.add(Quote(id=qid, tenant_id=tid, reference="DEV-1", status="draft", date=today))
    db.add(QuoteLine(tenant_id=tid, quote_id=qid, product_id=pid, supplier_id=metro, qty=5, unit_price=Decimal("18")))
    # une recette qui l'utilise
    rid, vid = str(uuid.uuid4()), str(uuid.uuid4())
    db.add(Recipe(id=rid, tenant_id=tid, name="Sauce", current_version_id=vid))
    db.add(RecipeVersion(id=vid, recipe_id=rid, version_number=1))
    db.add(RecipeIngredient(id=str(uuid.uuid4()), recipe_version_id=vid, product_id=pid, ingredient_name="Beurre", qty=2))
    db.commit()

    o = _ov(client, pid)
    assert o["annual_amount"] == 385.0
    assert {s["supplier_name"] for s in o["top_suppliers"]} == {"METRO", "TRANSGOURMET"}
    assert o["offers"]["supplier_count"] == 1 and o["offers"]["best_price"] == 18.0
    assert o["recipe_count"] == 1
    assert "savings" in o and o["savings"]["labels"]["realized"] == "Économisé"


def test_unknown_product_404(client_ctx):
    client, _ = client_ctx
    assert client.get(f"/api/v1/products/{uuid.uuid4()}/overview").status_code == 404
