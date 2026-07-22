"""Pure comparator core (`quote_service.compare_basket`).

The basket maths — per-supplier totals, coverage, lead time, cheapest /
best-coverage ranking — is pure and runs everywhere. The CRUD + endpoint
round-trip lives in ``test_quotes.py`` and needs a real Postgres (CI)."""

from app.services.quotes.quote_service import compare_basket


NAMES = {"A": "Metro", "B": "Transgourmet", "C": "Pomona"}


def _line(pid, name, qty, ratio=1.0):
    return {"product_id": pid, "product_name": name, "qty": qty, "unit_ratio": ratio}


def test_cheapest_full_coverage_supplier_wins():
    lines = [_line("p1", "Farine", 10), _line("p2", "Beurre", 2)]
    prices = {"p1": {"A": 1.0, "B": 1.2}, "p2": {"A": 8.0, "B": 6.5}}
    res = compare_basket(lines, prices, {}, NAMES)

    by = {s["supplier_id"]: s for s in res["suppliers"]}
    assert by["A"]["total"] == 26.0  # 10*1 + 2*8
    assert by["B"]["total"] == 25.0  # 10*1.2 + 2*6.5
    assert by["A"]["is_full_coverage"] and by["B"]["is_full_coverage"]
    # B is cheaper -> cheapest, and sorts first.
    assert res["cheapest_supplier_id"] == "B"
    assert res["suppliers"][0]["supplier_id"] == "B"
    assert by["B"]["is_cheapest"] and not by["A"]["is_cheapest"]


def test_full_coverage_ranks_above_a_cheaper_partial_supplier():
    lines = [_line("p1", "Farine", 10), _line("p2", "Beurre", 2)]
    # A covers both (26). C only prices p1, cheaply (total 5) but misses p2.
    prices = {"p1": {"A": 1.0, "C": 0.5}, "p2": {"A": 8.0}}
    res = compare_basket(lines, prices, {}, NAMES)

    by = {s["supplier_id"]: s for s in res["suppliers"]}
    assert by["A"]["is_full_coverage"] is True
    assert by["C"]["is_full_coverage"] is False
    assert by["C"]["covered_count"] == 1
    assert by["C"]["missing"] == [{"product_id": "p2", "product_name": "Beurre"}]
    # Despite C's lower total, the cheapest is chosen among FULL-coverage suppliers.
    assert res["cheapest_supplier_id"] == "A"
    assert res["suppliers"][0]["supplier_id"] == "A"  # full coverage sorts first
    assert res["best_coverage_supplier_id"] == "A"


def test_qty_is_standardized_by_unit_ratio_and_lead_time_preferred_flow():
    # qty 3 in a unit worth 2 base units -> 6 base units * 1.5 = 9.0
    lines = [_line("p1", "Huile", 3, ratio=2.0)]
    prices = {"p1": {"A": 1.5}}
    catalog = {"p1": {"A": {"available": True, "preferred": True, "lead_time_days": 5}}}
    res = compare_basket(lines, prices, catalog, NAMES)

    a = res["suppliers"][0]
    assert a["supplier_id"] == "A"
    assert a["total"] == 9.0
    assert a["lines"][0]["line_cost"] == 9.0
    assert a["lines"][0]["unit_cost"] == 1.5
    assert a["max_lead_time_days"] == 5
    assert a["preferred"] is True
    assert a["is_full_coverage"] is True


def test_max_lead_time_is_the_slowest_covered_line():
    lines = [_line("p1", "A", 1), _line("p2", "B", 1)]
    prices = {"p1": {"A": 1.0}, "p2": {"A": 1.0}}
    catalog = {
        "p1": {"A": {"lead_time_days": 2}},
        "p2": {"A": {"lead_time_days": 7}},
    }
    res = compare_basket(lines, prices, catalog, NAMES)
    assert res["suppliers"][0]["max_lead_time_days"] == 7


def test_partial_supplier_total_sums_only_covered_lines():
    lines = [_line("p1", "A", 10), _line("p2", "B", 3)]
    prices = {"p1": {"A": 2.0}}  # A can't price p2
    res = compare_basket(lines, prices, {}, NAMES)
    a = res["suppliers"][0]
    assert a["total"] == 20.0  # only p1
    assert a["covered_count"] == 1
    assert a["is_full_coverage"] is False


def test_basket_with_no_priceable_line_yields_no_suppliers():
    lines = [{"product_id": None, "description": "Note libre", "qty": 1}]
    res = compare_basket(lines, {}, {}, NAMES)
    assert res["priceable_count"] == 0
    assert res["suppliers"] == []
    assert res["cheapest_supplier_id"] is None
    assert res["best_coverage_supplier_id"] is None


def test_missing_qty_still_counts_as_covered_without_cost():
    lines = [{"product_id": "p1", "product_name": "X", "qty": None, "unit_ratio": 1.0}]
    prices = {"p1": {"A": 3.0}}
    res = compare_basket(lines, prices, {}, NAMES)
    a = res["suppliers"][0]
    assert a["covered_count"] == 1
    assert a["is_full_coverage"] is True
    assert a["total"] == 0.0  # priced but qty unknown -> no line cost added
    assert a["lines"][0]["line_cost"] is None
