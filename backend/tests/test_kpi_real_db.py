"""Pilotage Achats contre un vrai Postgres, via GET /purchasing/kpi.
Skip en local sans DATABASE_URL, tourne en CI."""
import uuid
from datetime import date, datetime, timedelta

import pytest

from app.models.models import (
    Organization, Product, Supplier, PurchaseOrder, PurchaseOrderLine,
    Invoice, Quote, QuoteLine,
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
    db.add(Organization(id=tid, name="Pilotage"))
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


def test_kpi_assembles_cycle_and_savings(db, client_ctx):
    client, c = client_ctx
    tid, metro, transg, pid = c["tenant_id"], c["metro"], c["transg"], c["product"]
    today = date.today()

    # Une facture (facturé) et une commande (commandé).
    db.add(Invoice(tenant_id=tid, supplier_id=metro, invoice_number="F1",
                   total_amount=650, date=today))
    db.add(PurchaseOrder(tenant_id=tid, reference="CMD-K", supplier_id=metro,
                         status="received", total_amount=1000, ordered_at=datetime.now()))
    db.commit()

    r = client.get("/api/v1/purchasing/kpi")
    assert r.status_code == 200, r.text
    k = r.json()
    assert k["window_months"] == 12
    assert k["cycle"]["ordered_total"] == 1000.0
    assert k["cycle"]["billed_total"] == 650.0
    # écart dérivé (reçu = 0 ici, pas de réception validée)
    assert k["cycle"]["gap_ordered_received"] == 1000.0
    # blocs présents (passe-plat)
    assert set(k["price"].keys()) >= {"n_hausse", "n_baisse", "n_critiques", "switch_savings_total"}
    assert "labels" in k and "most_competitive" in k["suppliers"]
    assert k["savings"]["labels"]["realized"] == "Économisé"
