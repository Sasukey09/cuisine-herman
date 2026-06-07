import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from .orchestrator import run_ocr
from .schemas import InvoiceExtractionResult, InvoiceLineExtraction, OcrResult, OcrTable


def extract_text(file_bytes: bytes, content_type: Optional[str] = None) -> str:
    """Run the OCR chain and return concatenated text."""
    return run_ocr(file_bytes, content_type).text


def to_number(value) -> Optional[float]:
    """Parse a money/quantity token tolerantly: '6,00' '1 234,56' '€6.00' '5'."""
    if value is None:
        return None
    s = re.sub(r"[^\d,.\-]", "", str(value))
    if not s or s in ("-", ".", ","):
        return None
    if "," in s and "." in s:
        # the rightmost separator is the decimal one
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


# header keyword -> canonical column field
_HEADER_KEYWORDS: Dict[str, List[str]] = {
    "description": ["désignation", "designation", "description", "produit", "libellé",
                    "libelle", "article", "intitulé", "intitule", "item"],
    "qty": ["qté", "qte", "quantité", "quantite", "qty", "nb", "nombre"],
    "unit": ["unité", "unite", "unit", "u.", "cond"],
    "unit_price": ["prix unitaire", "p.u", "pu ", "px unit", "prix u", "unit price", "p/u"],
    "total": ["montant", "total", "prix total", "amount", "prix ht", "prix ttc", "prix"],
}

_SKIP_DESC = {"total", "sous-total", "sous total", "tva", "total ht", "total ttc",
              "net à payer", "net a payer", "remise", "montant total"}

# Substrings that mark a summary/tax/total line (not a real article). Kept
# narrow so legitimate "Remise exceptionnelle …" discount lines are preserved.
_SUMMARY_SUBSTRINGS = (
    "sous-total", "sous total", "montant total", "total ht", "total ttc",
    "total à payer", "total a payer", "net à payer", "net a payer",
    "net à prélever", "net a prelever", "montant facturé", "montant facture",
    "à prélever", "a prelever", "dont tva", "dont éco", "dont eco",
    "montant net",
)


def _is_summary(desc: str) -> bool:
    """True for total/tax/summary rows that must not become product lines."""
    d = (desc or "").strip().lower()
    if d in _SKIP_DESC:
        return True
    return any(k in d for k in _SUMMARY_SUBSTRINGS)


def _match_header_field(cell: str) -> Optional[str]:
    c = (cell or "").strip().lower()
    if not c:
        return None
    for field, kws in _HEADER_KEYWORDS.items():
        if any(kw in c for kw in kws):
            return field
    return None


# A cell that is essentially a monetary/numeric amount (optionally a currency
# symbol/word), e.g. "48,98 €", "-10,04 EUR", "3.00". Used to tell amounts apart
# from description cells that merely contain a number (e.g. "Remise proche -15%").
_AMOUNT_RE = re.compile(
    r"^[-+]?[\d][\d ., ]*\s*(?:€|eur(?:os?)?|\$|ht|ttc)?\s*$", re.IGNORECASE
)


def _is_amount_cell(cell: str) -> bool:
    c = (cell or "").strip()
    return bool(c) and to_number(c) is not None and _AMOUNT_RE.match(c) is not None


def _header_columns(row: List[str]) -> Dict[int, str]:
    """Map column index -> field if ``row`` is a genuine column-header row.

    A real header has no monetary amount in it (those are data rows) and must
    expose at least a description column or two recognised columns.
    """
    if any(_is_amount_cell(c) for c in row):
        return {}
    colmap: Dict[int, str] = {}
    for i, cell in enumerate(row):
        field = _match_header_field(cell)
        if field is not None and field not in colmap.values():
            colmap[i] = field
    if "description" in colmap.values() or len(colmap) >= 2:
        return colmap
    return {}


