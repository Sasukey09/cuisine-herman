from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.services.units.unit_conversion import UnitConversionService, UnitConversionError


def _unit(uid, code, category, ratio):
    return SimpleNamespace(id=uid, code=code, category=category, ratio_to_base=ratio)


# Mirrors the 0002 seed
SEED = [
    _unit(1, "kg", "mass", "1"),
    _unit(2, "g", "mass", "0.001"),
    _unit(3, "L", "volume", "1"),
    _unit(4, "ml", "volume", "0.001"),
    _unit(5, "piece", "count", "1"),
    _unit(6, "portion", "count", "1"),
    _unit(7, "caisse", "count", "12"),
    _unit(8, "carton", "count", "24"),
    _unit(9, "palette", "count", "480"),
]


@pytest.fixture
def svc():
    return UnitConversionService(SEED)


def test_500_g_is_0_5_kg(svc):
    assert svc.convert(500, "g", "kg") == Decimal("0.5")


def test_1000_ml_is_1_L(svc):
    assert svc.convert(1000, "ml", "L") == Decimal("1")


def test_12_pieces_per_caisse(svc):
    assert svc.convert(1, "caisse", "piece") == Decimal("12")
    assert svc.convert(12, "piece", "caisse") == Decimal("1")


def test_same_unit_is_identity(svc):
    assert svc.convert(7, "kg", "kg") == Decimal("7")


def test_kg_to_g(svc):
    assert svc.convert(Decimal("2.5"), "kg", "g") == Decimal("2500")


def test_case_insensitive(svc):
    assert svc.convert(1000, "ML", "l") == Decimal("1")


def test_cross_category_without_pair_raises(svc):
    with pytest.raises(UnitConversionError):
        svc.convert(1, "L", "kg")


def test_cross_category_with_explicit_pair():
    # density: 1 L of this product weighs 0.92 kg
    svc = UnitConversionService(SEED, conversions=[{"from": "L", "to": "kg", "factor": "0.92"}])
    assert svc.convert(2, "L", "kg") == Decimal("1.84")


def test_unknown_unit_raises(svc):
    with pytest.raises(UnitConversionError):
        svc.convert(1, "tonne", "kg")


def test_ratio_map(svc):
    rm = svc.ratio_map()
    assert rm[2] == Decimal("0.001")
    assert rm[7] == Decimal("12")
