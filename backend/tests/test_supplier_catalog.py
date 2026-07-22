"""Product↔supplier catalog (supplier_products) + the "Fournisseurs" aggregation.

The price maths (`aggregate_supplier_prices`) and the schema defaults are pure and
run everywhere; the CRUD + endpoint round-trip needs a real Postgres (skips when
DATABASE_URL is absent, like the other *_real_db checks)."""

import uuid
from datetime import date
from types import SimpleNamespace

import pytest

from app.schemas.schemas import SupplierProductCreate, ProductCreate
from app.services.purchasing.purchase_service import aggregate_supplier_prices


# --------------------------------------------------------------------------- #
# Pure aggregation — the numbers behind the Fournisseurs tab.
# --------------------------------------------------------------------------- #
def _purchase(sid, cost, d, unit="kg", cur="EUR"):
    return SimpleNamespace(
        supplier_id=sid,
        unit_cost_standard=cost,
        unit_code=unit,
        currency=cur,
        purchase_date=d,
    )


def test_aggregate_supplier_prices_last_avg_best_and_date():
    rows = [  # oldest -> newest, as product_purchases returns them
        _purchase("A", 8.0, date(2026, 1, 1)),
        _purchase("A", 10.0, date(2026, 2, 1)),
        _purchase("B", 9.0, date(2026, 1, 15)),
    ]
    agg = aggregate_supplier_prices(rows)

    assert agg["A"]["last_cost"] == 10.0  # newest wins
    assert agg["A"]["best_cost"] == 8.0
    assert agg["A"]["avg_cost"] == 9.0
    assert agg["A"]["last_purchase_date"] == "2026-02-01"
    assert agg["B"]["last_cost"] == 9.0
    assert agg["B"]["best_cost"] == 9.0


def test_aggregate_ignores_missing_costs_but_keeps_date():
    rows = [_purchase("A", None, date(2026, 3, 1))]
    agg = aggregate_supplier_prices(rows)
    assert agg["A"]["last_cost"] is None
    assert agg["A"]["best_cost"] is None
    assert agg["A"]["avg_cost"] is None
    assert agg["A"]["last_purchase_date"] == "2026-03-01"


def test_aggregate_empty():
    assert aggregate_supplier_prices([]) == {}


# --------------------------------------------------------------------------- #
# Schemas.
# --------------------------------------------------------------------------- #
def test_supplier_product_create_defaults_available_true():
    s = SupplierProductCreate(supplier_id="sup-1")
    assert s.available is True
    assert s.preferred is False
    assert s.lead_time_days is None


def test_product_vat_rate_is_bounded():
    ProductCreate(name="Beurre", vat_rate=5.5)  # ok
    with pytest.raises(Exception):
        ProductCreate(name="Beurre", vat_rate=200)  # > 100 rejected


# --------------------------------------------------------------------------- #
# CRUD + aggregation against a real Postgres (CI).
# --------------------------------------------------------------------------- #
def test_product_suppliers_merges_catalog_and_prices(db):
    from app.crud import crud_supplier_product
    from app.models.models import (
        Organization,
        Product,
        PurchaseHistory,
        Supplier,
        Unit,
    )
    from app.services.purchasing import purchase_service

    tenant_id = str(uuid.uuid4())
    db.add(Organization(id=tenant_id, name="Cat Test"))
    db.commit()

    sup_a, sup_b = str(uuid.uuid4()), str(uuid.uuid4())
    product_id = str(uuid.uuid4())
    db.add(Supplier(id=sup_a, tenant_id=tenant_id, name="Metro"))
    db.add(Supplier(id=sup_b, tenant_id=tenant_id, name="Transgourmet"))
    db.add(Product(id=product_id, tenant_id=tenant_id, name="Beurre doux"))
    db.commit()

    kg = db.query(Unit).filter(Unit.code == "kg").first()

    # A purchase from supplier A (gives it a price/date); supplier B is catalog-only.
    db.add(
        PurchaseHistory(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            product_id=product_id,
            supplier_id=sup_a,
            purchase_date=date(2026, 2, 1),
            unit_id=kg.id if kg else None,
            unit_code="kg",
            unit_cost_standard=8.5,
            currency="EUR",
        )
    )
    db.commit()

    # Catalog links: B is preferred and available, plus a link for A.
    crud_supplier_product.create_link(
        db, tenant_id, product_id, SupplierProductCreate(supplier_id=sup_a)
    )
    crud_supplier_product.create_link(
        db,
        tenant_id,
        product_id,
        SupplierProductCreate(supplier_id=sup_b, preferred=True, lead_time_days=2),
    )

    result = purchase_service.product_suppliers(db, tenant_id, product_id)
    suppliers = {s["supplier_id"]: s for s in result["suppliers"]}

    assert set(suppliers) == {sup_a, sup_b}
    assert suppliers[sup_a]["last_cost"] == 8.5
    assert suppliers[sup_a]["last_purchase_date"] == "2026-02-01"
    assert suppliers[sup_b]["last_cost"] is None  # catalog-only, no purchase yet
    assert suppliers[sup_b]["preferred"] is True
    assert suppliers[sup_b]["lead_time_days"] == 2
    # A is the only priced supplier -> cheapest.
    assert result["cheapest_supplier_id"] == sup_a
    assert suppliers[sup_a]["is_cheapest"] is True
    # Preferred supplier sorts first.
    assert result["suppliers"][0]["supplier_id"] == sup_b

    # create_link is idempotent on the (product, supplier) pair.
    again = crud_supplier_product.create_link(
        db, tenant_id, product_id, SupplierProductCreate(supplier_id=sup_a, available=False)
    )
    links = crud_supplier_product.list_links(db, tenant_id, product_id)
    assert len([link for link in links if str(link.supplier_id) == sup_a]) == 1
    assert again.available is False