def lines_from_tables(tables: List[OcrTable]) -> List[InvoiceLineExtraction]:
    """Build invoice lines from OCR-extracted tables (e.g. Mistral markdown).

    Uses the column header when there is a real one; otherwise falls back to
    positional heuristics (first text cell = description, monetary cells =
    price/total) — which handles two-column layouts like telecom invoices where
    labels are on the left and amounts aligned far right.
    """
    out: List[InvoiceLineExtraction] = []
    for table in tables:
        rows = [r for r in table.rows if any((c or "").strip() for c in r)]
        if not rows:
            continue

        colmap = _header_columns(rows[0])
        has_header = bool(colmap)
        data_rows = rows[1:] if has_header else rows

        for row in data_rows:
            desc = unit = None
            qty = pu = total = None

            if has_header:
                for i, val in enumerate(row):
                    field = colmap.get(i)
                    if field == "description":
                        desc = (val or "").strip()
                    elif field == "qty":
                        qty = to_number(val)
                    elif field == "unit":
                        unit = (val or "").strip() or None
                    elif field == "unit_price":
                        pu = to_number(val)
                    elif field == "total":
                        total = to_number(val)
            else:
                # description = first cell with letters that isn't itself an amount
                for cell in row:
                    c = (cell or "").strip()
                    if c and re.search(r"[A-Za-zÀ-ÿ]", c) and not _is_amount_cell(c):
                        desc = c
                        break
                nums = [to_number(c) for c in row if _is_amount_cell(c)]
                if nums:
                    total = nums[-1]
                    if len(nums) >= 2:
                        pu = nums[-2]
                    if len(nums) >= 3:
                        qty = nums[-3]

            if not desc or _is_summary(desc):
                continue
            if pu is None and total is None and qty is None:
                continue
            # a single amount on a line is its total (and unit price if no qty)
            if pu is None and total is not None and qty:
                pu = round(total / qty, 4)
            elif pu is None and total is not None and not qty:
                pu = total
            unit_norm, _ = normalize_units(unit, qty)
            out.append(InvoiceLineExtraction(
                description=desc, qty=qty, unit=unit,
                unit_normalized=unit_norm, unit_price=pu, line_total=total,
            ))
    return out


def extract_products(text: str) -> List[InvoiceLineExtraction]:
    """Parse product lines from raw OCR text (fallback when no tables).

    Comma- and dot-decimals are both accepted; the unit price is derived from
    total/qty when missing. Markdown table rows are skipped (handled upstream).
    """
    num = r"[0-9][0-9 .,]*"
    lines: List[InvoiceLineExtraction] = []
    for raw in text.splitlines():
        raw = raw.strip()
        if not raw or raw.startswith("|"):
            continue

        m = re.search(
            rf"^(?P<desc>.+?)\s+(?P<qty>{num})\s*(?P<unit>[a-zA-Zµ]+)\s+"
            rf"(?P<unit_price>{num})\s*[€$A-Za-z]*\s+(?P<total>{num})$",
            raw,
        )
        if not m:
            m = re.search(
                rf"^(?P<desc>.+?)\s+(?P<qty>{num})\s*(?P<unit>[a-zA-Zµ]+)\s+(?P<unit_price>{num})$",
                raw,
            )
        if m:
            desc = m.group("desc").strip()
            qty = to_number(m.group("qty"))
            unit = m.group("unit")
            pu = to_number(m.group("unit_price"))
            total = to_number(m.groupdict().get("total")) if m.groupdict().get("total") else None
            if pu is None and total is not None and qty:
                pu = round(total / qty, 4)
            unit_norm, _ = normalize_units(unit, qty)
            lines.append(InvoiceLineExtraction(
                description=desc, qty=qty, unit=unit,
                unit_normalized=unit_norm, unit_price=pu, line_total=total,
            ))
            continue

        # Fallback: a line ending with a monetary amount + currency symbol
        # (service invoices like "Abonnement … 48,98 €" have no qty/unit columns).
        m3 = re.search(rf"^(?P<desc>.+?)\s+(?P<amount>-?{num})\s*(?:€|eur(?:os?)?|\$)", raw, re.IGNORECASE)
        if m3:
            if not _is_summary(m3.group("desc")) and "total" not in raw.lower():
                desc = m3.group("desc").strip(" :\t-")
                amount = to_number(m3.group("amount"))
                if desc and amount is not None:
                    lines.append(InvoiceLineExtraction(
                        description=desc, qty=None, unit=None, unit_normalized=None,
                        unit_price=amount, line_total=amount,
                    ))
            continue

        if any(k in raw.lower() for k in ("fournisseur", "supplier", "date", "facture", "invoice")):
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
    # Fallback for "FACTURE N° … du 25/01/2026" (no "Date:" label).
    if m_date is None:
        m_date = re.search(r"\bdu\s+([0-9]{2}/[0-9]{2}/[0-9]{4})", text, re.IGNORECASE)
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

    # Invoice number: the captured token must contain a digit, so the bare title
    # "FACTURE" (followed by e.g. "Fournisseur") no longer matches a label word.
    inv_token = r"([A-Za-z0-9][A-Za-z0-9\-/_.]*\d[A-Za-z0-9\-/_.]*)"
    for pat in (
        rf"(?:facture|invoice)\s*(?:n[°ºo.]?)?\s*[:#]?\s*{inv_token}",
        rf"n[°ºo]\s*(?:de\s+facture)?\s*[:#]?\s*{inv_token}",
        rf"(?:réf|ref|réference|reference)\s*[:#]?\s*{inv_token}",
    ):
        m_inv = re.search(pat, text, re.IGNORECASE)
        if m_inv:
            invoice_number = m_inv.group(1).strip(" .:-")
            break

    return supplier, invoice_date, invoice_number


