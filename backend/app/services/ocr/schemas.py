from pydantic import BaseModel
from typing import Optional, List
# Import under an alias: a field named ``date`` shadows the ``date`` type in the
# class namespace, which makes some pydantic versions resolve ``Optional[date]``
# to ``Optional[None]`` and reject real dates (HTTP 500 on every dated invoice).
from datetime import date as DateType


class InvoiceLineExtraction(BaseModel):
    description: str
    qty: Optional[float] = None
    unit: Optional[str] = None
    unit_normalized: Optional[str] = None
    unit_price: Optional[float] = None
    line_total: Optional[float] = None


class InvoiceExtractionResult(BaseModel):
    supplier: Optional[str] = None
    date: Optional[DateType] = None
    invoice_number: Optional[str] = None
    total_amount: Optional[float] = None
    lines: List[InvoiceLineExtraction] = []
    raw_text: Optional[str] = None


class OcrTable(BaseModel):
    """A table extracted from the document (header row optional)."""
    rows: List[List[str]] = []


class OcrResult(BaseModel):
    """Raw + structured output returned by an OCR provider.

    ``lines`` / header fields are populated only by providers that do
    structured invoice parsing (e.g. Google Document AI Invoice processor).
    Text-only providers leave them empty and the service falls back to regex
    heuristics over ``text``.
    """
    provider: str
    text: str = ""
    tables: List[OcrTable] = []
    pages: int = 1
    supplier: Optional[str] = None
    invoice_number: Optional[str] = None
    date: Optional[DateType] = None
    total_amount: Optional[float] = None
    lines: List[InvoiceLineExtraction] = []
