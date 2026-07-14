from types import SimpleNamespace as N

from app.services.invoicing import invoice_pricing


class FakeQuery:
    def __init__(self, result):
        self._result = result

    def filter(self, *a, **k):
        return self

    def join(self, *a, **k):
        return self

    def delete(self, *a, **k):
        return 0

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


# --------------------------------------------------------------------------- #
# B2 — invoice ingestion must always resolve supplier_id. Before, persist_extraction
# set number/date/total but never the supplier, so every derived price/purchase row
# was orphaned (supplier_id=NULL) and supplier comparison collapsed.
# --------------------------------------------------------------------------- #
def _extraction(supplier):
    return N(
        supplier=supplier,
        invoice_number="F-2026-001",
        date=None,
        total_amount=42.0,
        lines=[],
    )


def _patch_persist(monkeypatch, resolved_supplier, calls):
    monkeypatch.setattr(invoice_pricing.crud_price, "get_units_by_code", lambda db: {})
    monkeypatch.setattr(
        invoice_pricing.crud_invoice_line, "create_invoice_line",
        lambda *a, **k: N(id="line"),
    )

    def fake_get_or_create(db, tenant_id, name):
        calls.append(name)
        return resolved_supplier

    monkeypatch.setattr(
        invoice_pricing.crud_supplier, "get_or_create_supplier_by_name", fake_get_or_create
    )


def test_ingestion_resolves_and_sets_supplier_id(monkeypatch):
    invoice = N(id="inv1", tenant_id="t1", supplier_id=None,
                invoice_number=None, date=None, total_amount=None,
                ocr_status=None, parsed=False)
    calls = []
    _patch_persist(monkeypatch, N(id="sup-metro", name="Metro"), calls)

    invoice_pricing.persist_extraction(FakeDB(invoice), "t1", "inv1", _extraction("Metro"))

    assert invoice.supplier_id == "sup-metro"   # always set, never NULL
    assert calls == ["Metro"]


def test_ingestion_does_not_overwrite_an_existing_supplier(monkeypatch):
    invoice = N(id="inv1", tenant_id="t1", supplier_id="already-set",
                invoice_number=None, date=None, total_amount=None,
                ocr_status=None, parsed=False)
    calls = []
    _patch_persist(monkeypatch, N(id="sup-metro", name="Metro"), calls)

    invoice_pricing.persist_extraction(FakeDB(invoice), "t1", "inv1", _extraction("Metro"))

    assert invoice.supplier_id == "already-set"  # a supplier chosen at upload wins
    assert calls == []                           # resolution not even attempted


def test_ingestion_with_no_extracted_supplier_leaves_id_none(monkeypatch):
    invoice = N(id="inv1", tenant_id="t1", supplier_id=None,
                invoice_number=None, date=None, total_amount=None,
                ocr_status=None, parsed=False)
    calls = []
    _patch_persist(monkeypatch, None, calls)

    invoice_pricing.persist_extraction(FakeDB(invoice), "t1", "inv1", _extraction(None))

    assert invoice.supplier_id is None   # nothing to resolve; never fabricated
    assert calls == []


# --------------------------------------------------------------------------- #
# B5 — re-processing an invoice must be idempotent: every price creation is
# preceded by a delete of that line's prior price rows, so replaying /process
# never stacks a second ProductPrice. Purchase history already deletes-then-inserts.
# --------------------------------------------------------------------------- #
def test_reprocessing_is_idempotent_deletes_before_each_price(monkeypatch):
    invoice = N(id="inv1", tenant_id="t1", supplier_id=None, currency="EUR", date=None)
    lines = [N(id="l1", invoice_id="inv1", product_id="p1",
               description="Tomates", unit_price=2.0, unit_id=1)]

    ops = []  # ordered log of (action, line_id)
    monkeypatch.setattr(invoice_pricing.crud_invoice_line, "list_lines", lambda db, iid: lines)
    monkeypatch.setattr(
        invoice_pricing.crud_price, "delete_prices_for_line",
        lambda db, t, lid: ops.append(("delete", lid)),
    )
    monkeypatch.setattr(
        invoice_pricing.crud_price, "create_price",
        lambda db, tenant_id, product_id, price, **k: ops.append(("create", k["source_invoice_line_id"])) or N(id="pr"),
    )
    monkeypatch.setattr(invoice_pricing.cost_engine, "recompute_for_product", lambda *a, **k: [])
    from app.services.purchasing import purchase_service
    monkeypatch.setattr(purchase_service, "record_purchase", lambda *a, **k: {})
    monkeypatch.setattr(purchase_service, "detect_margin_alerts", lambda *a, **k: None)

    # Run the pipeline twice, as a user clicking "retraiter" would.
    invoice_pricing.process_invoice(FakeDB(invoice), "t1", "inv1", auto_match=False)
    invoice_pricing.process_invoice(FakeDB(invoice), "t1", "inv1", auto_match=False)

    # Each of the two runs: delete THEN create for l1. Never two creates in a row.
    assert ops == [
        ("delete", "l1"), ("create", "l1"),
        ("delete", "l1"), ("create", "l1"),
    ]


# --------------------------------------------------------------------------- #
# I3 — a below-threshold (ambiguous) fuzzy match must NOT be auto-bound or priced.
# --------------------------------------------------------------------------- #
def test_ambiguous_match_is_not_bound_or_priced(monkeypatch):
    invoice = N(id="inv1", tenant_id="t1", supplier_id=None, currency="EUR", date=None)
    line = N(id="l1", invoice_id="inv1", product_id=None,
             description="Filet de boeuf", unit_price=20.0, unit_id=1, match_confidence=None)

    monkeypatch.setattr(invoice_pricing.crud_invoice_line, "list_lines", lambda db, iid: [line])
    # 68 % onto "Filet de poulet": a real product id comes back, but manual_review.
    monkeypatch.setattr(
        invoice_pricing, "match_product",
        lambda db, t, text: {"product_id": "p_poulet", "confidence_score": 68.0,
                             "manual_review": True},
    )
    created = []
    monkeypatch.setattr(
        invoice_pricing.crud_price, "create_price",
        lambda *a, **k: created.append(k.get("product_id")) or N(id="pr"),
    )
    monkeypatch.setattr(invoice_pricing.crud_price, "delete_prices_for_line", lambda *a, **k: 0)
    monkeypatch.setattr(invoice_pricing.cost_engine, "recompute_for_product", lambda *a, **k: [])

    summary = invoice_pricing.process_invoice(FakeDB(invoice), "t1", "inv1")

    assert line.product_id is None            # never bound on an ambiguous match
    assert created == []                      # never priced
    assert summary["prices_created"] == 0
    assert summary["matched"] == 0
    assert summary["needs_review"] == ["l1"]  # sent to a human instead
