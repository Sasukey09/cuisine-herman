from typing import Optional
from sqlalchemy.orm import Session
from app.models.models import Product
from app.schemas.schemas import ProductCreate, ProductUpdate
import uuid


def create_product(db: Session, payload: ProductCreate, tenant_id: str) -> Product:
    obj = Product(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        name=payload.name,
        sku=payload.sku,
        base_unit_id=payload.base_unit_id,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def get_product(db: Session, product_id: str, tenant_id: str):
    return (
        db.query(Product)
        .filter(Product.id == product_id, Product.tenant_id == tenant_id)
        .first()
    )


def list_products(
    db: Session,
    tenant_id: str,
    skip: int = 0,
    limit: int = 50,
    q: Optional[str] = None,
):
    query = db.query(Product).filter(Product.tenant_id == tenant_id)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(Product.name.ilike(like))
    return query.order_by(Product.created_at.desc()).offset(skip).limit(limit).all()


def update_product(db: Session, product_id: str, tenant_id: str, payload: ProductUpdate):
    obj = get_product(db, product_id, tenant_id)
    if obj is None:
        return None
    data = payload.dict(exclude_unset=True)
    for field, value in data.items():
        setattr(obj, field, value)
    db.commit()
    db.refresh(obj)
    return obj


def delete_product(db: Session, product_id: str, tenant_id: str) -> bool:
    obj = get_product(db, product_id, tenant_id)
    if obj is None:
        return False
    db.delete(obj)
    db.commit()
    return True
