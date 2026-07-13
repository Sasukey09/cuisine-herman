from typing import Optional
from datetime import date
from sqlalchemy.orm import Session

from app.models.models import ProductPrice, Unit


def get_latest_price(
    db: Session, tenant_id: str, product_id: str, as_of: Optional[date] = None
) -> Optional[ProductPrice]:
    """Latest price for a product effective on/before ``as_of`` (default: today)."""
    q = db.query(ProductPrice).filter(
        ProductPrice.tenant_id == tenant_id,
        ProductPrice.product_id == product_id,
    )
    if as_of is not None:
        q = q.filter(ProductPrice.effective_date <= as_of)
    return q.order_by(ProductPrice.effective_date.desc(), ProductPrice.created_at.desc()).first()


def delete_prices_for_line(db: Session, tenant_id: str, line_id: str) -> int:
    """Remove price rows derived from a given invoice line (for clean re-pricing)."""
    deleted = (
        db.query(ProductPrice)
        .filter(
            ProductPrice.tenant_id == tenant_id,
            ProductPrice.source_invoice_line_id == line_id,
        )
        .delete(synchronize_session=False)
    )
    db.commit()
    return deleted


def get_units_map(db: Session) -> dict:
    """unit_id -> ratio_to_base, for converting quantities/prices to base units."""
    return {u.id: float(u.ratio_to_base or 1) for u in db.query(Unit).all()}


def get_units_by_code(db: Session) -> dict:
    """lowercased unit code -> unit_id, to resolve OCR unit strings."""
    return {(u.code or "").strip().lower(): u.id for u in db.query(Unit).all()}


def create_price(
    db: Session,
    tenant_id: str,
    product_id: str,
    price: float,
    unit_id=None,
    supplier_id=None,
    currency=None,
    effective_date=None,
    source_invoice_line_id=None,
) -> ProductPrice:
    import uuid

    row = ProductPrice(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        product_id=product_id,
        supplier_id=supplier_id,
        price=price,
        unit_id=unit_id,
        currency=currency,
        source_invoice_line_id=source_invoice_line_id,
    )
    if effective_date is not None:
        row.effective_date = effective_date
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_latest_prices(
    db: Session, tenant_id: str, product_ids, as_of: Optional[date] = None
) -> dict:
    """Latest price for MANY products, in a single query.

    The per-product :func:`get_latest_price` was being called once per recipe
    ingredient inside a loop over recipes — with 500 recipes of 10 ingredients
    that is 5 000 round trips for one page. Postgres' DISTINCT ON gives the same
    answer in one. Ordering is identical, so the winning row is the same.
    """
    ids = [str(p) for p in product_ids if p]
    if not ids:
        return {}

    q = db.query(ProductPrice).filter(
        ProductPrice.tenant_id == tenant_id,
        ProductPrice.product_id.in_(ids),
    )
    if as_of is not None:
        q = q.filter(ProductPrice.effective_date <= as_of)

    rows = (
        q.distinct(ProductPrice.product_id)
        .order_by(
            ProductPrice.product_id,
            ProductPrice.effective_date.desc(),
            ProductPrice.created_at.desc(),
        )
        .all()
    )
    return {str(r.product_id): r for r in rows}
