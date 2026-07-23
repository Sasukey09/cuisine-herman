"""Enrichissement d'en-tête propre au devis (validité / remise / conditions).

Pur (texte -> valeurs) : tourne partout. Le round-trip preview/confirm contre un
vrai Postgres est dans ``test_quotes.py``."""

from datetime import date

import pytest

from app.services.quotes.quote_import import (
    enrich_header,
    parse_conditions,
    parse_discount_total,
    parse_valid_until,
)


# --- validité --------------------------------------------------------------
@pytest.mark.parametrize(
    "text,expected",
    [
        ("Offre valable jusqu'au 31/08/2026", date(2026, 8, 31)),
        ("Validité : 15-09-2026", date(2026, 9, 15)),
        ("Devis valide jusqu'au 01.10.26", date(2026, 10, 1)),
    ],
)
def test_valid_until_absolute(text, expected):
    assert parse_valid_until(text) == expected


def test_valid_until_relative_uses_quote_date():
    # "valable 30 jours" n'a de sens que rapporté à la date du devis.
    assert parse_valid_until("Offre valable 30 jours", date(2026, 7, 1)) == date(2026, 7, 31)


def test_valid_until_relative_without_quote_date_is_unknown():
    assert parse_valid_until("Offre valable 30 jours") is None


def test_valid_until_absent():
    assert parse_valid_until("Devis n° 123 — Total 42,00 €") is None


def test_valid_until_ignores_impossible_date():
    assert parse_valid_until("valable jusqu'au 45/13/2026") is None


# --- remise globale --------------------------------------------------------
def test_discount_amount_french_format():
    assert parse_discount_total("Remise commerciale : 12,50 €") == 12.50


def test_discount_with_thousands_separator():
    assert parse_discount_total("Remise exceptionnelle 1 234,56 EUR") == 1234.56


def test_discount_percentage_alone_is_not_an_amount():
    # "Remise 5 %" n'est pas un montant : discount_total doit rester vide.
    assert parse_discount_total("Remise 5 %") is None


def test_discount_absent():
    assert parse_discount_total("Total TTC 90,00 €") is None


# --- conditions ------------------------------------------------------------
def test_conditions_payment():
    text = "Conditions de paiement : 30 jours fin de mois\nAutre ligne"
    assert parse_conditions(text) == "30 jours fin de mois"


def test_conditions_delivery_variant():
    assert parse_conditions("Conditions de livraison - franco de port") == "franco de port"


def test_conditions_absent():
    assert parse_conditions("Devis n° 42") is None


def test_conditions_are_truncated():
    long_tail = "x" * 500
    assert len(parse_conditions(f"Conditions de paiement : {long_tail}") or "") == 300


# --- agrégat ---------------------------------------------------------------
def test_enrich_header_combines_all_three():
    text = (
        "DEVIS n° D-2026-88\n"
        "Offre valable jusqu'au 30/09/2026\n"
        "Remise commerciale : 12,50 €\n"
        "Conditions de paiement : virement à 30 jours\n"
    )
    out = enrich_header(text, date(2026, 7, 1))
    assert out["valid_until"] == date(2026, 9, 30)
    assert out["discount_total"] == 12.50
    assert out["conditions"] == "virement à 30 jours"


def test_enrich_header_on_empty_text_is_all_none():
    assert enrich_header("") == {
        "valid_until": None,
        "discount_total": None,
        "conditions": None,
    }
