"""Rapprochement devis ↔ facture (§9) — le contrôle prévu/facturé.

Pur : tourne partout. C'est la fonction qui dit au restaurateur ce qu'on lui
facture en plus de ce qu'il avait accepté."""

from app.services.quotes.quote_invoice_match import compare_quote_invoice


def q(pid, qty, price, vat=5.5, desc=None):
    return {"product_id": pid, "description": desc, "qty": qty, "unit_price": price, "vat_rate": vat}


def test_conform_invoice_has_no_issue():
    r = compare_quote_invoice(
        [q("p1", 10, 2.0), q("p2", 5, 8.0)],
        [q("p1", 10, 2.0), q("p2", 5, 8.0)],
    )
    assert r["is_conform"] is True
    assert r["issue_count"] == 0
    assert r["total_delta"] == 0.0
    assert {l["status"] for l in r["lines"]} == {"ok"}


def test_price_increase_is_flagged_with_amount_and_pct():
    # devisé 2,00 € — facturé 2,20 € : +10 % et +2,00 € sur 10 unités
    r = compare_quote_invoice([q("p1", 10, 2.0)], [q("p1", 10, 2.20)])
    line = r["lines"][0]
    assert line["status"] == "price_up"
    assert line["price_delta"] == 0.20
    assert line["price_delta_pct"] == 10.0
    assert line["total_delta"] == 2.0
    assert r["is_conform"] is False
    assert r["total_delta"] == 2.0


def test_price_decrease_is_reported_as_favourable():
    r = compare_quote_invoice([q("p1", 10, 2.0)], [q("p1", 10, 1.80)])
    line = r["lines"][0]
    assert line["status"] == "price_down"
    assert line["price_delta"] == -0.20
    assert r["total_delta"] == -2.0  # négatif = favorable


def test_rounding_noise_is_not_an_increase():
    # 2,000 vs 2,004 : arrondi, pas une hausse.
    r = compare_quote_invoice([q("p1", 10, 2.0)], [q("p1", 10, 2.004)])
    assert r["lines"][0]["status"] == "ok"
    assert r["is_conform"] is True


def test_quantity_difference_alone():
    r = compare_quote_invoice([q("p1", 10, 2.0)], [q("p1", 8, 2.0)])
    line = r["lines"][0]
    assert line["status"] == "qty_diff"
    assert line["qty_delta"] == -2
    assert line["total_delta"] == -4.0


def test_line_billed_but_never_quoted_is_extra():
    """Le cas le plus suspect : une ligne qui n'était pas au devis."""
    r = compare_quote_invoice([q("p1", 10, 2.0)], [q("p1", 10, 2.0), q("p9", 3, 12.0)])
    extra = [l for l in r["lines"] if l["status"] == "extra"]
    assert len(extra) == 1
    assert extra[0]["product_id"] == "p9"
    assert extra[0]["quoted"]["unit_price"] is None
    assert r["total_delta"] == 36.0
    assert r["is_conform"] is False


def test_line_quoted_but_not_billed_is_missing():
    r = compare_quote_invoice([q("p1", 10, 2.0), q("p2", 5, 8.0)], [q("p1", 10, 2.0)])
    missing = [l for l in r["lines"] if l["status"] == "missing"]
    assert len(missing) == 1
    assert missing[0]["product_id"] == "p2"
    assert r["total_delta"] == -40.0


def test_vat_mismatch_flagged_even_when_price_conform():
    """Une TVA différente change le montant dû, même à prix HT identique."""
    r = compare_quote_invoice([q("p1", 10, 2.0, vat=5.5)], [q("p1", 10, 2.0, vat=20.0)])
    line = r["lines"][0]
    assert line["status"] == "ok"          # le prix HT est conforme…
    assert line["vat_mismatch"] is True     # …mais la TVA ne l'est pas
    assert r["is_conform"] is False, "un écart de TVA doit sortir du conforme"


def test_matching_falls_back_on_description_when_no_product():
    """Un fournisseur qui réécrit son libellé ne doit pas créer un faux « extra »."""
    r = compare_quote_invoice(
        [{"product_id": None, "description": "Farine T55  25kg", "qty": 2, "unit_price": 18.0}],
        [{"product_id": None, "description": "farine t55 25kg", "qty": 2, "unit_price": 18.0}],
    )
    assert len(r["lines"]) == 1
    assert r["lines"][0]["status"] == "ok"


def test_issues_are_listed_before_conform_lines():
    r = compare_quote_invoice(
        [q("p1", 1, 1.0), q("p2", 1, 1.0)],
        [q("p1", 1, 1.0), q("p2", 1, 2.0)],
    )
    assert r["lines"][0]["status"] == "price_up", "les écarts d'abord"
    assert r["lines"][-1]["status"] == "ok"


def test_totals_and_percentage():
    r = compare_quote_invoice([q("p1", 10, 10.0)], [q("p1", 10, 11.0)])
    assert r["quoted_total"] == 100.0
    assert r["billed_total"] == 110.0
    assert r["total_delta"] == 10.0
    assert r["total_delta_pct"] == 10.0


def test_empty_inputs():
    r = compare_quote_invoice([], [])
    assert r["lines"] == []
    assert r["is_conform"] is True
    assert r["total_delta"] == 0.0
    assert r["total_delta_pct"] is None
