from typing import Optional
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.models.models import Supplier, ProductPrice, Product
from app.schemas.schemas import SupplierCreate, SupplierUpdate
import uuid


def get_supplier_by_name(db: Session, tenant_id: str, name: str) -> Optional[Supplier]:
    norm = (name or "").strip()
    if not norm:
        return None
    return (
        db.query(Supplier)
        .filter(
            Supplier.tenant_id == tenant_id,
            func.lower(Supplier.name) == norm.lower(),
        )
        .first()
    )


def get_or_create_supplier_by_name(
    db: Session, tenant_id: str, name: str
) -> Optional[Supplier]:
    """Resolve a supplier by name within the tenant, creating it if absent.

    Used by invoice ingestion so an OCR-extracted supplier name always resolves to
    a real ``supplier_id``. Flushes (not commits) so it joins the caller's
    transaction. Returns ``None`` only when there is no usable name to resolve.
    """
    norm = (name or "").strip()
    if not norm:
        return None
    existing = get_supplier_by_name(db, tenant_id, norm)
    if existing is not None:
        return existing
    obj = Supplier(id=str(uuid.uuid4()), tenant_id=tenant_id, name=norm)
    db.add(obj)
    db.flush()  # make obj.id available; the caller owns the commit
    return obj


def create_supplier(db: Session, payload: SupplierCreate, tenant_id: str) -> Supplier:
    obj = Supplier(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        name=payload.name,
        code=payload.code,
        contact=payload.contact,
        rating=getattr(payload, "rating", None),
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def get_supplier(db: Session, supplier_id: str, tenant_id: str):
    return (
        db.query(Supplier)
        .filter(Supplier.id == supplier_id, Supplier.tenant_id == tenant_id)
        .first()
    )


def list_suppliers(
    db: Session,
    tenant_id: str,
    skip: int = 0,
    limit: int = 50,
    q: Optional[str] = None,
):
    query = db.query(Supplier).filter(Supplier.tenant_id == tenant_id)
    if q:
        query = query.filter(Supplier.name.ilike(f"%{q.strip()}%"))
    return query.order_by(Supplier.created_at.desc()).offset(skip).limit(limit).all()


def list_suppliers_enriched(
    db: Session,
    tenant_id: str,
    skip: int = 0,
    limit: int = 50,
    q: Optional[str] = None,
):
    """Suppliers + how many distinct products have been priced from each."""
    from sqlalchemy import func

    suppliers = list_suppliers(db, tenant_id, skip=skip, limit=limit, q=q)
    counts = dict(
        db.query(
            ProductPrice.supplier_id,
            func.count(func.distinct(ProductPrice.product_id)),
        )
        .filter(ProductPrice.tenant_id == tenant_id, ProductPrice.supplier_id.isnot(None))
        .group_by(ProductPrice.supplier_id)
        .all()
    )
    return [
        {
            "id": str(s.id),
            "name": s.name,
            "code": s.code,
            "contact": s.contact,
            "rating": float(s.rating) if s.rating is not None else None,
            "product_count": int(counts.get(s.id, 0)),
        }
        for s in suppliers
    ]


def update_supplier(db: Session, supplier_id: str, tenant_id: str, payload: SupplierUpdate):
    obj = get_supplier(db, supplier_id, tenant_id)
    if obj is None:
        return None
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(obj, field, value)
    db.commit()
    db.refresh(obj)
    return obj


def delete_supplier(db: Session, supplier_id: str, tenant_id: str) -> bool:
    obj = get_supplier(db, supplier_id, tenant_id)
    if obj is None:
        return False
    db.delete(obj)
    db.commit()
    return True


def get_supplier_prices(db: Session, supplier_id: str, tenant_id: str):
    """Price history recorded for this supplier, with product names."""
    rows = (
        db.query(ProductPrice, Product.name.label("product_name"))
        .outerjoin(Product, Product.id == ProductPrice.product_id)
        .filter(
            ProductPrice.tenant_id == tenant_id,
            ProductPrice.supplier_id == supplier_id,
        )
        .order_by(ProductPrice.effective_date.desc(), ProductPrice.created_at.desc())
        .all()
    )
    result = []
    for price, product_name in rows:
        result.append(
            {
                "id": str(price.id),
                "product_id": str(price.product_id) if price.product_id else None,
                "product_name": product_name,
                "price": float(price.price) if price.price is not None else None,
                "currency": price.currency,
                "unit_id": price.unit_id,
                "effective_date": price.effective_date,
                "source_invoice_line_id": str(price.source_invoice_line_id)
                if price.source_invoice_line_id
                else None,
            }
        )
    return result
