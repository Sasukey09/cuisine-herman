from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from app.models.models import (
    Product,
    ProductPrice,
    ProductCategory,
    Supplier,
    Unit,
)
from app.schemas.schemas import ProductCreate, ProductUpdate
import uuid


def list_products_enriched(
    db: Session,
    tenant_id: str,
    skip: int = 0,
    limit: int = 200,
    q: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Products with category, base unit, latest cost + supplier, and the
    price variation vs the previous price (standardized per base unit)."""
    products = list_products(db, tenant_id, skip=skip, limit=limit, q=q)
    ids = [p.id for p in products]

    units = {u.id: (u.code, float(u.ratio_to_base or 1) or 1.0) for u in db.query(Unit).all()}
    cats = {
        c.id: c.name
        for c in db.query(ProductCategory).filter(ProductCategory.tenant_id == tenant_id).all()
    }
    sups = {
        str(s.id): s.name
        for s in db.query(Supplier).filter(Supplier.tenant_id == tenant_id).all()
    }

    by_product: Dict[str, list] = {}
    if ids:
        rows = (
            db.query(ProductPrice)
            .filter(ProductPrice.tenant_id == tenant_id, ProductPrice.product_id.in_(ids))
            .order_by(
                ProductPrice.product_id,
                ProductPrice.effective_date.desc(),
                ProductPrice.created_at.desc(),
            )
            .all()
        )
        for r in rows:
            by_product.setdefault(str(r.product_id), []).append(r)

    out: List[Dict[str, Any]] = []
    for p in products:
        pl = by_product.get(str(p.id), [])
        latest = pl[0] if pl else None
        prev = pl[1] if len(pl) > 1 else None

        variation = None
        if latest is not None and prev is not None:
            r_new = units.get(latest.unit_id, (None, 1.0))[1] or 1.0
            r_old = units.get(prev.unit_id, (None, 1.0))[1] or 1.0
            try:
                a = float(latest.price) / r_new
                b = float(prev.price) / r_old
                if b > 0:
                    variation = round((a - b) / b * 100.0, 1)
            except (TypeError, ValueError, ZeroDivisionError):
                variation = None

        out.append(
            {
                "id": str(p.id),
                "name": p.name,
                "sku": p.sku,
                "category": cats.get(p.category_id),
                "unit": units.get(p.base_unit_id, (None,))[0]
                or (units.get(latest.unit_id, (None,))[0] if latest else None),
                "last_cost": float(latest.price) if latest and latest.price is not None else None,
                "currency": latest.currency if latest else None,
                "supplier": sups.get(str(latest.supplier_id)) if latest and latest.supplier_id else None,
                "variation_pct": variation,
            }
        )
    return out


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
    data = payload.model_dump(exclude_unset=True)
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
