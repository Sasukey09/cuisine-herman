import uuid
from typing import Optional
from sqlalchemy.orm import Session

from app.models.models import Product, ProductAlias, ProductMatchResult


def get_products_for_tenant(db: Session, tenant_id: str):
    return db.query(Product).filter(Product.tenant_id == tenant_id).all()


def get_aliases_for_tenant(db: Session, tenant_id: str):
    return db.query(ProductAlias).filter(ProductAlias.tenant_id == tenant_id).all()


def save_match_result(
    db: Session,
    tenant_id: str,
    ocr_text: str,
    matched_product_id: Optional[str],
    confidence: float,
    match_type: str,
    manual_review: bool = False,
) -> ProductMatchResult:
    m = ProductMatchResult(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        ocr_text=ocr_text,
        matched_product_id=matched_product_id,
        confidence=confidence,
        match_type=match_type,
        manual_review=manual_review,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return m
