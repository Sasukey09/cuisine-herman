from typing import List
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, Query
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core.tenancy import assert_product_in_tenant
from app.core.uploads import validate_upload
from app.db.session import get_db
from app.api.deps import get_current_tenant_id, require_writer, quota, daily_quota
from app.schemas.schemas import (
    InvoiceCreateResp,
    InvoiceRead,
    InvoiceLineRead,
    InvoiceProcessSummary,
    InvoiceIngestResult,
    MapProductRequest,
    MapProductResult,
)
from app.crud.crud_invoice import (
    create_invoice_from_upload,
    get_invoice,
    list_invoices,
    set_invoice_file_url,
    set_invoice_ocr_status,
    update_invoice,
)
from app.crud import crud_invoice_line, crud_price, crud_product, crud_supplier
from app.schemas.schemas import (
    InvoiceFileUrl,
    InvoiceQueuedResp,
    InvoiceLineUpdate,
    InvoiceUpdate,
    InvoiceLineCreate,
    CreateProductFromLine,
    ProductCreate,
    ProductRead,
    InvoicePreviewLine,
    InvoicePreviewResult,
    InvoiceConfirmRequest,
)
from app.models.models import Invoice
import uuid as _uuid
from app.services.ocr.service import extract_invoice
from app.services.ocr.schemas import InvoiceExtractionResult
from app.services.matching.product_matcher import match_product
from app.services.classification.classifier import classify
from app.services.ocr.errors import OcrError, AllProvidersFailedError
from app.services.ocr.http_errors import ocr_http_error
from app.services.invoicing import invoice_pricing
from app.services.purchasing import invoice_control, order_service
from app.services.storage import s3_storage

router = APIRouter()


def _tenant_name(db, tenant_id: str):
    """Raison sociale du tenant — sert à ne pas détecter le restaurant comme son
    propre fournisseur quand son nom figure en tête du document."""
    from app.models.models import Organization

    row = db.query(Organization.name).filter(Organization.id == tenant_id).first()
    return row[0] if row else None



def _ocr_http_error(exc: OcrError) -> HTTPException:
    """Délègue au helper partagé (factures + devis) — voir ocr/http_errors.py."""
    return ocr_http_error(exc, "facture")


def _celery_worker_available() -> bool:
    """Is anyone actually consuming the queue?

    On Render's free plan the worker service cannot run at all, so enqueueing
    would strand the invoice in "queued" forever.
    """
    try:
        from app.celery_app import celery_app

        return bool(celery_app.control.ping(timeout=0.5))
    except Exception:
        return False


@router.post("/upload", response_model=InvoiceCreateResp)
async def api_upload_invoice(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    _: list = Depends(require_writer),
    _q: None = Depends(quota("ocr", "OCR_PER_MIN", 20)),
    _qd: None = Depends(daily_quota("ocr", "OCR_PER_DAY", 400)),
):
    content = await file.read()
    validate_upload(content, file.content_type)
    filename, ctype = file.filename, file.content_type

    def _work():
        invoice = create_invoice_from_upload(db, file, tenant_id)
        key = s3_storage.upload_invoice(tenant_id, invoice["id"], filename, content, ctype)
        if key:
            set_invoice_file_url(db, invoice["id"], tenant_id, key)
        return invoice

    # Off the event loop: the storage upload is a blocking network call, and in
    # an `async def` it would freeze every other request served by this worker.
    return await run_in_threadpool(_work)


@router.post("/ingest", response_model=InvoiceIngestResult)
async def api_ingest_invoice(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    _: list = Depends(require_writer),
    _q: None = Depends(quota("ocr", "OCR_PER_MIN", 20)),
    _qd: None = Depends(daily_quota("ocr", "OCR_PER_DAY", 400)),
):
    """Full pipeline: upload -> OCR extract -> persist lines -> auto-match ->
    create price history -> recompute affected recipe costs."""
    content = await file.read()
    validate_upload(content, file.content_type)
    filename, ctype = file.filename, file.content_type

    def _work():
        invoice = create_invoice_from_upload(db, file, tenant_id)
        invoice_id = invoice["id"]
        # persist the original file (non-blocking if storage is unavailable)
        key = s3_storage.upload_invoice(tenant_id, invoice_id, filename, content, ctype)
        if key:
            set_invoice_file_url(db, invoice_id, tenant_id, key)
        try:
            extraction = extract_invoice(content, ctype)
        except OcrError as exc:
            raise _ocr_http_error(exc)
        invoice_pricing.persist_extraction(db, tenant_id, invoice_id, extraction)
        summary = invoice_pricing.process_invoice(db, tenant_id, invoice_id)
        return {"invoice_id": invoice_id, "summary": summary}

    # THE scalability wall this fixes: OCR is a blocking network call of 15-30s.
    # Called straight from an `async def`, it froze the worker's whole event loop
    # — every other tenant's requests on that worker waited for it. With
    # WEB_CONCURRENCY=2, two simultaneous invoice imports stalled the entire API.
    # In a thread, the worker keeps serving everyone else.
    return await run_in_threadpool(_work)


