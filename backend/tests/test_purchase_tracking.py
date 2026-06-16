"""Purchase & price tracking tests.

No DB / network: crud_purchase + name/unit helpers are monkeypatched and the DB
is faked, so we cover every documented case: hausse, baisse, changement de
fournisseur, comparaison multi-fournisseurs, recalcul recette (alerte marge).
"""
from types import SimpleNamespace as N

from app.services.purchasing import purchase_service as svc


def _line(**kw):
    base = dict(id="l1", product_id="p1", unit_id=1, unit_price=2.4, qty=5, line_total=12.0)
    base.update(kw)
    return N(**base)


def _invoice(**kw):
    base = dict(id="i1", supplier_id="metro", invoice_number="F-1", date=None, currency="EUR")
    base.update(kw)
    return N(**base)


def _patch_record(monkeypatch, prev_std):
    created = {}
    alerts = []
    monkeypatch.setattr(svc, "_unit_info", lambda db, uid: ("kg", 1.0))
    monkeypatch.setattr(svc, "_name", lambda db, m, i: {"p1": "Tomate", "metro": "Metro"}.get(str(i)))
    monkeypatch.setattr(svc.crud_purchase, "delete_for_line", lambda db, t, lid: 0)
    prev = N(unit_cost_standard=prev_std) if prev_std is not None else None
    monkeypatch.setattr(svc.crud_purchase, "last_purchase", lambda *a, **k: prev)
    monkeypatch.setattr(svc.crud_purchase, "create_purchase", lambda db, **f: created.update(f) or N(id="ph1", **f))
    monkeypatch.setattr(svc.crud_purchase, "create_alert", lambda db, **f: alerts.append(f) or N(id="al1"))
    return created, alerts


def test_price_increase_raises_alert(monkeypatch):
    created, alerts = _patch_record(monkeypatch, prev_std=2.0)
    out = svc.record_purchase(object(), "t1", _line(unit_price=2.4), _invoice())
    assert out["variation_pct"] == 20.0
    assert created["unit_cost_standard"] == 2.4
    assert created["variation_pct"] == 20.0
    assert len(alerts) == 1 and alerts[0]["type"] == "price_increase"
    assert alerts[0]["change_pct"] == 20.0


def test_price_decrease_raises_alert(monkeypatch):
    created, alerts = _patch_record(monkeypatch, prev_std=3.0)
    out = svc.record_purchase(object(), "t1", _line(unit_price=2.4), _invoice())
    assert out["variation_pct"] == -20.0
    assert len(alerts) == 1 and alerts[0]["type"] == "price_decrease"


def test_small_change_no_alert(monkeypatch):
    created, alerts = _patch_record(monkeypatch, prev_std=2.39)  # +0.4% < 5%
    svc.record_purchase(object(), "t1", _line(unit_price=2.4), _invoice())
    assert alerts == []


def test_supplier_change_has_no_baseline(monkeypatch):
    # First purchase from a new supplier -> last_purchase(None) -> no variation/alert.
    created, alerts = _patch_record(monkeypatch, prev_std=None)
    out = svc.record_purchase(object(), "t1", _line(unit_price=2.4), _invoice(supplier_id="pomona"))
    assert out["variation_pct"] is None
    assert created["variation_pct"] is None
    assert alerts == []


def test_standardized_cost_uses_unit_ratio(monkeypatch):
    # price 0.002 €/g, ratio_to_base(g)=0.001 -> 2.0 €/kg standardized.
    created, _ = _patch_record(monkeypatch, prev_std=None)
    monkeypatch.setattr(svc, "_unit_info", lambda db, uid: ("g", 0.001))
    svc.record_purchase(object(), "t1", _line(unit_price=0.002, unit_id=2), _invoice())
    assert round(created["unit_cost_standard"], 3) == 2.0


