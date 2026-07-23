"""Contrôle qualité et écarts de réception.

Pur : tourne sans base. Le cycle complet contre un vrai Postgres est dans
``test_receipts_api_real_db.py``.
"""

import pytest

from app.services.purchasing import order_service
from app.services.purchasing.reception_service import (
    ACCEPTED,
    BREAKAGE,
    CONFORME,
    DESTROYED,
    EN_ATTENTE,
    LINE_STATE_LABELS,
    OUTCOME_LABELS,
    OUTCOMES,
    PACKAGING_DAMAGED,
    PARTIELLEMENT_CONFORME,
    REASON_LABELS,
    REASONS,
    REFUSEE,
    REJECTED,
    REMPLACEE,
    SHORT_SHELF_LIFE,
    SUBSTITUTED,
    accepted_qty,
    compare_reception,
    line_quality,
)


def issue(qty, reason=PACKAGING_DAMAGED, outcome=REJECTED):
    return {"qty": qty, "reason": reason, "outcome": outcome}


def delivered(qty, issues=None, **kw):
    base = {"qty_delivered": qty, "issues": issues or []}
    base.update(kw)
    return base


# --------------------------------------------------------------------------- #
# La qualité d'une ligne
# --------------------------------------------------------------------------- #
def test_a_clean_delivery_is_fully_accepted():
    q = line_quality(delivered(10))
    assert q == {
        "qty_delivered": 10.0,
        "qty_accepted": 10.0,
        "qty_rejected": 0.0,
        "qty_destroyed": 0.0,
        "state": CONFORME,
        "state_label": "Conforme",
        "reasons": [],
    }


def test_the_case_that_justified_the_whole_model():
    """Sur 10 unités : 1 refusée pour DLC courte, 1 détruite pour casse,
    3 gardées sous réserve pour emballage endommagé. Le modèle précédent
    obligeait à choisir UN seul motif pour la ligne entière."""
    q = line_quality(
        delivered(
            10,
            [
                issue(1, SHORT_SHELF_LIFE, REJECTED),
                issue(1, BREAKAGE, DESTROYED),
                issue(3, PACKAGING_DAMAGED, ACCEPTED),
            ],
        )
    )
    assert q["qty_accepted"] == 8.0
    assert q["qty_rejected"] == 1.0
    assert q["qty_destroyed"] == 1.0
    assert q["state"] == PARTIELLEMENT_CONFORME
    assert q["reasons"] == sorted([SHORT_SHELF_LIFE, BREAKAGE, PACKAGING_DAMAGED])


def test_an_issue_kept_under_reserve_does_not_reduce_the_accepted_quantity():
    """Un emballage abîmé sur une marchandise qu'on garde : on l'a, on la paie.
    La réserve reste au dossier pour la discussion avec le fournisseur."""
    q = line_quality(delivered(10, [issue(3, PACKAGING_DAMAGED, ACCEPTED)]))
    assert q["qty_accepted"] == 10.0
    assert q["state"] == PARTIELLEMENT_CONFORME


def test_an_issue_without_quantity_covers_the_whole_line():
    """Le cas usuel du « tout refusé » : on ne veut pas obliger à le chiffrer."""
    q = line_quality(delivered(10, [{"reason": BREAKAGE, "outcome": REJECTED}]))
    assert q["qty_rejected"] == 10.0
    assert q["qty_accepted"] == 0.0
    assert q["state"] == REFUSEE


def test_nothing_delivered_yet():
    q = line_quality(delivered(0))
    assert q["state"] == EN_ATTENTE
    assert q["qty_accepted"] == 0.0


def test_a_substitution_states_itself_even_when_quantities_match():
    q = line_quality(delivered(10, substituted_product_id="autre-produit"))
    assert q["state"] == REMPLACEE
    # Le produit de remplacement est bien là : il n'y a pas de manquant.
    assert q["qty_accepted"] == 10.0


def test_a_substitution_declared_as_a_reason_is_recognised_too():
    q = line_quality(delivered(10, [issue(10, SUBSTITUTED, ACCEPTED)]))
    assert q["state"] == REMPLACEE


def test_issues_can_never_make_the_accepted_quantity_negative():
    """Une saisie incohérente ne doit pas produire un stock négatif."""
    q = line_quality(delivered(5, [issue(50, outcome=REJECTED)]))
    assert q["qty_accepted"] == 0.0
    assert q["qty_rejected"] == 5.0


def test_accepted_qty_is_the_shortcut_used_everywhere_else():
    assert accepted_qty(delivered(10, [issue(2, outcome=REJECTED)])) == 8.0


# --- les libellés vivent côté serveur -------------------------------------
def test_every_reason_has_a_french_label():
    for r in REASONS:
        assert REASON_LABELS.get(r), r


