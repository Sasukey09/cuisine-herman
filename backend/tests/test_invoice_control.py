"""Contrôle facture : commandé → livré → facturé.

Pur : tourne sans base. Le rattachement et le round-trip contre un vrai Postgres
sont dans ``test_invoice_control_real_db.py``.
"""

from app.services.purchasing.invoice_control import (
    BILLED_NOT_RECEIVED,
    EXTRA,
    MISSING,
    NOT_RECEIVED,
    OVER_BILLED,
    PRICE_DOWN,
    PRICE_UP,
    QTY_DIFF,
    VAT_DIFF,
    compare_control,
)


def ordered(pid, qty, price, vat=None):
    return {
        "product_id": pid,
        "description": pid,
        "qty_ordered": qty,
        "unit_price": price,
        "vat_rate": vat,
    }


def billed(pid, qty, price, vat=None, total=None):
    return {
        "product_id": pid,
        "description": pid,
        "qty": qty,
        "unit_price": price,
        "vat_rate": vat,
        "line_total": total,
    }


def line_for(report, pid):
    return next(l for l in report["lines"] if l["product_id"] == pid)


# --- le cas conforme ------------------------------------------------------
def test_a_faithful_invoice_is_conform():
    r = compare_control(
        [ordered("farine", 10, 18.5)],
        {"farine": 10},
        [billed("farine", 10, 18.5)],
    )
    assert r["is_conform"] is True
    assert r["issue_count"] == 0
    assert line_for(r, "farine")["status"] == "ok"


# --- l'anomalie que la Phase 4 existe pour attraper -----------------------
def test_being_billed_for_goods_never_received():
    """Le cas le plus grave : on nous facture 10, rien n'est entré. La colonne
    « livré » est ce qui rend ça visible — un rapprochement au devis seul ne
    l'aurait jamais vu."""
    r = compare_control(
        [ordered("farine", 10, 18.5)],
        {"farine": 0},  # rien de reçu
        [billed("farine", 10, 18.5)],
    )
    line = line_for(r, "farine")
    assert BILLED_NOT_RECEIVED in line["flags"]
    assert line["status"] == BILLED_NOT_RECEIVED
    assert r["billed_not_received_count"] == 1
    assert r["is_conform"] is False


def test_being_billed_more_than_received():
    """Reçu 6, facturé 10 : on paie 4 de trop."""
    r = compare_control(
        [ordered("farine", 10, 18.5)],
        {"farine": 6},
        [billed("farine", 10, 18.5)],
    )
    line = line_for(r, "farine")
    assert OVER_BILLED in line["flags"]
    assert r["billed_not_received_count"] == 1


def test_billed_matches_received_even_if_below_order():
    """Commandé 10, reçu 6 (partiel), facturé 6 : la facture est fidèle à la
    livraison. Ce n'est pas une anomalie de facturation — le manquant est un
    sujet de commande, pas de facture."""
    r = compare_control(
        [ordered("farine", 10, 18.5)],
        {"farine": 6},
        [billed("farine", 6, 18.5)],
    )
    line = line_for(r, "farine")
    assert line["status"] == "ok"
    assert not line["flags"]


# --- écarts de prix, TVA, quantité ----------------------------------------
def test_a_price_rise_is_flagged_with_its_delta():
    r = compare_control(
        [ordered("farine", 10, 18.5)], {"farine": 10}, [billed("farine", 10, 21.0)]
    )
    line = line_for(r, "farine")
    assert PRICE_UP in line["flags"]
    assert line["price_delta"] == 2.5
    assert line["total_delta"] == 25.0


def test_a_price_drop_is_flagged_too():
    r = compare_control(
        [ordered("farine", 10, 18.5)], {"farine": 10}, [billed("farine", 10, 17.0)]
    )
    assert PRICE_DOWN in line_for(r, "farine")["flags"]


def test_a_rounding_difference_is_not_a_price_gap():
    r = compare_control(
        [ordered("farine", 10, 18.5)], {"farine": 10}, [billed("farine", 10, 18.502)]
    )
    assert line_for(r, "farine")["status"] == "ok"


