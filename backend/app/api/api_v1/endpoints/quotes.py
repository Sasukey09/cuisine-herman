"""Quote comparator (#1) — REST surface.

A quote is a named basket of products; ``GET /quotes/{id}/comparison`` prices it
across suppliers and ``POST /quotes/{id}/order`` converts the retained supplier's
offer into an order. See ``app.services.quotes.quote_service``.
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core.uploads import validate_upload
from app.db.session import get_db
from app.api.deps import get_current_tenant_id, require_writer, quota, daily_quota
from app.schemas.schemas import (
    QuoteCreate,
    QuoteUpdate,
    QuoteRead,
    QuoteLineCreate,
    QuoteLineUpdate,
    QuoteOrderRequest,
    QuotePreviewLine,
    QuotePreviewResult,
    QuoteConfirmRequest,
    QuoteImportResult,
)
from app.crud import crud_quote, crud_product, crud_supplier
from app.services.quotes import quote_service, quote_import, quote_matrix
# --- Pipeline PARTAGE avec les factures (jamais duplique) ------------------
from app.services.ocr.service import extract_invoice
from app.services.ocr.errors import OcrError
from app.services.ocr.http_errors import ocr_http_error
from app.services.matching.product_matcher import match_product
from app.services.classification.classifier import classify

router = APIRouter()


def _detail(db: Session, tenant_id: str, quote) -> dict:
    supplier_names = crud_quote._supplier_names(db, tenant_id)
    line_counts = crud_quote._line_counts(db, tenant_id)
    data = crud_quote.to_read(quote, supplier_names, line_counts)
    data["lines"] = crud_quote.lines_read(db, tenant_id, str(quote.id))
    return data


@router.get("/", response_model=List[QuoteRead])
def api_list_quotes(
    status: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
):
    return crud_quote.list_read(db, tenant_id, status)


@router.post("/", status_code=201)
def api_create_quote(
    payload: QuoteCreate,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    _: list = Depends(require_writer),
):
    quote = crud_quote.create_quote(db, tenant_id, payload)
    return _detail(db, tenant_id, quote)


# ⚠ DOIT rester déclarée AVANT `GET /{quote_id}` : FastAPI résout les routes
# dans l'ordre, donc placée après, « /quotes/matrix » serait capturée par
# `/{quote_id}` avec quote_id="matrix" — Postgres reçoit alors « matrix » comme
# UUID et l'appel finit en 500 (constaté en production).
@router.get("/matrix")
def api_quote_matrix(
    status: str = Query("draft", description="Statut des devis à comparer"),
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Tableau comparatif multi-devis : une ligne = un produit, une colonne = un
    fournisseur (§7).

    Chaque offre porte son prix affiché, son **prix à l'unité de base** (le seul
    comparable entre conditionnements différents), TVA, remise, délai, dispo,
    validité, son rang (best / mid / worst) et l'écart % avec la meilleure.
    Voir `quote_matrix.build_matrix` pour les garde-fous (conditionnement
    illisible, offre périmée)."""
    return quote_matrix.build_for_tenant(db, tenant_id, statuses=(status,))


@router.get("/{quote_id}")
def api_get_quote(
    quote_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
):
    quote = crud_quote.get_quote(db, tenant_id, quote_id)
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    return _detail(db, tenant_id, quote)


@router.patch("/{quote_id}")
def api_update_quote(
    quote_id: str,
    payload: QuoteUpdate,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    _: list = Depends(require_writer),
):
    quote = crud_quote.get_quote(db, tenant_id, quote_id)
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    crud_quote.update_quote(db, quote, payload)
    return _detail(db, tenant_id, quote)


@router.delete("/{quote_id}", status_code=204)
def api_delete_quote(
    quote_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    _: list = Depends(require_writer),
):
    quote = crud_quote.get_quote(db, tenant_id, quote_id)
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    crud_quote.delete_quote(db, quote)
    return None


