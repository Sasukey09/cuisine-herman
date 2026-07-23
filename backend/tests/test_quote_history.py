"""Historique des offres reçues pour un produit (§10).

Ce qui a été **proposé** n'est pas ce qui a été **payé** : ces prix n'entrent
pas dans le food cost. Le calcul est pur, donc testable sans BDD.
"""

from datetime import date

from app.services.quotes.quote_history import build_history


def offer(supplier_id, day, price, **kw):
    base = {
        "supplier_id": supplier_id,
        "supplier_name": supplier_id,
        "date": date(2026, 1, day) if day else None,
        "unit_price": price,
        "quote_id": f"q{supplier_id}{day}",
    }
    base.update(kw)
    return base


def test_offers_are_sorted_most_recent_first():
    h = build_history([offer("A", 5, 10.0), offer("B", 20, 12.0), offer("C", 12, 11.0)])
    assert [o["supplier_id"] for o in h["offers"]] == ["B", "C", "A"]


def test_undated_offers_go_last_rather_than_being_placed_arbitrarily():
    h = build_history([offer("A", None, 10.0), offer("B", 3, 12.0)])
    assert [o["supplier_id"] for o in h["offers"]] == ["B", "A"]


def test_line_discount_is_part_of_the_offer():
    """Comparer un prix catalogue à un prix déjà remisé inventerait une hausse."""
    h = build_history([offer("A", 5, 20.0, discount_pct=10)])
    assert h["offers"][0]["net_unit_price"] == 18.0
    assert h["best_price"] == 18.0


def test_evolution_is_computed_per_supplier():
    h = build_history([offer("A", 5, 20.0), offer("A", 20, 22.0), offer("B", 12, 15.0)])
    by = {(o["supplier_id"], o["date"].day): o for o in h["offers"]}
    assert by[("A", 20)]["delta_pct_vs_previous"] == 10.0
    # La première offre d'un fournisseur n'a rien à quoi se comparer.
    assert by[("A", 5)]["delta_pct_vs_previous"] is None


def test_a_cheaper_competitor_is_not_a_price_drop():
    """Changer de fournisseur n'est pas une baisse de prix : sans cloisonnement
    par fournisseur, B afficherait −25 % qui ne veut rien dire."""
    h = build_history([offer("A", 5, 20.0), offer("B", 20, 15.0)])
    b = next(o for o in h["offers"] if o["supplier_id"] == "B")
    assert b["delta_pct_vs_previous"] is None


def test_best_offer_is_flagged_once():
    h = build_history([offer("A", 5, 20.0), offer("B", 20, 15.0), offer("C", 12, 18.0)])
    flagged = [o for o in h["offers"] if o["is_best"]]
    assert len(flagged) == 1 and flagged[0]["supplier_id"] == "B"
    assert h["best_supplier_name"] == "B"


def test_aggregates():
    h = build_history([offer("A", 5, 20.0), offer("B", 20, 10.0)])
    assert h["count"] == 2
    assert h["supplier_count"] == 2
    assert h["latest_price"] == 10.0  # la plus récente, pas la moins chère
    assert h["avg_price"] == 15.0


def test_offers_without_a_price_do_not_break_aggregates():
    h = build_history([offer("A", 5, None), offer("B", 20, 12.0)])
    assert h["count"] == 2
    assert h["best_price"] == 12.0
    assert h["avg_price"] == 12.0


def test_empty_history():
    h = build_history([])
    assert h["count"] == 0
    assert h["best_price"] is None
    assert h["latest_price"] is None
    assert h["avg_price"] is None
    assert h["offers"] == []


def test_commercial_fields_are_carried_through():
    h = build_history(
        [offer("A", 5, 20.0, pack_size="sac 25kg", brand="Marque Distributeur", min_qty=4)]
    )
    o = h["offers"][0]
    assert o["pack_size"] == "sac 25kg"
    assert o["brand"] == "Marque Distributeur"
    assert o["min_qty"] == 4.0
