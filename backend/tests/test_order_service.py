"""Commandes fournisseur : planification depuis les devis et avancement.

Pur : tourne sans base. Le round-trip contre un vrai Postgres est dans
``test_purchasing.py``.
"""

import pytest

from app.services.purchasing.order_service import (
    CANCELLED,
    CLOSED,
    CONFIRMED,
    DRAFT,
    PARTIALLY_RECEIVED,
    RECEIVED,
    SENT,
    can_transition,
    line_progress,
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


# --- avancement : commandé vs reçu ----------------------------------------
def ordered_line(lid, qty, price=10.0, product=None):
    return {
        "id": lid,
        "product_id": product or lid,
        "description": lid,
        "qty_ordered": qty,
        "unit_price": price,
    }


def received_line(lid, qty, condition="ok", product=None):
    return {
        "order_line_id": lid,
        "product_id": product,
        "description": product or lid,
        "qty_received": qty,
        "condition": condition,
    }


def test_everything_delivered_closes_the_order():
    r = line_progress([ordered_line("l1", 10)], [received_line("l1", 10)])
    assert r["is_complete"] is True
    assert r["issue_count"] == 0
    assert r["suggested_status"] == RECEIVED


def test_a_partial_delivery_is_valued_not_just_counted():
    """Ce qu'on oppose au fournisseur, c'est un montant, pas une quantité."""
    r = line_progress([ordered_line("l1", 10, price=18.5)], [received_line("l1", 6)])
    line = r["lines"][0]
    assert line["status"] == "partial"
    assert line["qty_missing"] == 4
    assert line["missing_value"] == 74.0
    assert r["suggested_status"] == PARTIALLY_RECEIVED


def test_several_deliveries_add_up_on_the_same_line():
    """Une commande livrée en deux fois est complète, pas partielle."""
    r = line_progress(
        [ordered_line("l1", 10)],
        [received_line("l1", 4), received_line("l1", 6)],
    )
    assert r["is_complete"] is True


def test_nothing_received_yet_suggests_no_status_change():
    r = line_progress([ordered_line("l1", 10)], [])
    assert r["nothing_received"] is True
    assert r["suggested_status"] is None
    assert r["lines"][0]["status"] == "pending"


def test_a_product_delivered_outside_the_order_is_flagged():
    r = line_progress(
        [ordered_line("l1", 10)],
        [received_line("l1", 10), received_line(None, 3, product="Crème")],
    )
    assert r["extra_count"] == 1
    extra = [l for l in r["lines"] if l["status"] == "extra"][0]
    assert extra["description"] == "Crème"
    # La commande reste complète : le surplus n'enlève rien à ce qui était dû.
    assert r["is_complete"] is True


def test_an_over_delivery_is_not_a_shortage():
    r = line_progress([ordered_line("l1", 10)], [received_line("l1", 12)])
    assert r["lines"][0]["status"] == "over"
    assert r["lines"][0]["missing_value"] == 0.0


def test_a_damaged_delivery_is_reported_even_at_the_right_quantity():
    r = line_progress(
        [ordered_line("l1", 10)],
        [received_line("l1", 10, condition="damaged")],
    )
    assert r["lines"][0]["conditions"] == ["damaged"]


def test_rounding_noise_is_not_a_shortage():
    r = line_progress([ordered_line("l1", 10)], [received_line("l1", 9.9999)])
    assert r["lines"][0]["status"] == "ok"


@pytest.mark.parametrize("qty", [0, None])
def test_a_line_ordered_with_no_quantity_does_not_block_completion(qty):
    r = line_progress([ordered_line("l1", qty)], [])
    assert r["lines"][0]["status"] == "ok"
