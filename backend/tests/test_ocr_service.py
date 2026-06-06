import os
from app.services.ocr.service import normalize_units, extract_products


def test_normalize_units_basic():
    unit, qty = normalize_units('kg', 10)
    assert unit == 'kg'
    assert qty == 10

    unit2, qty2 = normalize_units('g', 1000)
    assert unit2 == 'g'
    assert qty2 == 1.0  # 1000 * 0.001


def test_extract_products_parsing():
    text = "Tomates 10 kg 20.00 200.00\nMozzarella 5 kg 8.00 40.00\n"
    lines = extract_products(text)
    assert len(lines) == 2
    assert lines[0].description.lower().startswith('tomates')
    assert lines[0].qty == 10
    assert lines[0].unit_price == 20.00
