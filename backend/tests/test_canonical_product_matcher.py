import time
from types import SimpleNamespace

from app.services.matching.product_matcher import match_product

# db=None -> matcher skips persistence, so we only stub the read functions.
READ_PRODUCTS = "app.crud.crud_match.get_products_for_tenant"
READ_ALIASES = "app.crud.crud_match.get_aliases_for_tenant"


def make_product(pid, name=None, sku=None):
    return SimpleNamespace(id=pid, name=name, sku=sku)


def make_alias(product_id, alias):
    return SimpleNamespace(product_id=product_id, alias=alias)


def test_exact_sku_match(monkeypatch):
    monkeypatch.setattr(READ_PRODUCTS, lambda db, t: [make_product("p1", name="", sku="TOM123")])
    monkeypatch.setattr(READ_ALIASES, lambda db, t: [])
    res = match_product(None, "t1", "TOM123")
    assert res["confidence_score"] == 100.0
    assert res["match_type"] == "exact_sku"
    assert res["manual_review"] is False


def test_exact_name_match(monkeypatch):
    monkeypatch.setattr(READ_PRODUCTS, lambda db, t: [make_product("p1", name="Tomate ronde 5kg")])
    monkeypatch.setattr(READ_ALIASES, lambda db, t: [])
    res = match_product(None, "t1", "Tomate ronde 5kg")
    assert res["confidence_score"] == 100.0
    assert res["match_type"] == "exact_name"


def test_alias_match(monkeypatch):
    monkeypatch.setattr(READ_PRODUCTS, lambda db, t: [make_product("p1", name="Tomate ronde")])
    monkeypatch.setattr(READ_ALIASES, lambda db, t: [make_alias("p1", "Tomate ronde")])
    res = match_product(None, "t1", "TOMATE RONDE")
    assert res["confidence_score"] == 95.0
    assert res["match_type"] == "alias"


def test_fuzzy_match(monkeypatch):
    monkeypatch.setattr(READ_PRODUCTS, lambda db, t: [make_product("p1", name="Tomate ronde 5kg")])
    monkeypatch.setattr(READ_ALIASES, lambda db, t: [])
    res = match_product(None, "t1", "Tomatte ronde 5kg")
    assert res["match_type"] == "fuzzy_name"
    assert res["confidence_score"] > 80.0


def test_no_match(monkeypatch):
    monkeypatch.setattr(READ_PRODUCTS, lambda db, t: [make_product("p1", name="Tomate ronde")])
    monkeypatch.setattr(READ_ALIASES, lambda db, t: [])
    res = match_product(None, "t1", "Produit Inconnu XYZ")
    assert res["product_id"] is None
    assert res["manual_review"] is True


def test_multi_tenant_isolation(monkeypatch):
    def gp(db, tenant_id):
        return [make_product("p1", name="Tomate A")] if tenant_id == "t1" else [make_product("p2", name="Tomate B")]

    monkeypatch.setattr(READ_PRODUCTS, gp)
    monkeypatch.setattr(READ_ALIASES, lambda db, t: [])
    assert match_product(None, "t1", "Tomate A")["product_id"] == "p1"
    assert match_product(None, "t2", "Tomate A")["product_id"] != "p1"


def test_performance_10000_products(monkeypatch):
    n = 10_000
    products = [make_product(str(i), name=f"Product {i}") for i in range(n)]
    monkeypatch.setattr(READ_PRODUCTS, lambda db, t: products)
    monkeypatch.setattr(READ_ALIASES, lambda db, t: [])
    start = time.perf_counter()
    res = match_product(None, "tperf", f"Product {n-1}")
    elapsed = time.perf_counter() - start
    assert res["product_id"] is not None
    assert elapsed < 0.5, f"Matching took too long: {elapsed}s"
