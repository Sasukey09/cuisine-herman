"""Cœur pur du moteur d'économies : aucune base.

Le round-trip contre un vrai Postgres est dans ``test_savings_real_db.py``.
"""
from app.services.purchasing.savings_service import compute_savings, SAVINGS_LABELS


def line(chosen, competing, qty=1.0, pid="p1", sid="s1"):
    return {
        "product_id": pid,
        "supplier_id": sid,
        "qty": qty,
        "chosen_unit_price": chosen,
        "competing_prices": list(competing),
    }


def test_realized_plus_missed_equals_possible():
    # offres {8, 10, 12}, choisie 10, qté 2 → réalisée 4, manquée 4, possible 8
    r = compute_savings([line(10.0, [8.0, 12.0], qty=2)])
    assert r["realized"] == 4.0
    assert r["missed"] == 4.0
    assert r["possible"] == 8.0
    assert r["realized"] + r["missed"] == r["possible"]
    assert r["compared_lines"] == 1


def test_best_choice_when_cheapest_taken():
    # choisie = la moins chère → manquée 0, is_best vrai
    r = compute_savings([line(10.0, [12.0], qty=5)])
    assert r["realized"] == 10.0   # (12-10)*5
    assert r["missed"] == 0.0
    assert r["best_choice_rate"] == 1.0
    assert r["lines"][0]["is_best_choice"] is True


def test_negotiated_below_all_offers_is_never_penalised():
    # choisie 11 sous toutes les offres {12,13} → manquée 0, réalisée (13-11)*1
    r = compute_savings([line(11.0, [12.0, 13.0], qty=1)])
    assert r["missed"] == 0.0
    assert r["realized"] == 2.0
    assert r["lines"][0]["is_best_choice"] is True


def test_a_line_without_competition_is_excluded():
    r = compute_savings([line(10.0, [], qty=3)])
    assert r["compared_lines"] == 0
    assert r["realized"] == 0.0
    assert r["missed"] == 0.0
    assert r["best_choice_rate"] is None


def test_all_offers_equal_yield_zero_but_count_as_best():
    r = compute_savings([line(10.0, [10.0], qty=4)])
    assert r["realized"] == 0.0
    assert r["missed"] == 0.0
    assert r["possible"] == 0.0
    assert r["compared_lines"] == 1
    assert r["best_choice_rate"] == 1.0


def test_best_choice_rate_over_several_lines():
    r = compute_savings([
        line(10.0, [12.0]),        # meilleur choix
        line(12.0, [10.0]),        # pas le meilleur (manquée > 0)
    ])
    assert r["compared_lines"] == 2
    assert r["best_choice_rate"] == 0.5


def test_labels_are_the_single_source():
    assert set(SAVINGS_LABELS) == {"realized", "missed", "possible", "best_choice_rate"}
    assert SAVINGS_LABELS["realized"] == "Économisé"