def test_every_outcome_has_a_french_label():
    for o in OUTCOMES:
        assert OUTCOME_LABELS.get(o), o


def test_every_line_state_has_a_french_label():
    for label in LINE_STATE_LABELS.values():
        assert label and label[0].isupper()


def test_the_eight_quality_checks_asked_for_are_all_available():
    """Les motifs du poste de contrôle qualité, tels que définis avec le métier."""
    for r in (
        "packaging_damaged",
        "product_damaged",
        "short_shelf_life",
        "wrong_grade",
        "wrong_temperature",
        "wrong_packaging",
        "substituted",
        "breakage",
    ):
        assert r in REASONS


# --------------------------------------------------------------------------- #
# Le contrôle face à la commande
# --------------------------------------------------------------------------- #
def ordered(lid, qty, price=10.0, pack=None):
    return {
        "id": lid,
        "product_id": f"p-{lid}",
        "description": lid,
        "qty_ordered": qty,
        "unit_price": price,
        "pack_size": pack,
    }


def got(lid, qty, issues=None, price=None, pack=None, **kw):
    base = {
        "order_line_id": lid,
        "product_id": f"p-{lid}",
        "description": lid,
        "qty_delivered": qty,
        "unit_price": price,
        "pack_size": pack,
        "issues": issues or [],
    }
    base.update(kw)
    return base


def test_a_complete_delivery_closes_the_line():
    r = compare_reception([ordered("l1", 10)], [got("l1", 10)])
    assert r["lines"][0]["status"] == "ok"
    assert r["is_complete"] is True
    assert r["suggested_status"] == order_service.RECEIVED


def test_a_partial_delivery_values_what_is_owed():
    r = compare_reception([ordered("l1", 10, price=18.5)], [got("l1", 6)])
    line = r["lines"][0]
    assert line["status"] == "partial"
    assert line["qty_remaining"] == 4
    assert line["missing_value"] == 74.0
    assert r["suggested_status"] == order_service.PARTIALLY_RECEIVED


def test_rejected_goods_leave_the_order_still_due():
    """Le camion est reparti avec : la commande n'est pas honorée."""
    r = compare_reception(
        [ordered("l1", 10, price=18.5)], [got("l1", 10, [issue(10, outcome=REJECTED)])]
    )
    line = r["lines"][0]
    assert line["qty_delivered_now"] == 10, "c'est bien arrivé physiquement"
    assert line["qty_accepted_now"] == 0, "mais rien n'est resté"
    assert line["status"] == "pending"
    assert line["missing_value"] == 185.0
    assert r["is_complete"] is False
    assert r["rejected_count"] == 1


def test_destroyed_goods_are_reported_separately_from_rejected():
    """Refusée, elle repart ; détruite, on s'en débarrasse. Dans les deux cas on
    ne l'a pas — mais la distinction sert pour l'avoir fournisseur."""
    r = compare_reception(
        [ordered("l1", 10)], [got("l1", 10, [issue(2, BREAKAGE, DESTROYED)])]
    )
    line = r["lines"][0]
    assert line["qty_destroyed_now"] == 2
    assert line["qty_rejected_now"] == 0
    assert line["qty_accepted_now"] == 8
    assert r["destroyed_count"] == 1


def test_a_quality_issue_is_reported_even_at_the_right_quantity():
    r = compare_reception(
        [ordered("l1", 10)], [got("l1", 10, [issue(3, PACKAGING_DAMAGED, ACCEPTED)])]
    )
    line = r["lines"][0]
    assert line["status"] == "ok", "tout est là"
    assert PACKAGING_DAMAGED in line["reasons"], "mais l'anomalie reste visible"
    assert r["issue_count"] >= 1


# --- réceptions successives ------------------------------------------------
def test_a_second_delivery_completes_the_first():
    r = compare_reception(
        [ordered("l1", 10)], [got("l1", 6)], previously_received={"l1": 4}
    )
    line = r["lines"][0]
    assert line["qty_received_before"] == 4
    assert line["qty_received_total"] == 10
    assert r["is_complete"] is True


def test_a_corrective_receipt_completes_what_was_rejected():
    """Le scénario métier de la réception corrective : la première livraison a
    été refusée, la seconde est bonne. La première n'ayant rien apporté, elle
    ne compte pas dans le déjà-reçu."""
    first = compare_reception(
        [ordered("l1", 10)], [got("l1", 10, [issue(10, outcome=REJECTED)])]
    )
    assert first["is_complete"] is False

    second = compare_reception(
        [ordered("l1", 10)], [got("l1", 10)], previously_received={"l1": 0.0}
    )
    assert second["is_complete"] is True


