"""Contrôle de réception : commandé face à livré.

Pur : tourne sans base. Le cycle complet contre un vrai Postgres est dans
``test_reception_real_db.py``.
"""

import pytest

from app.services.purchasing import order_service
from app.services.purchasing.reception_service import (
    CONDITION_LABELS,
    CONDITIONS,
    DAMAGED,
    EXTRA,
    MISSING,
    OK,
    REJECTED,
    SUBSTITUTED,
    compare_reception,
    counts_toward_stock,
)


def ordered(lid, qty, price=10.0, pack=None):
    return {
        "id": lid,
        "product_id": f"p-{lid}",
        "description": lid,
        "qty_ordered": qty,
        "unit_price": price,
        "pack_size": pack,
    }


def got(lid, qty, condition=OK, price=None, pack=None, **kw):
    base = {
        "order_line_id": lid,
        "product_id": f"p-{lid}",
        "description": lid,
        "qty_received": qty,
        "condition": condition,
        "unit_price": price,
        "pack_size": pack,
    }
    base.update(kw)
    return base


# --- le cas nominal -------------------------------------------------------
def test_a_complete_delivery_closes_the_line():
    r = compare_reception([ordered("l1", 10)], [got("l1", 10)])
    assert r["lines"][0]["status"] == OK
    assert r["is_complete"] is True
    assert r["suggested_status"] == order_service.RECEIVED


def test_a_partial_delivery_states_what_is_still_due():
    r = compare_reception([ordered("l1", 10, price=18.5)], [got("l1", 6)])
    line = r["lines"][0]
    assert line["status"] == "partial"
    assert line["qty_remaining"] == 4
    # Ce qu'on oppose au fournisseur est un montant, pas un compte.
    assert line["missing_value"] == 74.0
    assert r["suggested_status"] == order_service.PARTIALLY_RECEIVED


def test_nothing_received_yet_suggests_no_change():
    r = compare_reception([ordered("l1", 10)], [])
    assert r["nothing_received"] is True
    assert r["lines"][0]["status"] == "pending"
    assert r["suggested_status"] is None


# --- plusieurs réceptions pour une commande -------------------------------
def test_a_second_delivery_completes_the_first():
    """Sans la mémoire des réceptions antérieures, une commande livrée en deux
    fois afficherait deux livraisons partielles au lieu d'une complète."""
    r = compare_reception(
        [ordered("l1", 10)],
        [got("l1", 6)],
        previously_received={"l1": 4},
    )
    line = r["lines"][0]
    assert line["qty_received_before"] == 4
    assert line["qty_received_now"] == 6
    assert line["qty_received_total"] == 10
    assert line["status"] == OK
    assert r["is_complete"] is True


def test_the_running_total_never_double_counts_the_current_receipt():
    r = compare_reception(
        [ordered("l1", 10)], [got("l1", 4)], previously_received={"l1": 4}
    )
    assert r["lines"][0]["qty_received_total"] == 8
    assert r["lines"][0]["qty_remaining"] == 2


# --- les six états d'une ligne --------------------------------------------
def test_every_condition_has_a_french_label():
    for c in CONDITIONS:
        assert CONDITION_LABELS.get(c), c


def test_a_rejected_line_leaves_the_order_still_due():
    """Refusée, la marchandise repart : la commande n'est pas honorée."""
    r = compare_reception([ordered("l1", 10)], [got("l1", 10, condition=REJECTED)])
    line = r["lines"][0]
    assert line["qty_received_now"] == 10, "elle est bien arrivée physiquement"
    assert line["qty_received_total"] == 0, "mais elle ne compte pas comme livrée"
    assert line["status"] == "pending"
    assert r["is_complete"] is False


def test_a_damaged_line_counts_as_delivered_but_is_flagged():
    """Abîmée, elle est en réserve — c'est une perte à venir, pas un manquant."""
    r = compare_reception([ordered("l1", 10)], [got("l1", 10, condition=DAMAGED)])
    line = r["lines"][0]
    assert line["status"] == OK
    assert line["conditions"] == [DAMAGED]
    assert r["issue_count"] >= 1, "l'anomalie doit rester visible"


def test_rejected_and_damaged_are_not_the_same_for_stock():
    """Les confondre fausserait l'inventaire dès le premier jour."""
    assert counts_toward_stock(DAMAGED) is True
    assert counts_toward_stock(REJECTED) is False
    assert counts_toward_stock(OK) is True


def test_a_substituted_product_is_reported_as_a_product_gap():
    r = compare_reception(
        [ordered("l1", 10)],
        [got("l1", 10, condition=SUBSTITUTED, substituted_product_id="autre")],
    )
    assert "product" in r["lines"][0]["anomalies"]


# --- les écarts que le seul comptage ne voit pas --------------------------
def test_a_price_gap_on_the_delivery_note_is_caught():
    r = compare_reception([ordered("l1", 10, price=18.5)], [got("l1", 10, price=21.0)])
    assert "price" in r["lines"][0]["anomalies"]


