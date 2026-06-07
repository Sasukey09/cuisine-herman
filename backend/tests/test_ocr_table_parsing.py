from app.services.ocr.service import to_number, lines_from_tables, extract_products
from app.services.ocr.schemas import OcrTable


def test_to_number_tolerant():
    assert to_number("6,00") == 6.0
    assert to_number("1 234,56") == 1234.56
    assert to_number("1,234.56") == 1234.56
    assert to_number("€6.00") == 6.0
    assert to_number("12,50 €") == 12.50
    assert to_number("") is None
    assert to_number(None) is None
    assert to_number("abc") is None


def test_table_with_french_header_and_commas():
    table = OcrTable(rows=[
        ["Désignation", "Quantité", "Unité", "Prix unitaire", "Montant"],
        ["Tomates", "2", "kg", "3,50", "7,00"],
        ["Farine T55", "10", "kg", "1,20", "12,00"],
        ["Total", "", "", "", "19,00"],  # should be skipped
    ])
    lines = lines_from_tables([table])
    assert len(lines) == 2
    assert lines[0].description == "Tomates"
    assert lines[0].qty == 2
    assert lines[0].unit == "kg"
    assert lines[0].unit_price == 3.5
    assert lines[0].line_total == 7.0


def test_derives_unit_price_from_total_and_qty():
    table = OcrTable(rows=[
        ["Produit", "Qté", "Total"],
        ["Beurre", "4", "32,00"],  # no unit price column -> derive 8.0
    ])
    lines = lines_from_tables([table])
    assert len(lines) == 1
    assert lines[0].unit_price == 8.0
    assert lines[0].line_total == 32.0


def test_service_invoice_trailing_euro_amounts():
    text = "\n".join([
        "OFFRE 48,98 €",
        "beIN SPORTS 01/01/2026 - 31/01/2026 (1 mois) 14,99 €",
        "Option Multi-TV THD 3,00 €",
        "Remise proche -15% -10,04 €",
        "Dont TVA à 20 % 7,36 €",          # skipped (TVA)
        "Montant net à prélever 56,93 €",   # skipped (à prélever)
        "Votre ligne : 09 61 61 39 77",     # skipped (no currency)
    ])
    lines = extract_products(text)
    descs = {l.description: l.line_total for l in lines}
    assert descs.get("OFFRE") == 48.98
    assert descs.get("Option Multi-TV THD") == 3.0
    assert any("Remise" in d for d in descs)
    assert all("TVA" not in d and "prélever" not in d for d in descs)


def test_table_without_header_positional():
    table = OcrTable(rows=[
        ["Oeufs", "6", "0,30", "1,80"],
    ])
    lines = lines_from_tables([table])
    assert len(lines) == 1
    assert lines[0].description == "Oeufs"
    assert lines[0].line_total == 1.8
