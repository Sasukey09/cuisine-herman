import pytest

from app.crud.crud_custom_field import slugify
from app.services.customization.fields_service import _coerce, FieldValueError


def test_slugify():
    assert slugify("Origine du produit") == "origine_du_produit"
    assert slugify("  DLC (jours) !! ") == "dlc_jours"
    assert slugify("Évolution-2024") == "volution_2024"  # non-ascii stripped
    assert slugify("") == "champ"


def test_coerce_number():
    assert _coerce("3.5", "number", [], "x") == 3.5
    assert _coerce(2, "number", [], "x") == 2.0
    assert _coerce("", "number", [], "x") is None
    with pytest.raises(FieldValueError):
        _coerce("abc", "number", [], "x")


def test_coerce_boolean():
    assert _coerce("oui", "boolean", [], "x") is True
    assert _coerce("false", "boolean", [], "x") is False
    assert _coerce(True, "boolean", [], "x") is True


def test_coerce_select_validates_options():
    assert _coerce("France", "select", ["France", "Italie"], "origine") == "France"
    with pytest.raises(FieldValueError):
        _coerce("Espagne", "select", ["France", "Italie"], "origine")


def test_coerce_text_and_none():
    assert _coerce("Bonjour", "text", [], "x") == "Bonjour"
    assert _coerce(None, "text", [], "x") is None