def test_a_vat_difference_is_flagged():
    r = compare_control(
        [ordered("farine", 10, 18.5, vat=5.5)],
        {"farine": 10},
        [billed("farine", 10, 18.5, vat=20.0)],
    )
    assert VAT_DIFF in line_for(r, "farine")["flags"]


def test_a_quantity_billed_different_from_received():
    """Reçu 10, facturé 12 (sur une commande de 12) : sur-facturation."""
    r = compare_control(
        [ordered("farine", 12, 18.5)],
        {"farine": 10},
        [billed("farine", 12, 18.5)],
    )
    line = line_for(r, "farine")
    # Facturé 12 pour 10 reçus : c'est de la sur-facturation, pas un simple écart.
    assert OVER_BILLED in line["flags"]


def test_billed_below_received_is_a_plain_qty_diff():
    """Reçu 10, facturé 8 : en notre faveur, mais signalé quand même."""
    r = compare_control(
        [ordered("farine", 10, 18.5)],
        {"farine": 10},
        [billed("farine", 8, 18.5)],
    )
    assert QTY_DIFF in line_for(r, "farine")["flags"]


# --- présence / absence ---------------------------------------------------
def test_a_product_billed_but_not_ordered_is_extra():
    r = compare_control([], {}, [billed("mystere", 3, 9.9)])
    line = line_for(r, "mystere")
    assert line["status"] == EXTRA
    assert line["ordered"] is None


def test_an_ordered_line_not_yet_received_nor_billed_is_pending():
    r = compare_control([ordered("farine", 10, 18.5)], {"farine": 0}, [])
    assert line_for(r, "farine")["status"] == NOT_RECEIVED


def test_a_received_line_not_yet_billed_is_missing_from_the_invoice():
    """Reçu mais pas facturé : à réclamer, ou avoir à venir."""
    r = compare_control([ordered("farine", 10, 18.5)], {"farine": 10}, [])
    assert line_for(r, "farine")["status"] == MISSING


# --- rapprochement par description quand le produit manque ----------------
def test_lines_match_on_normalized_description_without_a_product_id():
    r = compare_control(
        [{"description": "Farine T55", "qty_ordered": 10, "unit_price": 18.5}],
        {},
        [{"description": "  farine  t55 ", "qty": 10, "unit_price": 21.0}],
    )
    # Une seule ligne rapprochée, pas deux (un « commandé » + un « facturé »).
    assert len(r["lines"]) == 1
    assert PRICE_UP in r["lines"][0]["flags"]


# --- priorité des drapeaux ------------------------------------------------
def test_the_gravest_flag_becomes_the_status():
    """Prix en hausse ET facturé non reçu : c'est le second qu'on montre."""
    r = compare_control(
        [ordered("farine", 10, 18.5)],
        {"farine": 0},
        [billed("farine", 10, 21.0)],
    )
    line = line_for(r, "farine")
    assert PRICE_UP in line["flags"]
    assert BILLED_NOT_RECEIVED in line["flags"]
    assert line["status"] == BILLED_NOT_RECEIVED


def test_problem_lines_come_first():
    r = compare_control(
        [ordered("a", 10, 5.0), ordered("b", 10, 5.0)],
        {"a": 10, "b": 10},
        [billed("a", 10, 5.0), billed("b", 10, 9.0)],  # b en hausse
    )
    assert r["lines"][0]["product_id"] == "b", "la ligne à problème d'abord"


# --- totaux ---------------------------------------------------------------
def test_totals_and_delta():
    r = compare_control(
        [ordered("farine", 10, 18.5), ordered("beurre", 4, 42.0)],
        {"farine": 10, "beurre": 4},
        [billed("farine", 10, 20.0), billed("beurre", 4, 42.0)],
    )
    assert r["ordered_total"] == 353.0  # 185 + 168
    assert r["billed_total"] == 368.0  # 200 + 168
    assert r["total_delta"] == 15.0


def test_an_empty_invoice_against_an_order():
    r = compare_control([ordered("farine", 10, 18.5)], {"farine": 0}, [])
    assert r["is_conform"] is False
    assert r["lines"][0]["status"] == NOT_RECEIVED