# --- écarts que le seul comptage ne voit pas ------------------------------
def test_a_price_gap_on_the_delivery_note_is_caught():
    r = compare_reception([ordered("l1", 10, price=18.5)], [got("l1", 10, price=21.0)])
    assert "price" in r["lines"][0]["anomalies"]


def test_a_rounding_difference_is_not_a_price_gap():
    r = compare_reception([ordered("l1", 10, price=18.5)], [got("l1", 10, price=18.502)])
    assert "price" not in r["lines"][0]["anomalies"]


def test_a_packaging_gap_is_caught():
    """10 sacs de 10 kg au lieu de 10 sacs de 25 kg : même compte, 150 kg de
    moins."""
    r = compare_reception(
        [ordered("l1", 10, pack="sac 25kg")], [got("l1", 10, pack="sac 10kg")]
    )
    assert "pack_size" in r["lines"][0]["anomalies"]


def test_the_same_packaging_written_differently_is_not_a_gap():
    r = compare_reception(
        [ordered("l1", 10, pack="Sac 25kg")], [got("l1", 10, pack="  sac 25KG ")]
    )
    assert "pack_size" not in r["lines"][0]["anomalies"]


def test_an_unknown_packaging_on_one_side_accuses_nobody():
    r = compare_reception([ordered("l1", 10, pack="sac 25kg")], [got("l1", 10)])
    assert "pack_size" not in r["lines"][0]["anomalies"]


def test_a_delivery_by_another_supplier_is_flagged_on_the_document():
    r = compare_reception(
        [ordered("l1", 10)], [got("l1", 10)],
        order_supplier_id="METRO", receipt_supplier_id="AUTRE",
    )
    assert "supplier" in r["document_anomalies"]


def test_the_expected_supplier_raises_no_flag():
    r = compare_reception(
        [ordered("l1", 10)], [got("l1", 10)],
        order_supplier_id="METRO", receipt_supplier_id="METRO",
    )
    assert r["document_anomalies"] == []


def test_a_substitution_is_reported_as_a_product_gap():
    r = compare_reception(
        [ordered("l1", 10)], [got("l1", 10, substituted_product_id="autre")]
    )
    assert "product" in r["lines"][0]["anomalies"]


# --- hors commande --------------------------------------------------------
def test_a_product_delivered_outside_the_order_is_kept_and_flagged():
    r = compare_reception(
        [ordered("l1", 10)],
        [got("l1", 10), {"order_line_id": None, "description": "Crème", "qty_delivered": 3}],
    )
    extra = [l for l in r["lines"] if l["status"] == "extra"][0]
    assert extra["description"] == "Crème"
    assert extra["anomalies"] == ["unordered"]
    # Le surplus n'enlève rien à ce qui était dû.
    assert r["is_complete"] is True


def test_a_delivery_with_no_order_at_all_is_all_extra():
    r = compare_reception(
        [], [{"order_line_id": None, "description": "Crème", "qty_delivered": 3}]
    )
    assert r["extra_count"] == 1
    assert r["is_complete"] is False


# --- robustesse -----------------------------------------------------------
def test_an_over_delivery_owes_nothing():
    r = compare_reception([ordered("l1", 10)], [got("l1", 12)])
    assert r["lines"][0]["status"] == "over"
    assert r["lines"][0]["missing_value"] == 0.0


def test_rounding_noise_is_not_a_shortage():
    r = compare_reception([ordered("l1", 10)], [got("l1", 9.9999)])
    assert r["lines"][0]["status"] == "ok"


@pytest.mark.parametrize("qty", [0, None])
def test_a_line_ordered_without_quantity_never_holds_the_order_open(qty):
    """Rien n'était dû. La laisser « en attente » empêcherait la commande de se
    clore, définitivement."""
    r = compare_reception([ordered("l1", qty)], [])
    assert r["lines"][0]["status"] == "ok"
    assert r["is_complete"] is True


def test_two_partial_deliveries_of_one_line_add_up_within_a_receipt():
    r = compare_reception([ordered("l1", 10)], [got("l1", 4), got("l1", 6)])
    assert r["lines"][0]["qty_received_total"] == 10


def test_the_public_helper_is_the_one_endpoints_use():
    """Régression : le pré-remplissage appelait une fonction privée en passant
    une chaîne vide comme identifiant à exclure. Comparer un UUID à '' fait
    échouer Postgres à l'exécution — invisible hors base."""
    import inspect

    from app.services.purchasing import reception_service as rs

    assert hasattr(rs, "received_by_order_line")
    assert not hasattr(rs, "_received_before")
    sig = inspect.signature(rs.received_by_order_line)
    assert sig.parameters["exclude_receipt_id"].default is None