@router.post("/ingest-async", response_model=InvoiceQueuedResp)
async def api_ingest_invoice_async(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    _: list = Depends(require_writer),
    _q: None = Depends(quota("ocr", "OCR_PER_MIN", 20)),
    _qd: None = Depends(daily_quota("ocr", "OCR_PER_DAY", 400)),
):
    """Upload -> store file -> enqueue OCR as a Celery task and return immediately.

    The heavy OCR/parse/recompute runs in the worker; poll GET /invoices/{id}
    (field ``ocr_status``: queued/processing/done/error). Falls back to inline
    processing if storage or the task broker is unavailable.
    """
    content = await file.read()
    validate_upload(content, file.content_type)
    filename, ctype = file.filename, file.content_type

    def _work():
        invoice = create_invoice_from_upload(db, file, tenant_id)
        invoice_id = invoice["id"]
        key = s3_storage.upload_invoice(tenant_id, invoice_id, filename, content, ctype)

        def _process_inline() -> str:
            try:
                extraction = extract_invoice(content, ctype)
            except OcrError as exc:
                set_invoice_ocr_status(db, invoice_id, tenant_id, "error")
                raise _ocr_http_error(exc)
            invoice_pricing.persist_extraction(db, tenant_id, invoice_id, extraction)
            invoice_pricing.process_invoice(db, tenant_id, invoice_id)
            set_invoice_ocr_status(db, invoice_id, tenant_id, "done")
            return "done"

        # No object storage -> the worker can't fetch the file, so process inline.
        if not key:
            return {"invoice_id": invoice_id, "status": _process_inline()}

        set_invoice_file_url(db, invoice_id, tenant_id, key)

        # `.delay()` SUCCEEDS with no worker running — the broker happily accepts
        # the message and nobody ever consumes it. The old try/except therefore
        # guarded nothing, and the invoice stayed "queued" forever, with no
        # timeout and no error the user could see. Ask whether anyone is actually
        # listening before handing the job over.
        if not _celery_worker_available():
            return {"invoice_id": invoice_id, "status": _process_inline()}

        try:
            from app.tasks import process_invoice_ocr

            process_invoice_ocr.delay(invoice_id, tenant_id, key, ctype)
            set_invoice_ocr_status(db, invoice_id, tenant_id, "queued")
            return {"invoice_id": invoice_id, "status": "queued"}
        except Exception:
            # broker unreachable -> degrade gracefully to inline processing
            return {"invoice_id": invoice_id, "status": _process_inline()}

    return await run_in_threadpool(_work)


@router.get("/", response_model=List[InvoiceRead])
def api_list_invoices(
    skip: int = 0,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
):
    return list_invoices(db, tenant_id, skip=skip, limit=limit)


@router.patch("/{invoice_id}", response_model=InvoiceRead)
def api_update_invoice(
    invoice_id: str,
    payload: InvoiceUpdate,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    _: list = Depends(require_writer),
):
    """Edit the invoice header manually (number / date / total / currency)."""
    inv = update_invoice(db, invoice_id, tenant_id, **payload.model_dump(exclude_unset=True))
    if inv is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return inv


@router.delete("/{invoice_id}", status_code=204)
def api_delete_invoice(
    invoice_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    _: list = Depends(require_writer),
):
    """Delete an invoice (and its lines + derived prices), recompute recipes."""
    if not invoice_pricing.delete_invoice(db, tenant_id, invoice_id):
        raise HTTPException(status_code=404, detail="Invoice not found")


