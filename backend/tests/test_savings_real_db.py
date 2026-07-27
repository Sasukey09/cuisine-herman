"""Moteur d'économies contre un vrai Postgres, via GET /suppliers/{id}/overview.

Ce qui se vérifie ici et nulle part ailleurs : la résolution réelle des offres
concurrentes depuis les devis, la borne de validité (une offre postérieure à la
commande ne compte pas), et l'exclusion des commandes saisies à la main.
"""
import uuid
from datetime import date, datetime, timedelta

import pytest

from app.models.models import (
    Organization,
    Product,
    PurchaseOrder,
    PurchaseOrderLine,
    Quote,
    QuoteLine,
    Supplier,
    SupplierProduct,
)


@pytest.fixture()
def client_ctx(db):
    from fastapi.testclient import TestClient

    from app.api.deps import get_current_tenant_id
    from app.db.session import get_db
    from app.main import app

    tid = str(uuid.uuid4())
    metro, transg, pid = (str(uuid.uuid4()) for _ in range(3))
    db.add(Organization(id=tid, name="Éco"))
    db.commit()
    db.add(Supplier(id=metro, tenant_id=tid, name="METRO"))
    db.add(Supplier(id=transg, tenant_id=tid, name="TRANSGOURMET"))
    db.add(Product(id=pid, tenant_id=tid, name="Farine T55"))
    db.commit()

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_tenant_id] = lambda: tid
    client = TestClient(app)
    yield client, {"tenant_id": tid, "metro": metro, "transg": transg, "product": pid}
    app.dependency_overrides.clear()


def _overview(client, sid):
    r = client.get(f"/api/v1/suppliers/{sid}/overview")
    assert r.status_code == 200, r.text
    return r.json()


def _quote_line(db, tid, sid, pid, price, when, valid_until=None):
    """Une offre : un devis (daté) + sa ligne. Renvoie l'id de la ligne."""
    qid, lid = str(uuid.uuid4()), str(uuid.uuid4())
    db.add(Quote(id=qid, tenant_id=tid, reference=f"DEV-{price}", status="draft",
                 date=when, valid_until=valid_until))
    db.add(QuoteLine(id=lid, tenant_id=tid, quote_id=qid, product_id=pid,
                     supplier_id=sid, qty=5, unit_price=price))
    db.commit()
    return lid


def test_savings_from_a_real_competition(db, client_ctx):
    client, c = client_ctx
    tid, metro, transg, pid = c["tenant_id"], c["metro"], c["transg"], c["product"]
    today = date.today()

    # Deux offres, même produit : METRO 10, TRANSGOURMET 14, valides.
    metro_line = _quote_line(db, tid, metro, pid, 10.0, today - timedelta(days=10),
                             valid_until=today + timedelta(days=30))
    _quote_line(db, tid, transg, pid, 14.0, today - timedelta(days=10),
                valid_until=today + timedelta(days=30))

    # On a commandé chez METRO (le moins cher), 5 unités à 10, depuis SON offre.
    oid = str(uuid.uuid4())
    db.add(PurchaseOrder(id=oid, tenant_id=tid, reference="CMD-1", supplier_id=metro,
                         status="received", ordered_at=datetime.now()))
    db.add(PurchaseOrderLine(tenant_id=tid, order_id=oid, product_id=pid,
                             qty_ordered=5, unit_price=10.0,
                             source_quote_line_id=metro_line))
    db.commit()

    s = _overview(client, metro)["savings"]
    assert s["compared_lines"] == 1
    assert s["realized"] == 20.0   # (14 - 10) * 5
    assert s["missed"] == 0.0
    assert s["possible"] == 20.0
    assert s["best_choice_rate"] == 1.0
    assert s["labels"]["realized"] == "Économisé"


def test_a_later_quote_does_not_rewrite_the_past(db, client_ctx):
    client, c = client_ctx
    tid, metro, transg, pid = c["tenant_id"], c["metro"], c["transg"], c["product"]
    today = date.today()

    metro_line = _quote_line(db, tid, metro, pid, 10.0, today - timedelta(days=10))
    _quote_line(db, tid, transg, pid, 14.0, today - timedelta(days=10))
    # Une offre FUTURE, arrivée après la commande : ne doit pas gonfler l'économie.
    _quote_line(db, tid, transg, pid, 30.0, today + timedelta(days=5))

    oid = str(uuid.uuid4())
    db.add(PurchaseOrder(id=oid, tenant_id=tid, reference="CMD-2", supplier_id=metro,
                         status="received", ordered_at=datetime.now()))
    db.add(PurchaseOrderLine(tenant_id=tid, order_id=oid, product_id=pid,
                             qty_ordered=5, unit_price=10.0,
                             source_quote_line_id=metro_line))
    db.commit()

    s = _overview(client, metro)["savings"]
    assert s["realized"] == 20.0, "l'offre postérieure (30) est ignorée : worst = 14"


