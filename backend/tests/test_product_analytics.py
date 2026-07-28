from datetime import date
from app.services.purchasing.product_analytics import scorecard

TODAY = date(2026, 7, 28)


def _p(when, sid, name, total, cost):
    return {"purchase_date": when, "supplier_id": sid, "supplier_name": name,
            "total_price": total, "unit_cost_standard": cost}


def _sav():
    return {"realized": 20.0, "missed": 0.0, "possible": 20.0, "best_choice_rate": 1.0,
            "compared_lines": 1, "labels": {"realized": "Économisé"}}


def test_monthly_and_annual_from_purchases():
    card = scorecard(
        [_p(date(2026, 6, 5), "a", "A", 100, 10.0), _p(date(2026, 6, 20), "a", "A", 50, 10.0),
         _p(date(2026, 7, 2), "b", "B", 200, 12.0)],
        {"count": 0}, _sav(), None, 0, TODAY)
    assert card["annual_amount"] == 350.0
    assert card["monthly"] == [{"month": "2026-06", "amount": 150.0}, {"month": "2026-07", "amount": 200.0}]
    assert card["purchase_count"] == 3 and card["supplier_count"] == 2


def test_top_suppliers_ranked_with_cheapest_flag():
    card = scorecard(
        [_p(date(2026, 7, 1), "a", "A", 100, 10.0), _p(date(2026, 7, 2), "b", "B", 400, 12.0),
         _p(date(2026, 7, 3), "a", "A", 50, 10.0)],
        {"count": 0}, _sav(), {"supplier_id": "a", "supplier_name": "A", "cost": 10.0}, 0, TODAY)
    assert card["top_suppliers"][0]["supplier_id"] == "b"           # B: 400
    assert card["top_suppliers"][1]["amount"] == 150.0              # A cumulé
    assert card["top_suppliers"][1]["is_cheapest"] is True and card["top_suppliers"][0]["is_cheapest"] is False
    assert card["cheapest_supplier"] == {"supplier_id": "a", "supplier_name": "A", "cost": 10.0}


def test_costs_and_price_trend():
    # 6 vieux mois à 10, 6 récents à 12 → +20 %
    card = scorecard(
        [_p(date(2025, 9, 1), "a", "A", 100, 10.0), _p(date(2026, 7, 1), "a", "A", 100, 12.0)],
        {"count": 0}, _sav(), None, 0, TODAY)
    assert card["last_cost"] == 12.0 and card["best_cost"] == 10.0 and card["avg_cost"] == 11.0
    assert card["price_trend_pct"] == 20.0


def test_offers_block_and_counts():
    qh = {"count": 3, "supplier_count": 2, "best_price": 9.5, "best_supplier_name": "A",
          "latest_price": 10.0, "avg_price": 10.5}
    card = scorecard([], qh, _sav(), None, 4, TODAY)
    assert card["offer_count"] == 3 and card["recipe_count"] == 4
    assert card["offers"] == {"best_price": 9.5, "best_supplier_name": "A",
                              "latest_price": 10.0, "avg_price": 10.5, "supplier_count": 2}
    assert card["savings"]["realized"] == 20.0


def test_empty_product_is_honest_and_product_centric():
    card = scorecard([], {"count": 0}, _sav(), None, 0, TODAY)
    assert card["annual_amount"] == 0.0 and card["top_suppliers"] == [] and card["monthly"] == []
    assert card["offers"] is None and card["price_trend_pct"] is None
    # produit-centré : PAS de champs fournisseur-only
    for k in ("conformity_rate", "on_time_rate", "score", "late_count"):
        assert k not in card