@router.post("/{invoice_id}/lines", response_model=InvoiceLineRead, status_code=201)
def api_add_line(
    invoice_id: str,
    payload: InvoiceLineCreate,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    _: list = Depends(require_writer),
):
    """Add a line manually (fallback when OCR missed items)."""
    invoice = get_invoice(db, invoice_id, tenant_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    unit_id = None
    if payload.unit:
        unit_id = crud_price.get_units_by_code(db).get(payload.unit.strip().lower())
    # Client-supplied product id: refuse one owned by another organization.
    assert_product_in_tenant(db, tenant_id, payload.product_id)
    line = crud_invoice_line.create_invoice_line(
        db,
        invoice_id,
        description=payload.description,
        qty=payload.qty,
        unit_id=unit_id,
        unit_price=payload.unit_price,
        line_total=payload.line_total,
        vat_rate=payload.vat_rate,
        product_id=payload.product_id,
    )
    if line.product_id is not None and line.unit_price is not None:
        invoice_pricing.reprice_line(db, tenant_id, line)
        db.refresh(line)
    return line


@router.delete("/{invoice_id}/lines/{line_id}", status_code=204)
def api_delete_line(
    invoice_id: str,
    line_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    _: list = Depends(require_writer),
):
    """Delete a line (and its derived price), recompute affected recipes."""
    line = crud_invoice_line.get_line(db, tenant_id, line_id)
    if not line or str(line.invoice_id) != invoice_id:
        raise HTTPException(status_code=404, detail="Invoice line not found")
    invoice_pricing.delete_line(db, tenant_id, line)


@router.get("/{invoice_id}", response_model=InvoiceRead)
def api_get_invoice(
    invoice_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
):
    invoice = get_invoice(db, invoice_id, tenant_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice


@router.get("/{invoice_id}/file", response_model=InvoiceFileUrl)
def api_get_invoice_file(
    invoice_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
):
    invoice = get_invoice(db, invoice_id, tenant_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if not invoice.file_url:
        raise HTTPException(status_code=404, detail="Aucun fichier stocké pour cette facture")
    url = s3_storage.presigned_url(invoice.file_url)
    if not url:
        raise HTTPException(status_code=404, detail="Stockage de fichiers indisponible")
    return {"url": url}


@router.get("/{invoice_id}/lines", response_model=List[InvoiceLineRead])
def api_list_invoice_lines(
    invoice_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
):
    invoice = get_invoice(db, invoice_id, tenant_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return crud_invoice_line.list_lines(db, invoice_id)


@router.post("/{invoice_id}/process", response_model=InvoiceProcessSummary)
def api_process_invoice(
    invoice_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    _: list = Depends(require_writer),
):
    """(Re)run auto-match + pricing + recompute on an already-parsed invoice."""
    try:
        return invoice_pricing.process_invoice(db, tenant_id, invoice_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post(
    "/{invoice_id}/lines/{line_id}/create-product", response_model=ProductRead, status_code=201
)
def api_create_product_from_line(
    invoice_id: str,
    line_id: str,
    payload: CreateProductFromLine,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    _: list = Depends(require_writer),
):
    """Create a new catalog product from an unrecognised invoice line, then map
    the line to it and derive its price (so the cost updates automatically)."""
    line = crud_invoice_line.get_line(db, tenant_id, line_id)
    if not line or str(line.invoice_id) != invoice_id:
        raise HTTPException(status_code=404, detail="Invoice line not found")

    name = (payload.name or line.description or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Un nom de produit est requis")

    unit_id = line.unit_id  # read before create_product's commit expires the row
    product = crud_product.create_product(
        db,
        ProductCreate(name=name, sku=payload.sku, base_unit_id=unit_id),
        tenant_id,
    )
    # re-fetch the line (the commit above expired it), then map to the new
    # product + create its price + recompute recipes.
    line = crud_invoice_line.get_line(db, tenant_id, line_id)
    invoice_pricing.map_line_product(db, tenant_id, line, str(product.id))
    return product


@router.post(
    "/{invoice_id}/lines/{line_id}/map-product", response_model=MapProductResult
)
def api_map_line_product(
    invoice_id: str,
    line_id: str,
    payload: MapProductRequest,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    _: list = Depends(require_writer),
):
    line = crud_invoice_line.get_line(db, tenant_id, line_id)
    if not line or str(line.invoice_id) != invoice_id:
        raise HTTPException(status_code=404, detail="Invoice line not found")
    return invoice_pricing.map_line_product(db, tenant_id, line, payload.product_id)


@router.patch("/{invoice_id}/lines/{line_id}", response_model=InvoiceLineRead)
def api_update_line(
    invoice_id: str,
    line_id: str,
    payload: InvoiceLineUpdate,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    _: list = Depends(require_writer),
):
    """Correct an extracted line (description / qty / unit / unit_price / total).

    If the line is mapped to a product, its price row is re-derived from the
    corrected values and the affected recipe costs are recomputed — so a fix in
    the OCR output propagates to the real cost.
    """
    line = crud_invoice_line.get_line(db, tenant_id, line_id)
    if not line or str(line.invoice_id) != invoice_id:
        raise HTTPException(status_code=404, detail="Invoice line not found")

    fields = {
        "description": payload.description,
        "qty": payload.qty,
        "unit_price": payload.unit_price,
        "line_total": payload.line_total,
        "vat_rate": payload.vat_rate,
    }
    if payload.unit is not None:
        unit_id = crud_price.get_units_by_code(db).get(payload.unit.strip().lower())
        if unit_id is not None:
            fields["unit_id"] = unit_id

    updated = crud_invoice_line.update_line(db, tenant_id, line_id, **fields)
    if updated.product_id is not None and updated.unit_price is not None:
        invoice_pricing.reprice_line(db, tenant_id, updated)
        db.refresh(updated)
    return updated


@router.get("/{invoice_id}/control")
def api_invoice_control(
    invoice_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Contrôle facture : commandé → livré → facturé, en une vue.

    Rattache la facture à sa commande (déjà liée, ou par recouvrement
    fournisseur + produits), puis confronte les trois. Met en évidence, du plus
    grave au moins grave : facturé mais non reçu, facturé hors commande, prix,
    TVA, quantités. Rend ``linked: false`` plutôt qu'un rapprochement douteux."""
    invoice = get_invoice(db, invoice_id, tenant_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice_control.control_for_invoice(db, tenant_id, invoice)


# Rétrocompatibilité : l'application iOS déjà en production appelle encore
# `/quote-variance`. On la sert avec le NOUVEAU contrôle (commandé → livré →
# facturé) plutôt que l'ancien rapprochement au devis, qui est mort depuis que
# la commande est un objet à part entière. Un seul moteur, deux chemins d'accès
# le temps que les clients basculent.
@router.get("/{invoice_id}/quote-variance", deprecated=True)
def api_invoice_quote_variance(
    invoice_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
):
    return api_invoice_control(invoice_id, db, tenant_id)


@router.post("/extract", response_model=InvoiceExtractionResult)
async def api_extract_invoice(
    file: UploadFile = File(...),
    tenant_id: str = Depends(get_current_tenant_id),
    # Was the only expensive route without it: a read-only `viewer` could burn
    # the paid OCR quota at will.
    _: list = Depends(require_writer),
    _q: None = Depends(quota("ocr", "OCR_PER_MIN", 20)),
    _qd: None = Depends(daily_quota("ocr", "OCR_PER_DAY", 400)),
):
    content = await file.read()
    validate_upload(content, file.content_type)
    ctype = file.content_type

    def _work():
        try:
            return extract_invoice(content, ctype)
        except OcrError as exc:
            raise _ocr_http_error(exc)

    return await run_in_threadpool(_work)


@router.post("/preview", response_model=InvoicePreviewResult)
async def api_preview_invoice(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    _: list = Depends(require_writer),
    _q: None = Depends(quota("ocr", "OCR_PER_MIN", 20)),
    _qd: None = Depends(daily_quota("ocr", "OCR_PER_DAY", 400)),
):
    """Smart-import preview: OCR + per-line product-match suggestion + category
    suggestion, for the validation dialog. Persists nothing (the detected supplier
    is resolved to an existing one but never created here)."""
    content = await file.read()
    validate_upload(content, file.content_type)
    ctype = file.content_type

    def _work():
        try:
            extraction = extract_invoice(content, ctype)
        except OcrError as exc:
            raise _ocr_http_error(exc)

        # Le nom lu en tête peut être celui du destinataire : on l'écarte.
        own = _tenant_name(db, tenant_id)
        if own and extraction.supplier:
            from app.services.ocr.service import guess_supplier

            extraction.supplier = guess_supplier(extraction.raw_text or "", exclude=own)

        supplier_id = None
        if extraction.supplier:
            existing = crud_supplier.get_supplier_by_name(db, tenant_id, extraction.supplier)
            supplier_id = str(existing.id) if existing is not None else None

        lines: List[InvoicePreviewLine] = []
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
                InvoicePreviewLine(
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
        return InvoicePreviewResult(
            supplier=extraction.supplier,
            supplier_id=supplier_id,
            date=extraction.date,
            invoice_number=extraction.invoice_number,
            total_amount=getattr(extraction, "total_amount", None),
            lines=lines,
        )

    return await run_in_threadpool(_work)


@router.post("/confirm", response_model=InvoiceIngestResult, status_code=201)
def api_confirm_invoice(
    payload: InvoiceConfirmRequest,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    _: list = Depends(require_writer),
):
    """Persist a validated smart-import: create the invoice, then per line create
    a new product (auto-classified, with VAT) or associate an existing one, and
    derive prices (which also links the product to the supplier — #7). Lines are
    the ones the user reviewed in the dialog; no re-OCR."""
    # Detect/resolve the supplier once (#7 starts here).
    supplier_id = payload.supplier_id
    if not supplier_id and payload.supplier:
        sup = crud_supplier.get_or_create_supplier_by_name(db, tenant_id, payload.supplier)
        supplier_id = str(sup.id) if sup is not None else None

    invoice = Invoice(
        id=str(_uuid.uuid4()),
        tenant_id=tenant_id,
        supplier_id=supplier_id,
        invoice_number=payload.invoice_number,
        date=payload.date,
        total_amount=payload.total_amount,
        currency=payload.currency or "EUR",
        parsed=True,
        ocr_status="confirmed",
    )
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    invoice_id = str(invoice.id)

    units = crud_price.get_units_by_code(db)
    created_products = 0
    associated = 0
    lines_persisted = 0

    for l in payload.lines:
        if l.action == "skip":
            continue
        unit_id = units.get((l.unit or "").strip().lower()) if l.unit else None
        product_id = None
        if l.action == "associate" and l.product_id:
            assert_product_in_tenant(db, tenant_id, l.product_id)
            product_id = l.product_id
            associated += 1
        elif l.action == "create":
            prod = crud_product.create_product(
                db,
                ProductCreate(
                    name=l.description,
                    base_unit_id=unit_id,
                    category=l.category,
                    vat_rate=l.vat_rate,
                ),
                tenant_id,
            )
            product_id = str(prod.id)
            created_products += 1

        line = crud_invoice_line.create_invoice_line(
            db,
            invoice_id,
            description=l.description,
            qty=l.qty,
            unit_id=unit_id,
            unit_price=l.unit_price,
            line_total=l.line_total,
            vat_rate=l.vat_rate,
            product_id=product_id,
        )
        lines_persisted += 1
        # Derive the price -> also records purchase history + auto-links the
        # product to the invoice's supplier (#7) + recomputes recipe costs.
        if product_id and l.unit_price is not None:
            invoice_pricing.reprice_line(db, tenant_id, line)

    # Rattachement à la COMMANDE correspondante, et avancement de son cycle.
    # Best-effort : un rapprochement impossible ne doit jamais faire échouer
    # l'import. La facture se rattache à la commande — et atteint le devis à
    # travers elle —, ce qui donne le contrôle à trois colonnes commandé →
    # livré → facturé.
    try:
        matched = invoice_control.find_matching_order(db, tenant_id, invoice)
        if matched is not None:
            invoice.order_id = matched.id
            # Une commande reçue devient facturée : dernier pas avant la clôture.
            # On ne force pas depuis un état antérieur — une facture peut arriver
            # avant que la réception ne soit saisie, ce n'est pas à elle de
            # décréter la livraison faite.
            if order_service.can_transition(matched.status, order_service.INVOICED):
                matched.status = order_service.INVOICED
            db.commit()
    except Exception:
        db.rollback()

    return {
        "invoice_id": invoice_id,
        "summary": {
            "invoice_id": invoice_id,
            "lines": lines_persisted,
            "matched": associated,
            "prices_created": created_products + associated,
            "needs_review": [],
        },
    }
