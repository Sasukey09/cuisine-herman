import base64
from typing import List, Optional

from ..provider import OCRProvider, is_pdf
from ..schemas import OcrResult, OcrTable
from ..errors import OcrConfigurationError, OcrTransientError
from ..config import get_ocr_config


def _parse_markdown_tables(markdown: str) -> List[OcrTable]:
    """Extract GitHub-flavoured markdown tables (| a | b |) into OcrTable rows."""
    tables: List[OcrTable] = []
    rows: List[List[str]] = []
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            # skip the markdown separator row (---|---)
            if all(set(c) <= {"-", ":", " "} and c for c in cells):
                continue
            rows.append(cells)
        elif rows:
            tables.append(OcrTable(rows=rows))
            rows = []
    if rows:
        tables.append(OcrTable(rows=rows))
    return tables


class MistralOCRProvider(OCRProvider):
    """Mistral OCR via the hosted REST API.

    Sends the document (PDF or image) as a base64 data URL and concatenates the
    per-page markdown returned by the API.
    """

    name = "mistral"

    def is_configured(self) -> bool:
        return bool(get_ocr_config().mistral_api_key)

    def extract_document(self, file_bytes: bytes, content_type: Optional[str] = None) -> OcrResult:
        cfg = get_ocr_config()
        if not cfg.mistral_api_key:
            raise OcrConfigurationError("MISTRAL_API_KEY is not set")
        try:
            import httpx
        except Exception as exc:  # pragma: no cover
            raise OcrConfigurationError(f"httpx not available: {exc}")

        b64 = base64.b64encode(file_bytes).decode("ascii")
        if is_pdf(file_bytes, content_type):
            document = {
                "type": "document_url",
                "document_url": f"data:application/pdf;base64,{b64}",
            }
        else:
            mime = content_type or "image/png"
            document = {"type": "image_url", "image_url": f"data:{mime};base64,{b64}"}

        payload = {
            "model": cfg.mistral_model,
            "document": document,
            "include_image_base64": False,
        }
        headers = {
            "Authorization": f"Bearer {cfg.mistral_api_key}",
            "Content-Type": "application/json",
        }

        try:
            resp = httpx.post(
                cfg.mistral_url, json=payload, headers=headers, timeout=cfg.timeout_seconds
            )
        except httpx.HTTPError as exc:
            raise OcrTransientError(f"mistral request error: {exc}")

        if resp.status_code in (408, 429) or resp.status_code >= 500:
            raise OcrTransientError(f"mistral HTTP {resp.status_code}")
        if resp.status_code >= 400:
            # 4xx other than rate-limit: bad request/auth -> let the chain fall back
            raise OcrTransientError(f"mistral HTTP {resp.status_code}: {resp.text[:200]}")

        data = resp.json()
        pages = data.get("pages", []) or []
        markdown = "\n\n".join(p.get("markdown", "") for p in pages)
        tables = _parse_markdown_tables(markdown)
        return OcrResult(
            provider=self.name,
            text=markdown,
            tables=tables,
            pages=len(pages) or 1,
        )
