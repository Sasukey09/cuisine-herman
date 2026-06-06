from datetime import date
from typing import List, Optional

from ..provider import OCRProvider, is_pdf
from ..schemas import OcrResult, OcrTable, InvoiceLineExtraction
from ..errors import OcrConfigurationError, OcrTransientError
from ..config import get_ocr_config


def _text_from_anchor(document, layout) -> str:
    """Resolve a layout's text_anchor into the underlying document text."""
    anchor = getattr(layout, "text_anchor", None)
    if not anchor or not anchor.text_segments:
        return ""
    parts = []
    for seg in anchor.text_segments:
        start = int(seg.start_index or 0)
        end = int(seg.end_index or 0)
        parts.append(document.text[start:end])
    return "".join(parts).strip()


def _to_float(value) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(str(value).replace(",", ".").replace(" ", ""))
    except (TypeError, ValueError):
        return None


class GoogleDocumentAIProvider(OCRProvider):
    """Google Cloud Document AI (Invoice processor) — text, tables and line items."""

    name = "google"

    def is_configured(self) -> bool:
        cfg = get_ocr_config()
        return bool(cfg.gcp_project and cfg.docai_processor_id)

    def extract_document(self, file_bytes: bytes, content_type: Optional[str] = None) -> OcrResult:
        cfg = get_ocr_config()
        if not self.is_configured():
            raise OcrConfigurationError("GCP_PROJECT_ID / DOCAI_PROCESSOR_ID not set")
        try:
            from google.cloud import documentai
            from google.api_core.client_options import ClientOptions
            from google.api_core import exceptions as gexc
        except Exception as exc:  # pragma: no cover
            raise OcrConfigurationError(f"google-cloud-documentai not available: {exc}")

        mime = content_type or ("application/pdf" if is_pdf(file_bytes, content_type) else "image/png")
        opts = ClientOptions(api_endpoint=f"{cfg.docai_location}-documentai.googleapis.com")
        client = documentai.DocumentProcessorServiceClient(client_options=opts)

        if cfg.docai_processor_version:
            name = client.processor_version_path(
                cfg.gcp_project, cfg.docai_location, cfg.docai_processor_id, cfg.docai_processor_version
            )
        else:
            name = client.processor_path(cfg.gcp_project, cfg.docai_location, cfg.docai_processor_id)

        request = documentai.ProcessRequest(
            name=name,
            raw_document=documentai.RawDocument(content=file_bytes, mime_type=mime),
        )

        try:
            result = client.process_document(request=request, timeout=cfg.timeout_seconds)
        except (gexc.Unauthenticated, gexc.PermissionDenied, gexc.InvalidArgument) as exc:
            raise OcrConfigurationError(f"document ai access error: {exc}")
        except (gexc.DeadlineExceeded, gexc.ServiceUnavailable, gexc.ServerError, gexc.RetryError) as exc:
            raise OcrTransientError(f"document ai transient error: {exc}")
        except gexc.GoogleAPICallError as exc:
            raise OcrTransientError(f"document ai error: {exc}")

        document = result.document
        return OcrResult(
            provider=self.name,
            text=document.text or "",
            tables=self._tables(document),
            pages=len(document.pages) or 1,
            lines=self._line_items(document),
            **self._header(document),
        )

    # -- parsing helpers ----------------------------------------------------

    def _tables(self, document) -> List[OcrTable]:
        tables: List[OcrTable] = []
        for page in document.pages:
            for table in getattr(page, "tables", []):
                rows: List[List[str]] = []
                for row in list(table.header_rows) + list(table.body_rows):
                    rows.append([_text_from_anchor(document, c.layout) for c in row.cells])
                if rows:
                    tables.append(OcrTable(rows=rows))
        return tables

    def _header(self, document) -> dict:
        header = {"supplier": None, "invoice_number": None, "date": None, "total_amount": None}
        for ent in document.entities:
            t = ent.type_
            if t == "supplier_name":
                header["supplier"] = ent.mention_text or None
            elif t == "invoice_id":
                header["invoice_number"] = ent.mention_text or None
            elif t == "invoice_date":
                header["date"] = self._entity_date(ent)
            elif t in ("total_amount", "net_amount"):
                header["total_amount"] = self._entity_amount(ent)
        return header

    def _line_items(self, document) -> List[InvoiceLineExtraction]:
        lines: List[InvoiceLineExtraction] = []
        for ent in document.entities:
            if ent.type_ != "line_item":
                continue
            props = {p.type_: p for p in ent.properties}
            desc = props.get("line_item/description")
            lines.append(
                InvoiceLineExtraction(
                    description=(desc.mention_text if desc else ent.mention_text) or "",
                    qty=self._entity_amount(props.get("line_item/quantity")),
                    unit=props["line_item/unit"].mention_text if "line_item/unit" in props else None,
                    unit_normalized=None,
                    unit_price=self._entity_amount(props.get("line_item/unit_price")),
                    line_total=self._entity_amount(props.get("line_item/amount")),
                )
            )
        return lines

    @staticmethod
    def _entity_amount(ent) -> Optional[float]:
        if ent is None:
            return None
        norm = getattr(ent, "normalized_value", None)
        money = getattr(norm, "money_value", None) if norm else None
        if money is not None:
            units = getattr(money, "units", 0) or 0
            nanos = getattr(money, "nanos", 0) or 0
            return float(units) + float(nanos) / 1e9
        if norm and getattr(norm, "text", None):
            return _to_float(norm.text)
        return _to_float(getattr(ent, "mention_text", None))

    @staticmethod
    def _entity_date(ent) -> Optional[date]:
        norm = getattr(ent, "normalized_value", None)
        dv = getattr(norm, "date_value", None) if norm else None
        if dv and dv.year and dv.month and dv.day:
            try:
                return date(dv.year, dv.month, dv.day)
            except ValueError:
                return None
        return None
