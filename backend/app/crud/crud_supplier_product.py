"""CRUD for the product↔supplier catalog (supplier_products).

Prices stay in product_prices; this table holds the catalog attributes a price
row cannot: availability, a preferred flag, the supplier's reference, lead time.
"""

from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.models import SupplierProduct
from app.schemas.schemas import SupplierProductCreate, SupplierProductUpdate


def list_links(db: Session, tenant_id: str, product_id: str) -> List[SupplierProduct]:
    return (
        db.query(SupplierProduct)
        .filter(
            SupplierProduct.tenant_id == tenant_id,
            SupplierProduct.product_id == product_id,
        )
        .order_by(SupplierProduct.preferred.desc(), SupplierProduct.created_at.asc())
        .all()
    )


def get_link(db: Session, tenant_id: str, link_id: str) -> Optional[SupplierProduct]:
    return (
        db.query(SupplierProduct)
        .filter(SupplierProduct.id == link_id, SupplierProduct.tenant_id == tenant_id)
        .first()
    )


def get_link_by_supplier(
    db: Session, tenant_id: str, product_id: str, supplier_id: str
) -> Optional[SupplierProduct]:
    return (
        db.query(SupplierProduct)
        .filter(
            SupplierProduct.tenant_id == tenant_id,
            SupplierProduct.product_id == product_id,
            SupplierProduct.supplier_id == supplier_id,
        )
        .first()
    )


def get_or_create_link(
    db: Session, tenant_id: str, product_id: str, supplier_id: str
) -> SupplierProduct:
    """Ensure a (product, supplier) catalog row exists. Flushes (not commits) so
    it joins the caller's transaction — used by invoice import to link a product
    to its supplier automatically."""
    existing = get_link_by_supplier(db, tenant_id, product_id, supplier_id)
    if existing is not None:
        return existing
    obj = SupplierProduct(
        tenant_id=tenant_id, product_id=product_id, supplier_id=supplier_id
    )
    db.add(obj)
    db.flush()
    return obj


def create_link(
    db: Session, tenant_id: str, product_id: str, payload: SupplierProductCreate
) -> SupplierProduct:
    """Create the catalog link, or update it if the (product, supplier) pair
    already exists — the endpoint stays idempotent instead of 409-ing."""
    existing = get_link_by_supplier(db, tenant_id, product_id, payload.supplier_id)
    data = payload.model_dump(exclude={"supplier_id"}, exclude_unset=True)
    if existing is not None:
        for field, value in data.items():
            setattr(existing, field, value)
        db.commit()
        db.refresh(existing)
        return existing
    obj = SupplierProduct(
        tenant_id=tenant_id,
        product_id=product_id,
        supplier_id=payload.supplier_id,
        **data,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_link(
    db: Session, link: SupplierProduct, payload: SupplierProductUpdate
) -> SupplierProduct:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(link, field, value)
    db.commit()
    db.refresh(link)
    return link


def delete_link(db: Session, link: SupplierProduct) -> None:
    db.delete(link)
    db.commit()
