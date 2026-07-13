from typing import List
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.tenancy import assert_product_in_tenant
from app.core.uploads import validate_upload
from app.db.session import get_db
from app.api.deps import get_current_tenant_id, require_writer, quota
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
from app.crud import crud_invoice_line, crud_price, crud_product
from app.schemas.schemas import (
    InvoiceFileUrl,
    InvoiceQueuedResp,
    InvoiceLineUpdate,
    InvoiceUpdate,
    InvoiceLineCreate,
    CreateProductFromLine,
    ProductCreate,
    ProductRead,
)
from app.services.ocr.service import extract_invoice
from app.services.ocr.schemas import InvoiceExtractionResult
from app.services.ocr.errors import OcrError
from app.services.invoicing import invoice_pricing
from app.services.storage import s3_storage

router = APIRouter()

_OCR_UNAVAILABLE = "Service OCR indisponible : impossible d'analyser la facture pour le moment."


@router.post("/upload", response_model=InvoiceCreateResp)
async def api_upload_invoice(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    _: list = Depends(require_writer),
    _q: None = Depends(quota("ocr", "OCR_PER_MIN", 20)),
):
    content = await file.read()
    validate_upload(content, file.content_type)
    invoice = create_invoice_from_upload(db, file, tenant_id)
    key = s3_storage.upload_invoice(tenant_id, invoice["id"], file.filename, content, file.content_type)
    if key:
        set_invoice_file_url(db, invoice["id"], tenant_id, key)
    return invoice


@router.post("/ingest", response_model=InvoiceIngestResult)
async def api_ingest_invoice(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    _: list = Depends(require_writer),
    _q: None = Depends(quota("ocr", "OCR_PER_MIN", 20)),
):
    """Full pipeline: upload -> OCR extract -> persist lines -> auto-match ->
    create price history -> recompute affected recipe costs."""
    content = await file.read()
    validate_upload(content, file.content_type)
    invoice = create_invoice_from_upload(db, file, tenant_id)
    invoice_id = invoice["id"]
    # persist the original file (non-blocking if storage is unavailable)
    key = s3_storage.upload_invoice(tenant_id, invoice_id, file.filename, content, file.content_type)
    if key:
        set_invoice_file_url(db, invoice_id, tenant_id, key)
    try:
        extraction = extract_invoice(content, file.content_type)
    except OcrError:
        raise HTTPException(status_code=502, detail=_OCR_UNAVAILABLE)
    invoice_pricing.persist_extraction(db, tenant_id, invoice_id, extraction)
    summary = invoice_pricing.process_invoice(db, tenant_id, invoice_id)
    return {"invoice_id": invoice_id, "summary": summary}


@router.post("/ingest-async", response_model=InvoiceQueuedResp)
async def api_ingest_invoice_async(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    _: list = Depends(require_writer),
    _q: None = Depends(quota("ocr", "OCR_PER_MIN", 20)),
):
    """Upload -> store file -> enqueue OCR as a Celery task and return immediately.

    The heavy OCR/parse/recompute runs in the worker; poll GET /invoices/{id}
    (field ``ocr_status``: queued/processing/done/error). Falls back to inline
    processing if storage or the task broker is unavailable.
    """
    content = await file.read()
    validate_upload(content, file.content_type)
    invoice = create_invoice_from_upload(db, file, tenant_id)
    invoice_id = invoice["id"]
    key = s3_storage.upload_invoice(tenant_id, invoice_id, file.filename, content, file.content_type)

    def _process_inline() -> str:
        try:
            extraction = extract_invoice(content, file.content_type)
        except OcrError:
            set_invoice_ocr_status(db, invoice_id, tenant_id, "error")
            raise HTTPException(status_code=502, detail=_OCR_UNAVAILABLE)
        invoice_pricing.persist_extraction(db, tenant_id, invoice_id, extraction)
        invoice_pricing.process_invoice(db, tenant_id, invoice_id)
        set_invoice_ocr_status(db, invoice_id, tenant_id, "done")
        return "done"

    # No object storage -> the worker can't fetch the file, so process inline.
    if not key:
        return {"invoice_id": invoice_id, "status": _process_inline()}

    set_invoice_file_url(db, invoice_id, tenant_id, key)
    try:
        from app.tasks import process_invoice_ocr

        process_invoice_ocr.delay(invoice_id, tenant_id, key, file.content_type)
        set_invoice_ocr_status(db, invoice_id, tenant_id, "queued")
        return {"invoice_id": invoice_id, "status": "queued"}
    except Exception:
        # broker unavailable -> degrade gracefully to inline processing
        return {"invoice_id": invoice_id, "status": _process_inline()}


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


@router.post("/extract", response_model=InvoiceExtractionResult)
async def api_extract_invoice(
    file: UploadFile = File(...),
    tenant_id: str = Depends(get_current_tenant_id),
    # Was the only expensive route without it: a read-only `viewer` could burn
    # the paid OCR quota at will.
    _: list = Depends(require_writer),
    _q: None = Depends(quota("ocr", "OCR_PER_MIN", 20)),
):
    content = await file.read()
    validate_upload(content, file.content_type)
    try:
        return extract_invoice(content, file.content_type)
    except OcrError:
        raise HTTPException(status_code=502, detail=_OCR_UNAVAILABLE)