def test_supplier_comparison_flags_cheapest(monkeypatch):
    monkeypatch.setattr(svc, "_supplier_names", lambda db, t: {"metro": "Metro", "pomona": "Pomona", "tg": "Transgourmet"})
    purchases = [  # ascending (last per supplier wins; here one each)
        N(id="a", supplier_id="metro", unit_cost_standard=2.88, unit_code="kg", currency="EUR", purchase_date=None),
        N(id="b", supplier_id="pomona", unit_cost_standard=2.40, unit_code="kg", currency="EUR", purchase_date=None),
        N(id="c", supplier_id="tg", unit_cost_standard=2.55, unit_code="kg", currency="EUR", purchase_date=None),
    ]
    monkeypatch.setattr(svc.crud_purchase, "product_purchases", lambda db, t, pid: purchases)
    out = svc.supplier_comparison(object(), "t1", "p1")
    assert out["cheapest_supplier_id"] == "pomona"
    cheapest = [s for s in out["suppliers"] if s["is_cheapest"]]
    assert len(cheapest) == 1 and cheapest[0]["supplier_name"] == "Pomona"
    # sorted ascending by standardized cost
    assert [s["supplier_name"] for s in sorted(out["suppliers"], key=lambda x: x["unit_cost_standard"])][0] == "Pomona"


def test_price_dashboard_most_increased(monkeypatch):
    monkeypatch.setattr(svc, "_product_names", lambda db, t: {"p1": "Tomate"})
    monkeypatch.setattr(svc, "_supplier_names", lambda db, t: {"metro": "Metro", "pomona": "Pomona"})
    purchases = [  # descending (most recent first)
        N(id="n", product_id="p1", supplier_id="metro", unit_cost_standard=2.88, unit_code="kg", purchase_date=None),
        N(id="o", product_id="p1", supplier_id="pomona", unit_cost_standard=2.40, unit_code="kg", purchase_date=None),
    ]
    monkeypatch.setattr(svc.crud_purchase, "all_purchases", lambda db, t: purchases)
    monkeypatch.setattr(svc.crud_purchase, "list_alerts", lambda db, t, **k: [])
    out = svc.price_dashboard(object(), "t1")
    assert out["most_increased"] and out["most_increased"][0]["product_name"] == "Tomate"
    assert out["most_increased"][0]["change_pct"] == 20.0
    # two suppliers -> a savings opportunity (2.88 vs 2.40)
    assert out["savings_opportunities"]
    assert out["savings_opportunities"][0]["cheapest_supplier"] == "Pomona"


# --------------------------------------------------------------------------- #
# margin alert after recipe recompute
# --------------------------------------------------------------------------- #
class FakeQuery:
    def __init__(self, store):
        self.store = store

    def join(self, *a, **k):
        return self

    def filter(self, *a, **k):
        return self

    def order_by(self, *a, **k):
        return self

    def distinct(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def all(self):
        return self.store.pop(0) if self.store else []


class FakeDB:
    def __init__(self, results):
        self.results = list(results)

    def query(self, *a, **k):
        return FakeQuery(self.results)

    def commit(self):
        pass

    def rollback(self):
        pass


def test_margin_alert_on_cost_rise(monkeypatch):
    alerts = []
    monkeypatch.setattr(svc.crud_purchase, "create_alert", lambda db, **f: alerts.append(f) or N(id="m1"))
    # 1st query -> versions; 2nd query -> two snapshots (new then old)
    results = [
        [("v1", "r1", "Pizza Margherita")],
        [N(cost_per_portion=1.30), N(cost_per_portion=1.00)],  # +30%
    ]
    raised = svc.detect_margin_alerts(FakeDB(results), "t1", "p1")
    assert len(raised) == 1
    assert alerts[0]["type"] == "margin"
    assert alerts[0]["recipe_id"] == "r1"
    assert alerts[0]["change_pct"] == 30.0


def test_no_margin_alert_when_cost_stable(monkeypatch):
    alerts = []
    monkeypatch.setattr(svc.crud_purchase, "create_alert", lambda db, **f: alerts.append(f) or N(id="m1"))
    results = [
        [("v1", "r1", "Pizza")],
        [N(cost_per_portion=1.01), N(cost_per_portion=1.00)],  # +1% < 5%
    ]
    raised = svc.detect_margin_alerts(FakeDB(results), "t1", "p1")
    assert raised == []
    assert alerts == []