@router.get("/{quote_id}/comparison")
def api_quote_comparison(
    quote_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Price the basket across suppliers: per-supplier total, coverage, lead time,
    cheapest + best-coverage flags."""
    quote = crud_quote.get_quote(db, tenant_id, quote_id)
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    lines = crud_quote.get_lines(db, tenant_id, quote_id)
    return quote_service.comparison(db, tenant_id, quote, lines)


@router.post("/{quote_id}/order")
def api_order_quote(
    quote_id: str,
    payload: QuoteOrderRequest,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    _: list = Depends(require_writer),
):
    """Convert the quote into an order for the chosen supplier, snapshotting its
    prices onto the lines and the total onto the quote."""
    quote = crud_quote.get_quote(db, tenant_id, quote_id)
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    lines = crud_quote.get_lines(db, tenant_id, quote_id)
    totals = quote_service.supplier_totals(db, tenant_id, lines, payload.supplier_id)
    cost_by_product = {
        l["product_id"]: l["unit_cost"]
        for l in totals["lines"]
        if l.get("product_id")
    }
    crud_quote.mark_ordered(
        db, quote, payload.supplier_id, totals["total"], cost_by_product
    )
    return _detail(db, tenant_id, quote)


# --- lines ---------------------------------------------------------------- #


@router.post("/{quote_id}/lines", status_code=201)
def api_add_line(
    quote_id: str,
    payload: QuoteLineCreate,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    _: list = Depends(require_writer),
):
    quote = crud_quote.get_quote(db, tenant_id, quote_id)
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    crud_quote.add_line(db, tenant_id, quote_id, payload)
    return _detail(db, tenant_id, quote)


@router.patch("/{quote_id}/lines/{line_id}")
def api_update_line(
    quote_id: str,
    line_id: str,
    payload: QuoteLineUpdate,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    _: list = Depends(require_writer),
):
    line = crud_quote.get_line(db, tenant_id, quote_id, line_id)
    if not line:
        raise HTTPException(status_code=404, detail="Line not found")
    crud_quote.update_line(db, line, payload)
    quote = crud_quote.get_quote(db, tenant_id, quote_id)
    return _detail(db, tenant_id, quote)


@router.delete("/{quote_id}/lines/{line_id}")
def api_delete_line(
    quote_id: str,
    line_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    _: list = Depends(require_writer),
):
    line = crud_quote.get_line(db, tenant_id, quote_id, line_id)
    if not line:
        raise HTTPException(status_code=404, detail="Line not found")
    crud_quote.delete_line(db, line)
    quote = crud_quote.get_quote(db, tenant_id, quote_id)
    return _detail(db, tenant_id, quote)


# --- Import de devis (OCR) ------------------------------------------------- #
# Strictement le pipeline des factures : validate_upload -> extract_invoice ->
# match_product + classify. Rien n'est redéveloppé ici ; seul l'en-tête propre
# au devis (validité / remise / conditions) est enrichi par `quote_import`.


@router.post("/preview", response_model=QuotePreviewResult)
async def api_preview_quote(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    _: list = Depends(require_writer),
    _q: None = Depends(quota("ocr", "OCR_PER_MIN", 20)),
    _qd: None = Depends(daily_quota("ocr", "OCR_PER_DAY", 400)),
):
    """Aperçu d'import : OCR + suggestion produit + suggestion de catégorie par
    ligne, pour le dialogue de validation. **Ne persiste rien** (le fournisseur
    détecté est résolu s'il existe, jamais créé ici)."""
    content = await file.read()
    validate_upload(content, file.content_type)
    ctype = file.content_type

    def _work():
        try:
            extraction = extract_invoice(content, ctype)
        except OcrError as exc:
            raise ocr_http_error(exc, "devis")

        supplier_id = None
        if extraction.supplier:
            existing = crud_supplier.get_supplier_by_name(db, tenant_id, extraction.supplier)
            supplier_id = str(existing.id) if existing is not None else None

        header = quote_import.enrich_header(extraction.raw_text or "", extraction.date)

        lines: List[QuotePreviewLine] = []
        for raw in extraction.lines:
            desc = raw.description or ""
            m = (
                match_product(db, tenant_id, desc)
                if desc
                else {"product_id": None, "confidence_score": None, "manual_review": True}
            )
            pid = m.get("product_id")
            pname = None
            if pid:
                p = crud_product.get_product(db, pid, tenant_id)
                pname = p.name if p is not None else None
            lines.append(
                QuotePreviewLine(
                    description=desc,
                    qty=raw.qty,
                    unit=raw.unit,
                    unit_price=raw.unit_price,
                    line_total=raw.line_total,
                    matched_product_id=pid,
                    matched_product_name=pname,
                    match_confidence=m.get("confidence_score"),
                    needs_review=bool(m.get("manual_review", True)) or not pid,
                    suggested_category=classify(desc) if desc else None,
                )
            )

        return QuotePreviewResult(
            supplier=extraction.supplier,
            supplier_id=supplier_id,
            date=extraction.date,
            valid_until=header["valid_until"],
            # Sur un devis, le "numéro de facture" extrait EST le numéro du devis.
            quote_number=extraction.invoice_number,
            total_amount=getattr(extraction, "total_amount", None),
            discount_total=header["discount_total"],
            conditions=header["conditions"],
            lines=lines,
        )

    return await run_in_threadpool(_work)


@router.post("/confirm", response_model=QuoteImportResult, status_code=201)
def api_confirm_quote(
    payload: QuoteConfirmRequest,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    _: list = Depends(require_writer),
):
    """Persiste un import de devis validé : crée le devis puis, par ligne, crée
    un produit (auto-classé + TVA) / associe un existant / ignore.

    Volontairement **sans** `reprice_line` : un devis est une OFFRE, pas un
    achat. Voir `quote_import.confirm_import`, qui porte la logique (testable
    contre un vrai Postgres et réutilisable).
    """
    return QuoteImportResult(**quote_import.confirm_import(db, tenant_id, payload))
