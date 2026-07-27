"""Fiche fournisseur 360° : agrégation des faits d'achat.

Pur : tourne sans base. Le round-trip contre un vrai Postgres est dans
``test_supplier_overview_real_db.py``.
"""

from datetime import date

from app.services.purchasing.supplier_analytics import scorecard

TODAY = date(2026, 7, 23)


def order(total, status="received"):
    return {"status": status, "total_amount": total, "ordered_at": None}


def receipt(issue_count=0, received=None, expected=None):
    return {"received_at": received, "expected_date": expected, "issue_count": issue_count}


def purchase(total, when, cost=None, pid="p1", name="Farine"):
    return {
        "purchase_date": when,
        "total_price": total,
        "unit_cost_standard": cost,
        "product_id": pid,
        "product_name": name,
    }


def empty():
    return scorecard([], [], [], [], 0, TODAY)


# --- un fournisseur vierge n'invente rien ---------------------------------
def test_a_supplier_with_no_history_has_no_score():
    card = empty()
    assert card["score"] is None, "pas de faits, pas de score"
    assert card["conformity_rate"] is None
    assert card["on_time_rate"] is None
    assert card["annual_amount"] == 0
    assert card["order_count"] == 0


# --- volumes --------------------------------------------------------------
def test_cancelled_orders_do_not_count_in_the_order_volume():
    card = scorecard(
        [order(100), order(200), order(999, status="cancelled")], [], [], [], 0, TODAY
    )
    assert card["order_count"] == 2
    assert card["ordered_total"] == 300.0
    # …mais elles restent visibles dans la répartition par statut.
    assert card["orders_by_status"]["cancelled"] == 1


def test_annual_amount_counts_only_the_last_365_days():
    card = scorecard(
        [],
        [],
        [],
        [purchase(500, date(2026, 7, 1)), purchase(999, date(2024, 1, 1))],
        0,
        TODAY,
    )
    assert card["annual_amount"] == 500.0, "le vieux paiement est hors des 12 mois"


def test_annual_amount_is_paid_not_ordered():
    """Le montant annuel vient de l'historique d'achat (payé), pas des
    commandes (engagé) : c'est la dépense réelle."""
    card = scorecard(
        [order(1000)], [], [], [purchase(600, date(2026, 7, 1))], 0, TODAY
    )
    assert card["annual_amount"] == 600.0
    assert card["ordered_total"] == 1000.0


# --- évolution mensuelle et produits --------------------------------------
def test_monthly_series_groups_and_sorts_by_month():
    card = scorecard(
        [],
        [],
        [],
        [
            purchase(100, date(2026, 6, 5)),
            purchase(50, date(2026, 6, 20)),
            purchase(200, date(2026, 7, 2)),
        ],
        0,
        TODAY,
    )
    assert card["monthly"] == [
        {"month": "2026-06", "amount": 150.0},
        {"month": "2026-07", "amount": 200.0},
    ]


def test_top_products_ranked_by_amount():
    card = scorecard(
        [],
        [],
        [],
        [
            purchase(100, date(2026, 7, 1), pid="farine", name="Farine"),
            purchase(400, date(2026, 7, 1), pid="beurre", name="Beurre"),
            purchase(50, date(2026, 7, 2), pid="farine", name="Farine"),
        ],
        0,
        TODAY,
    )
    assert card["distinct_products"] == 2
    assert card["top_products"][0]["product_name"] == "Beurre"
    assert card["top_products"][1]["amount"] == 150.0  # farine cumulée


# --- conformité -----------------------------------------------------------
def test_conformity_rate_is_issue_free_receptions():
    card = scorecard([], [receipt(0), receipt(0), receipt(2)], [], [], 0, TODAY)
    assert card["conformity_rate"] == round(2 / 3, 3)


def test_a_supplier_always_conform_scores_on_conformity_alone():
    card = scorecard([], [receipt(0), receipt(0)], [], [], 0, TODAY)
    assert card["conformity_rate"] == 1.0
    assert card["score"] == 100  # pas de dates → seule la conformité juge


# --- ponctualité ----------------------------------------------------------
def test_late_receptions_need_both_dates():
    """Sans date promise, pas de retard : on ne reproche pas un retard qu'on
    n'a jamais annoncé."""
    card = scorecard(
        [],
        [receipt(0, received=date(2026, 7, 10))],  # pas d'expected
        [],
        [],
        0,
        TODAY,
    )
    assert card["on_time_rate"] is None
    assert card["late_count"] == 0


def test_a_late_delivery_is_counted():
    card = scorecard(
        [],
        [
            receipt(0, received=date(2026, 7, 10), expected=date(2026, 7, 5)),  # en retard
            receipt(0, received=date(2026, 7, 4), expected=date(2026, 7, 5)),   # à l'heure
        ],
        [],
        [],
        0,
        TODAY,
    )
    assert card["late_count"] == 1
    assert card["on_time_rate"] == 0.5


def test_score_blends_conformity_and_punctuality():
    card = scorecard(
        [],
        [
            receipt(0, received=date(2026, 7, 4), expected=date(2026, 7, 5)),  # conforme, à l'heure
            receipt(1, received=date(2026, 7, 10), expected=date(2026, 7, 5)),  # anomalie, en retard
        ],
        [],
        [],
        0,
        TODAY,
    )
    # conformité 0.5, ponctualité 0.5 → 50
    assert card["conformity_rate"] == 0.5
    assert card["on_time_rate"] == 0.5
    assert card["score"] == 50


# --- inflation subie ------------------------------------------------------
def test_price_trend_compares_first_and_second_half_year():
    card = scorecard(
        [],
        [],
        [],
        [
            purchase(100, date(2025, 9, 1), cost=10.0),   # vieux (1er semestre) : 10
            purchase(100, date(2026, 7, 1), cost=12.0),   # récent : 12 → +20 %
        ],
        0,
        TODAY,
    )
    assert card["price_trend_pct"] == 20.0


def test_price_trend_needs_both_halves():
    card = scorecard([], [], [], [purchase(100, date(2026, 7, 1), cost=12.0)], 0, TODAY)
    assert card["price_trend_pct"] is None


# --- garde-fou : jamais de « montant économisé » inventé ------------------
def test_no_fabricated_savings_field():
    """Le cœur pur ``scorecard`` n'invente pas d'économie : il n'a pas les offres.
    Le vrai « montant économisé » est désormais assemblé dans ``overview`` à partir
    des comparatifs de devis (moteur B) et vérifié dans ``test_savings_real_db.py``.
    Ici on garde la garantie que la couche pure, elle, reste sans économie inventée."""
    assert "savings" not in empty()
    assert "montant_economise" not in empty()