def test_an_expired_competing_offer_is_excluded(db, client_ctx):
    client, c = client_ctx
    tid, metro, transg, pid = c["tenant_id"], c["metro"], c["transg"], c["product"]
    today = date.today()

    metro_line = _quote_line(db, tid, metro, pid, 10.0, today - timedelta(days=10),
                             valid_until=today + timedelta(days=30))
    _quote_line(db, tid, transg, pid, 14.0, today - timedelta(days=10),
                valid_until=today + timedelta(days=30))

    # Un 3e fournisseur : offre chère (30) qui existait à la date du devis mais dont
    # la validité expirait AVANT la commande → périmée, donc écartée. Si elle
    # comptait, worst passerait à 30 et realized à 100.
    sysco = str(uuid.uuid4())
    db.add(Supplier(id=sysco, tenant_id=tid, name="SYSCO"))
    db.commit()
    _quote_line(db, tid, sysco, pid, 30.0, today - timedelta(days=20),
                valid_until=today - timedelta(days=5))

    oid = str(uuid.uuid4())
    db.add(PurchaseOrder(id=oid, tenant_id=tid, reference="CMD-EXP", supplier_id=metro,
                         status="received", ordered_at=datetime.now()))
    db.add(PurchaseOrderLine(tenant_id=tid, order_id=oid, product_id=pid,
                             qty_ordered=5, unit_price=10.0,
                             source_quote_line_id=metro_line))
    db.commit()

    s = _overview(client, metro)["savings"]
    assert s["realized"] == 20.0, "l'offre périmée (30) est écartée : worst = 14"


def test_an_unavailable_supplier_offer_is_excluded(db, client_ctx):
    client, c = client_ctx
    tid, metro, transg, pid = c["tenant_id"], c["metro"], c["transg"], c["product"]
    today = date.today()

    metro_line = _quote_line(db, tid, metro, pid, 10.0, today - timedelta(days=10),
                             valid_until=today + timedelta(days=30))
    _quote_line(db, tid, transg, pid, 14.0, today - timedelta(days=10),
                valid_until=today + timedelta(days=30))

    # 3e fournisseur : offre chère (30), valide, mais marqué indisponible au
    # catalogue (supplier_products.available = False) → écartée. Sinon worst = 30.
    sysco = str(uuid.uuid4())
    db.add(Supplier(id=sysco, tenant_id=tid, name="SYSCO"))
    db.commit()
    _quote_line(db, tid, sysco, pid, 30.0, today - timedelta(days=10),
                valid_until=today + timedelta(days=30))
    db.add(SupplierProduct(tenant_id=tid, product_id=pid, supplier_id=sysco,
                           available=False))
    db.commit()

    oid = str(uuid.uuid4())
    db.add(PurchaseOrder(id=oid, tenant_id=tid, reference="CMD-INDISPO", supplier_id=metro,
                         status="received", ordered_at=datetime.now()))
    db.add(PurchaseOrderLine(tenant_id=tid, order_id=oid, product_id=pid,
                             qty_ordered=5, unit_price=10.0,
                             source_quote_line_id=metro_line))
    db.commit()

    s = _overview(client, metro)["savings"]
    assert s["realized"] == 20.0, "le fournisseur indisponible (30) est écarté : worst = 14"


def test_another_tenants_quote_does_not_leak(db, client_ctx):
    client, c = client_ctx
    tid, metro, transg, pid = c["tenant_id"], c["metro"], c["transg"], c["product"]
    today = date.today()

    metro_line = _quote_line(db, tid, metro, pid, 10.0, today - timedelta(days=10),
                             valid_until=today + timedelta(days=30))
    _quote_line(db, tid, transg, pid, 14.0, today - timedelta(days=10),
                valid_until=today + timedelta(days=30))

    # Un devis appartenant à un AUTRE tenant, pour le même product_id. Sa ligne a
    # été (par skew) étiquetée sur notre tenant, donc le filtre QuoteLine.tenant_id
    # seul la laisserait passer : c'est le filtre Quote.tenant_id qui l'écarte.
    # Sinon cette offre à 30 fuirait et ferait grimper worst à 30.
    other = str(uuid.uuid4())
    db.add(Organization(id=other, name="Autre"))
    db.commit()
    qb = str(uuid.uuid4())
    db.add(Quote(id=qb, tenant_id=other, reference="DEV-B", status="draft",
                 date=today - timedelta(days=10),
                 valid_until=today + timedelta(days=30)))
    db.add(QuoteLine(id=str(uuid.uuid4()), tenant_id=tid, quote_id=qb, product_id=pid,
                     supplier_id=transg, qty=5, unit_price=30.0))
    db.commit()

    oid = str(uuid.uuid4())
    db.add(PurchaseOrder(id=oid, tenant_id=tid, reference="CMD-XT", supplier_id=metro,
                         status="received", ordered_at=datetime.now()))
    db.add(PurchaseOrderLine(tenant_id=tid, order_id=oid, product_id=pid,
                             qty_ordered=5, unit_price=10.0,
                             source_quote_line_id=metro_line))
    db.commit()

    s = _overview(client, metro)["savings"]
    assert s["realized"] == 20.0, "le devis de l'autre tenant (30) ne fuit pas : worst = 14"


def test_a_hand_typed_order_contributes_nothing(db, client_ctx):
    client, c = client_ctx
    tid, metro, pid = c["tenant_id"], c["metro"], c["product"]
    # Commande sans source_quote_line_id : pas de comparatif, donc pas d'économie.
    oid = str(uuid.uuid4())
    db.add(PurchaseOrder(id=oid, tenant_id=tid, reference="CMD-3", supplier_id=metro,
                         status="received", ordered_at=datetime.now()))
    db.add(PurchaseOrderLine(tenant_id=tid, order_id=oid, product_id=pid,
                             qty_ordered=5, unit_price=10.0))
    db.commit()

    s = _overview(client, metro)["savings"]
    assert s["compared_lines"] == 0
    assert s["realized"] == 0.0
    assert s["best_choice_rate"] is None
