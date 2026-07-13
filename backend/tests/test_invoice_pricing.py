from types import SimpleNamespace as N

from app.services.invoicing import invoice_pricing


class FakeQuery:
    def __init__(self, result):
        self._result = result

    def filter(self, *a, **k):
        return self

    def join(self, *a, **k):
        return self

    def first(self):
        return self._result


class FakeDB:
    """Minimal stand-in: the only real query in process_invoice fetches the invoice."""

    def __init__(self, invoice):
        self._invoice = invoice

    def query(self, *models):
        return FakeQuery(self._invoice)

    def add(self, *a):
        pass

    def commit(self):
        pass

    def refresh(self, *a):
        pass


def test_process_invoice_orchestration(monkeypatch):
    invoice = N(id="inv1", tenant_id="t1", supplier_id=None, currency="EUR", date=None)
    lines = [
        N(id="l1", invoice_id="inv1", product_id=None, description="Tomates", unit_price=2.0, unit_id=1),
        N(id="l2", invoice_id="inv1", product_id=None, description="Inconnu", unit_price=5.0, unit_id=1),
        N(id="l3", invoice_id="inv1", product_id="p3", description="Sel", unit_price=None, unit_id=1),
    ]

    matches = {
        "Tomates": {"product_id": "p1", "confidence_score": 95.0, "manual_review": False},
        "Inconnu": {"product_id": None, "confidence_score": 0.0, "manual_review": True},
    }

    created_prices = []
    recomputed = []

    monkeypatch.setattr(invoice_pricing.crud_invoice_line, "list_lines", lambda db, iid: lines)
    monkeypatch.setattr(invoice_pricing, "match_product", lambda db, t, text: matches[text])

    def fake_create_price(db, tenant_id, product_id, price, **k):
        created_prices.append(product_id)
        return N(id=f"price-{product_id}")

    monkeypatch.setattr(invoice_pricing.crud_price, "create_price", fake_create_price)
    # recompute_for_product now REQUIRES the tenant: it used to recompute the
    # recipes of every tenant referencing the product.
    monkeypatch.setattr(
        invoice_pricing.cost_engine, "recompute_for_product",
        lambda db, pid, tenant_id: recomputed.append((pid, tenant_id)) or [],
    )

    summary = invoice_pricing.process_invoice(FakeDB(invoice), "t1", "inv1")

    assert summary["lines"] == 3
    assert summary["matched"] == 1                  # only "Tomates" matched
    assert summary["prices_created"] == 1           # l1 priced; l2 no product; l3 no unit_price
    assert summary["needs_review"] == ["l2"]
    assert created_prices == ["p1"]
    # recompute triggered for the priced product, scoped to the caller's tenant
    assert recomputed == [("p1", "t1")]
