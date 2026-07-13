from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_current_tenant_id, require_writer, quota
from app.schemas.schemas import (
    ProductCreate,
    ProductUpdate,
    ProductRead,
    ProductMatchRequest,
    ProductMatchResultRead,
)
from app.crud.crud_product import (
    create_product,
    get_product,
    list_products,
    list_products_enriched,
    update_product,
    delete_product,
)
from app.services.matching.product_matcher import match_product
from app.services.purchasing import purchase_service

router = APIRouter()


@router.get("/{product_id}/price-history")
def api_product_price_history(
    product_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Full purchase history of a product (date, supplier, qty, total, unit cost,
    standardized cost/base unit, variation vs previous purchase)."""
    if not get_product(db, product_id, tenant_id):
        raise HTTPException(status_code=404, detail="Product not found")
    return purchase_service.product_price_history(db, tenant_id, product_id)


@router.get("/{product_id}/supplier-comparison")
def api_product_supplier_comparison(
    product_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Latest standardized cost per supplier for a product; cheapest flagged."""
    if not get_product(db, product_id, tenant_id):
        raise HTTPException(status_code=404, detail="Product not found")
    return purchase_service.supplier_comparison(db, tenant_id, product_id)


# The fuzzy score runs a sliding-window comparison of `text` against every
# product and alias in the catalogue: cost is O(len(text) × catalogue size).
MAX_MATCH_TEXT_CHARS = 300


@router.post("/match", response_model=ProductMatchResultRead)
def api_match_product(
    payload: ProductMatchRequest,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    _: list = Depends(require_writer),
    _q: None = Depends(quota("match", "PRODUCT_MATCH_PER_MIN", 60)),
):
    if len(payload.text or "") > MAX_MATCH_TEXT_CHARS:
        raise HTTPException(
            status_code=413,
            detail=f"Libellé trop long ({MAX_MATCH_TEXT_CHARS} caractères maximum).",
        )
    return match_product(db, tenant_id, payload.text, payload.fuzzy_min_score)


@router.post("/", response_model=ProductRead, status_code=201)
def api_create_product(
    payload: ProductCreate,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    _: list = Depends(require_writer),
):
    return create_product(db, payload, tenant_id)


@router.get("/", response_model=List[ProductRead])
def api_list_products(
    skip: int = 0,
    limit: int = Query(50, ge=1, le=200),
    q: Optional[str] = None,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
):
    return list_products(db, tenant_id, skip=skip, limit=limit, q=q)


@router.get("/enriched")
def api_list_products_enriched(
    skip: int = 0,
    limit: int = Query(200, ge=1, le=500),
    q: Optional[str] = None,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Products + category, base unit, latest cost/supplier and price variation."""
    return list_products_enriched(db, tenant_id, skip=skip, limit=limit, q=q)


@router.get("/{product_id}", response_model=ProductRead)
def api_get_product(
    product_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
):
    product = get_product(db, product_id, tenant_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.put("/{product_id}", response_model=ProductRead)
def api_update_product(
    product_id: str,
    payload: ProductUpdate,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    _: list = Depends(require_writer),
):
    product = update_product(db, product_id, tenant_id, payload)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.delete("/{product_id}", status_code=204)
def api_delete_product(
    product_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    _: list = Depends(require_writer),
):
    try:
        deleted = delete_product(db, product_id, tenant_id)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Produit référencé (factures/recettes) — suppression impossible.",
        )
    if not deleted:
        raise HTTPException(status_code=404, detail="Product not found")
    return None