def _parse_total(text: str) -> Optional[float]:
    """Extract the invoice grand total from a total/net-to-pay line.

    Uses a strict money pattern (decimals required, optional 3-digit thousands
    groups) so a date year on the same line — "… le 03/02/2026  56,93 €" — is
    not glued onto the amount.
    """
    amt = r"-?\d{1,3}(?:[  .]\d{3})*[.,]\d{2}"
    keys = (
        "montant net à prélever", "montant net a prelever", "net à payer",
        "net a payer", "total ttc", "montant facturé", "montant facture",
        "total à payer", "total a payer", "montant net",
    )
    cur = r"(?:€|eur(?:os?)?|\$)"
    # whole-euro fallback: no space-thousands (would glue a date year on) and
    # not directly preceded by another digit.
    int_amt = r"(?<!\d)-?\d{1,3}(?:\.\d{3})*"
    for raw in text.splitlines():
        if any(k in raw.lower() for k in keys):
            # prefer a decimal amount before a currency mark; then a whole-euro
            # amount before the currency mark; finally any decimal amount.
            amounts = (
                re.findall(rf"({amt})\s*{cur}", raw, re.IGNORECASE)
                or re.findall(rf"({int_amt})\s*{cur}", raw, re.IGNORECASE)
                or re.findall(amt, raw)
            )
            if amounts:
                val = to_number(amounts[-1])
                if val is not None:
                    return val
    return None


def _result_from_ocr(ocr: OcrResult) -> InvoiceExtractionResult:
    text = ocr.text or ""
    supplier, invoice_date, invoice_number = _parse_header(text)

    # 1) provider-structured lines (e.g. Document AI invoice parser)
    if ocr.lines:
        lines = ocr.lines
    else:
        # 2) tables (Mistral markdown) -> lines ; 3) raw-text regex fallback
        lines = lines_from_tables(ocr.tables) if ocr.tables else []
        if not lines:
            lines = extract_products(text)

    return InvoiceExtractionResult(
        supplier=ocr.supplier or supplier,
        date=ocr.date or invoice_date,
        invoice_number=ocr.invoice_number or invoice_number,
        total_amount=ocr.total_amount or _parse_total(text),
        lines=lines,
        raw_text=text,
    )


def extract_invoice(file, content_type: Optional[str] = None) -> InvoiceExtractionResult:
    """Extract structured invoice data from a file-like object or raw bytes."""
    file_bytes = file.read() if hasattr(file, "read") else file
    ocr = run_ocr(file_bytes, content_type)
    return _result_from_ocr(ocr)
