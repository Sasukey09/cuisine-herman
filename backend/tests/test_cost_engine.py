from types import SimpleNamespace

from app.services.costing.cost_engine import compute_cost_breakdown

# unit_id -> ratio_to_base : 1 = kg (base mass), 2 = g
UNITS = {1: 1.0, 2: 0.001}


def ing(product_id, qty=None, unit_id=None, qty_normalized=None, loss_pct=0, yield_pct=100):
    return SimpleNamespace(
        product_id=product_id,
        qty=qty,
        unit_id=unit_id,
        qty_normalized=qty_normalized,
        loss_pct=loss_pct,
        yield_pct=yield_pct,
    )


def price(pid, value, unit_id=1):
    return SimpleNamespace(id=f"price-{pid}", price=value, unit_id=unit_id)


def lookup_from(prices):
    return lambda product_id: prices.get(product_id)


def test_simple_cost_and_food_cost():
    prices = {"p1": price("p1", 5.0, unit_id=1)}  # 5 / kg
    res = compute_cost_breakdown(
        [ing("p1", qty_normalized=2.0)], lookup_from(prices), UNITS,
        yield_qty=4, selling_price=10.0,
    )
    assert res["computed_cost_total"] == 10.0       # 2kg * 5
    assert res["cost_per_portion"] == 2.5           # 10 / 4 portions
    assert res["food_cost_pct"] == 25.0             # 2.5 / 10
    assert res["margin_estimated"] == 7.5           # 10 - 2.5
    assert res["has_missing_prices"] is False
    assert res["_price_ids"] == ["price-p1"]


def test_loss_and_yield_applied():
    prices = {"p1": price("p1", 10.0, unit_id=1)}
    res = compute_cost_breakdown(
        [ing("p1", qty_normalized=1.0, loss_pct=10, yield_pct=90)],
        lookup_from(prices), UNITS, yield_qty=1,
    )
    # 1 * 10 * 1.1 / 0.9 = 12.2222
    assert round(res["computed_cost_total"], 2) == 12.22


def test_unit_conversion_g_to_kg():
    prices = {"p1": price("p1", 8.0, unit_id=1)}  # 8 / kg
    # 500 g, no normalized qty -> qty_base = 500 * 0.001 = 0.5 kg
    res = compute_cost_breakdown(
        [ing("p1", qty=500, unit_id=2)], lookup_from(prices), UNITS, yield_qty=1,
    )
    assert res["computed_cost_total"] == 4.0


def test_missing_price_flagged():
    res = compute_cost_breakdown(
        [ing("p_unknown", qty_normalized=3.0)], lookup_from({}), UNITS, yield_qty=1,
    )
    assert res["has_missing_prices"] is True
    assert res["computed_cost_total"] == 0.0
    assert res["breakdown"][0]["missing_price"] is True
    assert res["breakdown"][0]["line_cost"] is None


def test_no_selling_price_no_food_cost():
    prices = {"p1": price("p1", 5.0)}
    res = compute_cost_breakdown(
        [ing("p1", qty_normalized=2.0)], lookup_from(prices), UNITS, yield_qty=4,
    )
    assert res["food_cost_pct"] is None
    assert res["margin_estimated"] is None


def test_multiple_ingredients_sum():
    prices = {"p1": price("p1", 5.0), "p2": price("p2", 2.0)}
    res = compute_cost_breakdown(
        [ing("p1", qty_normalized=2.0), ing("p2", qty_normalized=3.0)],
        lookup_from(prices), UNITS, yield_qty=1,
    )
    assert res["computed_cost_total"] == 16.0  # 10 + 6
    assert len(res["_price_ids"]) == 2


# --------------------------------------------------------------------------- #
# B1 — dimensional safety: the engine must NEVER combine a quantity with a price
# expressed in a different unit category. unit_id -> category:
#   1 = mass (kg), 2 = mass (g), 3 = volume (L), 4 = count (pièce)
# --------------------------------------------------------------------------- #
CATEGORIES = {1: "mass", 2: "mass", 3: "volume", 4: "count"}


def test_incompatible_units_grams_vs_litres_are_refused_not_computed():
    # ingredient recorded in grams (mass), price expressed per litre (volume).
    prices = {"p1": price("p1", 2.0, unit_id=3)}  # 2 € / L
    res = compute_cost_breakdown(
        [ing("p1", qty=200, unit_id=2)],  # 200 g
        lookup_from(prices), UNITS, yield_qty=1, unit_categories=CATEGORIES,
    )
    line = res["breakdown"][0]
    assert line["incompatible_units"] is True
    assert line["line_cost"] is None                 # never a silent number
    assert res["has_incompatible_units"] is True
    assert res["computed_cost_total"] == 0.0         # refused line excluded
    assert res["_incompatible_units"] == ["p1"]
    assert "mass" in line["incompatible_reason"] and "volume" in line["incompatible_reason"]


def test_same_category_still_computes_with_categories_supplied():
    # 500 g of a product priced 8 € / kg — same category, must compute normally.
    prices = {"p1": price("p1", 8.0, unit_id=1)}
    res = compute_cost_breakdown(
        [ing("p1", qty=500, unit_id=2)],
        lookup_from(prices), UNITS, yield_qty=1, unit_categories=CATEGORIES,
    )
    assert res["computed_cost_total"] == 4.0
    assert res["has_incompatible_units"] is False


def test_unknown_unit_id_is_refused():
    prices = {"p1": price("p1", 5.0, unit_id=1)}
    res = compute_cost_breakdown(
        [ing("p1", qty=1, unit_id=999)],  # 999 not in reference data
        lookup_from(prices), UNITS, yield_qty=1, unit_categories=CATEGORIES,
    )
    assert res["breakdown"][0]["incompatible_units"] is True
    assert res["has_incompatible_units"] is True
    assert res["computed_cost_total"] == 0.0


def test_null_unit_id_stays_permissive():
    # A null unit id means "no unit / already base" (legacy data) — not refused.
    prices = {"p1": price("p1", 5.0, unit_id=None)}
    res = compute_cost_breakdown(
        [ing("p1", qty_normalized=2.0, unit_id=None)],
        lookup_from(prices), UNITS, yield_qty=1, unit_categories=CATEGORIES,
    )
    assert res["has_incompatible_units"] is False
    assert res["computed_cost_total"] == 10.0


def test_mixed_lines_only_good_one_counts_and_flag_is_set():
    prices = {
        "good": price("good", 8.0, unit_id=1),   # 8 €/kg
        "bad": price("bad", 2.0, unit_id=3),     # 2 €/L
    }
    res = compute_cost_breakdown(
        [ing("good", qty=500, unit_id=2), ing("bad", qty=200, unit_id=2)],
        lookup_from(prices), UNITS, yield_qty=1, unit_categories=CATEGORIES,
    )
    assert res["computed_cost_total"] == 4.0     # only the compatible line
    assert res["has_incompatible_units"] is True
    assert res["_incompatible_units"] == ["bad"]