def test_a_rounding_difference_is_not_a_price_gap():
    r = compare_reception([ordered("l1", 10, price=18.5)], [got("l1", 10, price=18.502)])
    assert "price" not in r["lines"][0]["anomalies"]


def test_a_packaging_gap_is_caught():
    """10 sacs de 10 kg au lieu de 10 sacs de 25 kg : même nombre de lignes,
    150 kg de moins."""
    r = compare_reception(
        [ordered("l1", 10, pack="sac 25kg")], [got("l1", 10, pack="sac 10kg")]
    )
    assert "pack_size" in r["lines"][0]["anomalies"]


def test_the_same_packaging_written_differently_is_not_a_gap():
    r = compare_reception(
        [ordered("l1", 10, pack="Sac 25kg")], [got("l1", 10, pack="  sac 25KG ")]
    )
    assert "pack_size" not in r["lines"][0]["anomalies"]


def test_an_unknown_packaging_on_one_side_is_not_a_gap():
    """Un bon de livraison muet sur le conditionnement n'accuse personne."""
    r = compare_reception([ordered("l1", 10, pack="sac 25kg")], [got("l1", 10)])
    assert "pack_size" not in r["lines"][0]["anomalies"]


def test_a_delivery_by_another_supplier_is_flagged_on_the_document():
    r = compare_reception(
        [ordered("l1", 10)],
        [got("l1", 10)],
        order_supplier_id="METRO",
        receipt_supplier_id="AUTRE",
    )
    assert "supplier" in r["document_anomalies"]
    assert r["issue_count"] >= 1


def test_the_expected_supplier_raises_no_flag():
    r = compare_reception(
        [ordered("l1", 10)], [got("l1", 10)],
        order_supplier_id="METRO", receipt_supplier_id="METRO",
    )
    assert r["document_anomalies"] == []


# --- hors commande --------------------------------------------------------
def test_a_product_delivered_outside_the_order_is_kept_and_flagged():
    r = compare_reception(
        [ordered("l1", 10)],
        [got("l1", 10), {"order_line_id": None, "description": "Crème", "qty_received": 3}],
    )
    extra = [l for l in r["lines"] if l["status"] == EXTRA][0]
    assert extra["description"] == "Crème"
    assert extra["anomalies"] == ["unordered"]
    assert r["extra_count"] == 1
    # Le surplus n'enlève rien à ce qui était dû.
    assert r["is_complete"] is True


def test_a_delivery_with_no_order_is_all_extra():
    r = compare_reception([], [{"order_line_id": None, "description": "Crème", "qty_received": 3}])
    assert r["extra_count"] == 1
    assert r["is_complete"] is False


# --- robustesse -----------------------------------------------------------
def test_an_over_delivery_owes_nothing():
    r = compare_reception([ordered("l1", 10)], [got("l1", 12)])
    assert r["lines"][0]["status"] == "over"
    assert r["lines"][0]["missing_value"] == 0.0
    assert r["lines"][0]["qty_remaining"] == 0.0


def test_rounding_noise_is_not_a_shortage():
    r = compare_reception([ordered("l1", 10)], [got("l1", 9.9999)])
    assert r["lines"][0]["status"] == OK


@pytest.mark.parametrize("qty", [0, None])
def test_a_line_ordered_without_quantity_never_holds_the_order_open(qty):
    """Rien n'était dû sur cette ligne. La laisser « en attente » empêcherait
    la commande de se clore, définitivement."""
    r = compare_reception([ordered("l1", qty)], [])
    assert r["lines"][0]["status"] == OK
    assert r["is_complete"] is True


def test_two_partial_deliveries_of_the_same_line_add_up_within_one_receipt():
    r = compare_reception([ordered("l1", 10)], [got("l1", 4), got("l1", 6)])
    assert r["lines"][0]["qty_received_total"] == 10
    assert r["lines"][0]["status"] == OK


def test_missing_is_a_condition_a_receiver_can_state_explicitly():
    """Le réceptionnaire peut déclarer un manquant sans saisir 0 : la ligne
    porte la mention, et le calcul reste celui des quantités."""
    r = compare_reception([ordered("l1", 10)], [got("l1", 0, condition=MISSING)])
    assert MISSING in r["lines"][0]["conditions"]
    assert r["lines"][0]["status"] == "pending"


def test_the_public_helper_is_the_one_endpoints_use():
    """Régression : le pré-remplissage appelait une fonction privée en passant
    une chaîne vide comme identifiant à exclure. Comparer un UUID à '' fait
    échouer Postgres à l'exécution — invisible hors base."""
    from app.services.purchasing import reception_service as rs

    assert hasattr(rs, "received_by_order_line")
    assert not hasattr(rs, "_received_before"), "l'ancienne privée ne doit plus traîner"

    import inspect

    sig = inspect.signature(rs.received_by_order_line)
    assert sig.parameters["exclude_receipt_id"].default is None, (
        "l'exclusion doit être optionnelle, pas une chaîne vide"
    )
