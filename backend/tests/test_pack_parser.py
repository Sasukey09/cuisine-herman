"""Lecture du conditionnement + prix à l'unité de base.

C'est la brique qui rend le comparateur honnête : sans elle, un sac de 25 kg et
une plaquette de 500 g sont comparés sur leur prix affiché, ce qui désigne le
mauvais « moins cher ». Pur : tourne partout."""

import pytest

from app.services.quotes.pack_parser import parse_pack, price_per_base_unit


# --- masse -----------------------------------------------------------------
@pytest.mark.parametrize(
    "text,expected",
    [
        ("Farine T55 sac 25kg", (25.0, "kg")),
        ("sac 25 kg", (25.0, "kg")),
        ("Beurre doux plaquette 500g", (0.5, "kg")),
        ("Poivre 100 grammes", (0.1, "kg")),
        ("Levure 20gr", (0.02, "kg")),
        ("Colorant 500mg", (0.0005, "kg")),
    ],
)
def test_parse_mass(text, expected):
    assert parse_pack(text) == expected


# --- volume ----------------------------------------------------------------
@pytest.mark.parametrize(
    "text,expected",
    [
        ("Huile d'olive bidon 5L", (5.0, "L")),
        ("Vinaigre 75cl", (0.75, "L")),
        ("Crème liquide 1,5 litre", (1.5, "L")),
        ("Arôme 250ml", (0.25, "L")),
    ],
)
def test_parse_volume(text, expected):
    assert parse_pack(text) == expected


# --- multipack : le piège classique ---------------------------------------
def test_multipack_multiplies():
    # « carton de 6x1L » vaut 6 L, surtout pas 1 L.
    assert parse_pack("Lait carton de 6x1L") == (6.0, "L")
    assert parse_pack("Eau 6 x 1,5 L") == (9.0, "L")
    assert parse_pack("Beurre 2x500g") == (1.0, "kg")


# --- refus explicite -------------------------------------------------------
@pytest.mark.parametrize(
    "text",
    ["carton de 6", "Farine T55", "", None, "lot de 3 pièces"],
)
def test_unreadable_pack_returns_none(text):
    # Mieux vaut ne rien affirmer que comparer à tort.
    assert parse_pack(text) is None


def test_number_without_unit_is_not_a_pack():
    assert parse_pack("Filet de boeuf 1er choix") is None


# --- prix à l'unité de base ------------------------------------------------
def test_price_per_kg_from_pack_size():
    # 18,50 € le sac de 25 kg -> 0,74 €/kg
    assert price_per_base_unit(18.50, pack_size="sac 25kg") == (0.74, "kg")


def test_price_per_kg_falls_back_on_description():
    # Les fournisseurs écrivent souvent le conditionnement dans le libellé.
    assert price_per_base_unit(4.20, description="Beurre doux plaquette 500g") == (8.4, "kg")


def test_price_per_base_unit_applies_discount():
    # 20 € le bidon de 5 L, remise 10 % -> 18 € / 5 L = 3,60 €/L
    assert price_per_base_unit(20.0, pack_size="bidon 5L", discount_pct=10) == (3.6, "L")


def test_comparator_ranking_flips_once_normalised():
    """Le cas qui justifie tout ce module : le prix affiché ment."""
    sac = price_per_base_unit(18.50, description="Farine sac 25kg")
    plaquette = price_per_base_unit(4.20, description="Farine plaquette 500g")
    assert sac is not None and plaquette is not None
    # La plaquette est 4x moins chère à l'affichage…
    assert 4.20 < 18.50
    # …mais 11x plus chère au kilo.
    assert sac[0] < plaquette[0]


def test_no_price_or_unreadable_pack_yields_none():
    assert price_per_base_unit(None, pack_size="sac 25kg") is None
    assert price_per_base_unit(10.0, pack_size="carton de 6") is None
    assert price_per_base_unit(10.0) is None
