"""Cœur pur du moteur d'économies : aucune base.

Le round-trip contre un vrai Postgres est dans ``test_savings_real_db.py``.
"""
from app.services.purchasing.savings_service import (
    _comparable,
    compute_savings,
    SAVINGS_LABELS,
)


def _offer(unit_price, pack_size=None, description=None, discount_pct=None):
    return {
        "unit_price": unit_price,
        "pack_size": pack_size,
        "description": description,
        "discount_pct": discount_pct,
    }


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


# --------------------------------------------------------------------------- #
# `_comparable` : on compare au prix/unité de base, comme quote_matrix.
# --------------------------------------------------------------------------- #
def test_comparable_same_base_unit_normalises_to_price_per_kg():
    # METRO 10 €/5 kg = 2,00 €/kg (choisie) ; TRANSGOURMET 14 €/10 kg = 1,40 €/kg.
    # Au prix unitaire brut, 10 < 14 : METRO paraîtrait le moins cher. Au kilo,
    # c'est l'inverse — et c'est ce que le moteur doit voir.
    pair = _comparable(_offer(10.0, "5 kg"), [_offer(14.0, "10 kg")])
    assert pair == (2.0, [1.4])

    # Enchaîné sur le cœur : choisie plus chère au kilo → réalisée 0, manquée réelle.
    chosen_value, competing_values = pair
    r = compute_savings([line(chosen_value, competing_values, qty=5)])
    assert r["realized"] == 0.0
    assert r["missed"] == 3.0  # (2.0 - 1.4) * 5
    assert r["lines"][0]["is_best_choice"] is False


def test_comparable_no_pack_falls_back_to_raw_unit_price():
    # Aucun conditionnement lisible → même unité implicite → prix brut.
    pair = _comparable(_offer(10.0, None), [_offer(14.0, None)])
    assert pair == (10.0, [14.0])


def test_comparable_mixed_packaging_is_not_compared():
    # Choisie normalise (5 kg), concurrente non → non comparable → None.
    assert _comparable(_offer(10.0, "5 kg"), [_offer(14.0, None)]) is None


def test_comparable_different_base_units_are_not_compared():
    # kg vs L : deux unités de base différentes → None (on ne compare pas kg et L).
    assert _comparable(_offer(10.0, "5 kg"), [_offer(14.0, "3 L")]) is None
