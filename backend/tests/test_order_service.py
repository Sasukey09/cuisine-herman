"""Commandes fournisseur : planification depuis les devis et avancement.

Pur : tourne sans base. Le round-trip contre un vrai Postgres est dans
``test_purchasing.py``.
"""


from app.services.purchasing.order_service import (
    CANCELLED,
    CLOSED,
    CONFIRMED,
    DRAFT,
    PARTIALLY_RECEIVED,
    RECEIVED,
    SENT,
    can_transition,

    plan_orders,
)


def offer(supplier, product, qty, price, **kw):
    base = {
        "supplier_id": supplier,
        "supplier_name": supplier,
        "quote_line_id": f"ql-{supplier}-{product}",
        "product_id": product,
        "description": product,
        "qty": qty,
        "unit_price": price,
    }
    base.update(kw)
    return base


# --- planification --------------------------------------------------------
def test_the_comparator_verdict_becomes_several_orders():
    """Le point de tout le remaniement : le comparateur désigne le moins cher
    produit par produit, donc chez plusieurs fournisseurs. Une commande par
    fournisseur, sinon son conseil reste inexécutable."""
    plans = plan_orders([
        offer("METRO", "farine", 10, 18.5),
        offer("TRANSGOURMET", "beurre", 4, 42.0),
        offer("METRO", "sucre", 5, 12.0),
    ])
    assert len(plans) == 2
    by = {p["supplier_id"]: p for p in plans}
    assert len(by["METRO"]["lines"]) == 2
    assert len(by["TRANSGOURMET"]["lines"]) == 1


def test_the_biggest_basket_comes_first():
    plans = plan_orders([
        offer("PETIT", "sel", 1, 2.0),
        offer("GROS", "viande", 10, 50.0),
    ])
    assert [p["supplier_id"] for p in plans] == ["GROS", "PETIT"]


def test_the_offered_price_is_taken_as_is():
    """Rien n'est rechiffré depuis l'historique d'achat : c'est exactement ce
    qui rendait le contrôle devis/facture circulaire."""
    plans = plan_orders([offer("A", "farine", 10, 18.5)])
    line = plans[0]["lines"][0]
    assert line["unit_price"] == 18.5
    assert line["line_total"] == 185.0


def test_a_line_discount_lowers_the_line_total():
    plans = plan_orders([offer("A", "farine", 10, 20.0, discount_pct=10)])
    assert plans[0]["lines"][0]["line_total"] == 180.0


def test_a_document_line_total_wins_over_the_recomputed_one():
    """Le total du document peut porter un arrondi que qté × PU ne reproduit
    pas. Le recalculer silencieusement ferait mentir la commande."""
    plans = plan_orders([offer("A", "farine", 3, 3.33, line_total=10.0)])
    assert plans[0]["lines"][0]["line_total"] == 10.0


def test_delivery_fee_is_counted_once_per_supplier():
    """Deux devis du même fournisseur : on ne paie le port qu'une fois."""
    plans = plan_orders([
        offer("A", "farine", 10, 18.5, delivery_fee=50),
        offer("A", "sucre", 5, 12.0, delivery_fee=50),
    ])
    assert plans[0]["delivery_fee"] == 50.0


def test_the_order_total_includes_shipping_and_global_discount():
    plans = plan_orders([
        offer("A", "farine", 10, 10.0, delivery_fee=20, discount_total=15),
    ])
    p = plans[0]
    assert p["lines_total"] == 100.0
    assert p["total_amount"] == 105.0  # 100 − 15 + 20


def test_lines_from_two_quotes_of_one_supplier_land_in_one_order():
    plans = plan_orders([
        offer("A", "farine", 10, 18.5, quote_line_id="ql1"),
        offer("A", "beurre", 2, 40.0, quote_line_id="ql2"),
    ])
    assert len(plans) == 1
    assert {l["source_quote_line_id"] for l in plans[0]["lines"]} == {"ql1", "ql2"}


def test_the_quote_line_origin_is_kept_on_every_line():
    plans = plan_orders([offer("A", "farine", 10, 18.5)])
    assert plans[0]["lines"][0]["source_quote_line_id"] == "ql-A-farine"


def test_no_offer_no_order():
    assert plan_orders([]) == []


# --- cycle de vie ---------------------------------------------------------
def test_a_normal_life_runs_from_draft_to_closed():
    assert can_transition(DRAFT, SENT)
    assert can_transition(SENT, CONFIRMED)
    assert can_transition(CONFIRMED, RECEIVED)
    assert can_transition(RECEIVED, "invoiced")
    assert can_transition("invoiced", CLOSED)


def test_a_closed_or_cancelled_order_is_a_dead_end():
    """Rouvrir un engagement passé réécrirait l'histoire."""
    for target in (DRAFT, SENT, CONFIRMED, RECEIVED):
        assert not can_transition(CLOSED, target)
        assert not can_transition(CANCELLED, target)


def test_cancelling_is_possible_until_delivery_is_complete():
    for state in (DRAFT, SENT, CONFIRMED, PARTIALLY_RECEIVED):
        assert can_transition(state, CANCELLED)
    # Une commande entièrement livrée ne s'annule plus : elle se retourne.
    assert not can_transition(RECEIVED, CANCELLED)


def test_an_unknown_status_is_refused():
    assert not can_transition(DRAFT, "en_cours_peut_etre")


def test_the_progress_engine_is_not_duplicated():
    """Régression d'architecture : `order_service` portait sa propre mécanique
    « commandé vs reçu », qui ignorait le contrôle qualité et comptait comme
    reçu ce qui était reparti avec le livreur. Une seule question, un seul
    moteur — celui du service Réception."""
    from app.services.purchasing import order_service, reception_service

    assert not hasattr(order_service, "line_progress")
    assert hasattr(reception_service, "compare_reception")
    assert hasattr(reception_service, "order_progress")
