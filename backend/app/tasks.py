from app.celery_app import celery_app
from app.db.session import SessionLocal
from app.services.costing import cost_engine


@celery_app.task(name="app.tasks.process_invoice_ocr", bind=True, max_retries=2)
def process_invoice_ocr(self, invoice_id: str, tenant_id: str, s3_key: str, content_type: str = None):
    """Async invoice OCR: download file from storage -> OCR -> persist lines ->
    auto-match -> price history -> recompute affected recipe costs.

    Updates ``invoice.ocr_status`` (processing/done/error) so the UI can poll.
    Retries transient OCR failures with backoff; permanent failures mark error.
    """
    # local imports keep the task module light and avoid import cycles
    from app.services.storage import s3_storage
    from app.services.ocr.service import extract_invoice
    from app.services.ocr.errors import OcrError
    from app.services.invoicing import invoice_pricing
    from app.crud import crud_invoice

    db = SessionLocal()
    try:
        crud_invoice.set_invoice_ocr_status(db, invoice_id, tenant_id, "processing")
        content = s3_storage.download_invoice(s3_key)
        if content is None:
            crud_invoice.set_invoice_ocr_status(db, invoice_id, tenant_id, "error")
            return {"invoice_id": invoice_id, "status": "error", "reason": "file_unavailable"}
        try:
            extraction = extract_invoice(content, content_type)
        except OcrError as exc:
            # transient: retry a couple of times, then mark error
            if self.request.retries < self.max_retries:
                raise self.retry(exc=exc, countdown=10)
            crud_invoice.set_invoice_ocr_status(db, invoice_id, tenant_id, "error")
            return {"invoice_id": invoice_id, "status": "error", "reason": "ocr_failed"}

        invoice_pricing.persist_extraction(db, tenant_id, invoice_id, extraction)
        summary = invoice_pricing.process_invoice(db, tenant_id, invoice_id)
        crud_invoice.set_invoice_ocr_status(db, invoice_id, tenant_id, "done")
        return {"invoice_id": invoice_id, "status": "done", "summary": summary}
    finally:
        db.close()


@celery_app.task(name="app.tasks.recompute_recipe_costs")
def recompute_recipe_costs(product_id: str):
    """Recompute cost snapshots for every recipe version using this product."""
    db = SessionLocal()
    try:
        recomputed = cost_engine.recompute_for_product(db, product_id)
        return {"product_id": product_id, "recomputed_versions": recomputed}
    finally:
        db.close()
