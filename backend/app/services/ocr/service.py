import re
from datetime import datetime
from typing import List, Optional, Tuple

from .orchestrator import run_ocr
from .schemas import InvoiceExtractionResult, InvoiceLineExtraction, OcrResult


def extract_text(file_bytes: bytes, content_type: Optional[str] = None) -> str:
    """Run the OCR chain and return concatenated text."""
    return run_ocr(file_bytes, content_type).text


def extract_products(text: str) -> List[InvoiceLineExtraction]:
    """Parse product lines from OCR text using regex heuristics."""
    lines = []
    for raw in text.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        m = re.search(
            r"^(?P<desc>[A-Za-z0-9 \-]+)\s+(?P<qty>[0-9]+(?:\.[0-9]+)?)\s*(?P<unit>[a-zA-Z]+)\s+(?P<unit_price>[0-9]+(?:\.[0-9]+)?)\s*[A-Za-z€$]*\s*(?P<total>[0-9]+(?:\.[0-9]+)?)$",
            raw,
        )
        if m:
            desc = m.group('desc').strip()
            qty = float(m.group('qty'))
            unit = m.group('unit')
            unit_price = float(m.group('unit_price'))
            total = float(m.group('total'))
            unit_norm, _ = normalize_units(unit, qty)
            lines.append(InvoiceLineExtraction(description=desc, qty=qty, unit=unit, unit_normalized=unit_norm, unit_price=unit_price, line_total=total))
            continue

        m2 = re.search(
            r"^(?P<desc>.+?)\s+(?P<qty>[0-9]+(?:\.[0-9]+)?)\s*(?P<unit>[a-zA-Z]+)\s+(?P<unit_price>[0-9]+(?:\.[0-9]+)?)$",
            raw,
        )
        if m2:
            desc = m2.group('desc').strip()
            qty = float(m2.group('qty'))
            unit = m2.group('unit')
            unit_price = float(m2.group('unit_price'))
            unit_norm, _ = normalize_units(unit, qty)
            lines.append(InvoiceLineExtraction(description=desc, qty=qty, unit=unit, unit_normalized=unit_norm, unit_price=unit_price, line_total=None))
            continue

        if any(k.lower() in raw.lower() for k in ("fournisseur", "supplier", "date", "facture", "invoice")):
            continue

    return lines


def normalize_units(unit: Optional[str], qty: Optional[float] = None) -> Tuple[Optional[str], Optional[float]]:
    """Normalize unit strings to canonical units and optionally convert quantity."""
    if not unit:
        return None, qty
    u = unit.strip().lower()
    mapping = {
        'kg': ('kg', 1),
        'g': ('g', 0.001),
        'gram': ('g', 0.001),
        'l': ('l', 1),
        'ml': ('ml', 0.001),
        'pcs': ('pcs', 1),
        'pc': ('pcs', 1),
        'piece': ('pcs', 1),
    }
    if u in mapping:
        norm, factor = mapping[u]
        return (norm, qty * factor) if qty is not None else (norm, qty)
    if u.endswith('s') and u[:-1] in mapping:
        norm, factor = mapping[u[:-1]]
        return (norm, qty * factor) if qty is not None else (norm, qty)
    return unit.upper(), qty


def _parse_header(text: str):
    supplier = invoice_date = invoice_number = None

    m_sup = re.search(r"(?:Fournisseur|Supplier)[:\s]+(.+)", text, re.IGNORECASE)
    if m_sup:
        supplier = m_sup.group(1).strip()

    m_date = re.search(
        r"Date[:\s]+([0-9]{4}-[0-9]{2}-[0-9]{2}|[0-9]{4}/[0-9]{2}/[0-9]{2}|[0-9]{2}/[0-9]{2}/[0-9]{4})",
        text,
    )
    if m_date:
        for fmt in ("fromiso", "%d/%m/%Y", "%Y/%m/%d"):
            try:
                if fmt == "fromiso":
                    invoice_date = datetime.fromisoformat(m_date.group(1)).date()
                else:
                    invoice_date = datetime.strptime(m_date.group(1), fmt).date()
                break
            except ValueError:
                invoice_date = None

    m_inv = re.search(r"(?:Facture|Invoice)[:\s]*([A-Z0-9\-]+)", text, re.IGNORECASE)
    if m_inv:
        invoice_number = m_inv.group(1).strip()

    return supplier, invoice_date, invoice_number


def _result_from_ocr(ocr: OcrResult) -> InvoiceExtractionResult:
    # Prefer the provider's structured line items (e.g. Document AI invoice parser).
    if ocr.lines:
        return InvoiceExtractionResult(
            supplier=ocr.supplier,
            date=ocr.date,
            invoice_number=ocr.invoice_number,
            lines=ocr.lines,
            raw_text=ocr.text,
        )

    # Otherwise fall back to regex heuristics over the raw text.
    text = ocr.text or ""
    supplier, invoice_date, invoice_number = _parse_header(text)
    return InvoiceExtractionResult(
        supplier=ocr.supplier or supplier,
        date=ocr.date or invoice_date,
        invoice_number=ocr.invoice_number or invoice_number,
        lines=extract_products(text),
        raw_text=text,
    )


def extract_invoice(file, content_type: Optional[str] = None) -> InvoiceExtractionResult:
    """Extract structured invoice data from a file-like object or raw bytes."""
    file_bytes = file.read() if hasattr(file, "read") else file
    ocr = run_ocr(file_bytes, content_type)
    return _result_from_ocr(ocr)
