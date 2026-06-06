from typing import Optional

from ..provider import OCRProvider
from ..schemas import OcrResult

SAMPLE_TEXT = (
    "Fournisseur: March\n"
    "Date: 2026-06-01\n"
    "Facture: INV-2026-001\n"
    "\n"
    "Tomates 10 kg 20.00 EUR 200.00\n"
    "Mozzarella 5 kg 8.00 EUR 40.00\n"
    "Olive oil 2 L 10.00 EUR 20.00\n"
)


class StubOCRProvider(OCRProvider):
    """Deterministic local provider used when no real OCR backend is configured.

    Returns text only; the service parses lines via regex heuristics. Disable in
    production by setting OCR_ALLOW_STUB_FALLBACK=false.
    """

    name = "stub"

    def is_configured(self) -> bool:
        return True

    def extract_document(self, file_bytes: bytes, content_type: Optional[str] = None) -> OcrResult:
        return OcrResult(provider=self.name, text=SAMPLE_TEXT, pages=1)
