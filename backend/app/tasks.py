from app.celery_app import celery_app
from app.db.session import SessionLocal
from app.services.costing import cost_engine


@celery_app.task(name="app.tasks.run_ocr")
def run_ocr(invoice_id: str, s3_url: str):
    # TODO: download file, call OCR providers, push parse task
    return {"invoice_id": invoice_id, "status": "ocr_started"}


@celery_app.task(name="app.tasks.recompute_recipe_costs")
def recompute_recipe_costs(product_id: str):
    """Recompute cost snapshots for every recipe version using this product."""
    db = SessionLocal()
    try:
        recomputed = cost_engine.recompute_for_product(db, product_id)
        return {"product_id": product_id, "recomputed_versions": recomputed}
    finally:
        db.close()
