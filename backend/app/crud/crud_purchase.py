"""Persistence + queries for purchase history and price alerts."""
import uuid
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.models import PurchaseHistory, PriceAlert


# --------------------------------------------------------------------------- #
# purchase history
# --------------------------------------------------------------------------- #
def create_purchase(db: Session, **fields) -> PurchaseHistory:
    row = PurchaseHistory(id=str(uuid.uuid4()), **fields)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def last_purchase(
    db: Session, tenant_id: str, product_id: str, supplier_id: Optional[str],
    exclude_line_id: Optional[str] = None,
) -> Optional[PurchaseHistory]:
    """Most recent prior purchase of the same product from the same supplier."""
    q = db.query(PurchaseHistory).filter(
        PurchaseHistory.tenant_id == tenant_id,
        PurchaseHistory.product_id == product_id,
    )
    if supplier_id is not None:
        q = q.filter(PurchaseHistory.supplier_id == supplier_id)
    else:
        q = q.filter(PurchaseHistory.supplier_id.is_(None))
    if exclude_line_id is not None:
        q = q.filter(PurchaseHistory.invoice_line_id != exclude_line_id)
    return q.order_by(
        PurchaseHistory.purchase_date.desc().nullslast(),
        PurchaseHistory.created_at.desc(),
    ).first()


def delete_for_line(db: Session, tenant_id: str, invoice_line_id: str) -> int:
    """Drop any purchase rows derived from an invoice line (idempotent re-record)."""
    deleted = (
        db.query(PurchaseHistory)
        .filter(
            PurchaseHistory.tenant_id == tenant_id,
            PurchaseHistory.invoice_line_id == invoice_line_id,
        )
        .delete(synchronize_session=False)
    )
    db.commit()
    return deleted


def product_purchases(db: Session, tenant_id: str, product_id: str) -> List[PurchaseHistory]:
    return (
        db.query(PurchaseHistory)
        .filter(
            PurchaseHistory.tenant_id == tenant_id,
            PurchaseHistory.product_id == product_id,
        )
        .order_by(
            PurchaseHistory.purchase_date.asc().nullsfirst(),
            PurchaseHistory.created_at.asc(),
        )
        .all()
    )


def supplier_purchases(db: Session, tenant_id: str, supplier_id: str) -> List[PurchaseHistory]:
    return (
        db.query(PurchaseHistory)
        .filter(
            PurchaseHistory.tenant_id == tenant_id,
            PurchaseHistory.supplier_id == supplier_id,
        )
        .order_by(
            PurchaseHistory.purchase_date.desc().nullslast(),
            PurchaseHistory.created_at.desc(),
        )
        .all()
    )


def all_purchases(db: Session, tenant_id: str) -> List[PurchaseHistory]:
    return (
        db.query(PurchaseHistory)
        .filter(PurchaseHistory.tenant_id == tenant_id)
        .order_by(
            PurchaseHistory.purchase_date.desc().nullslast(),
            PurchaseHistory.created_at.desc(),
        )
        .all()
    )


# --------------------------------------------------------------------------- #
# alerts
# --------------------------------------------------------------------------- #
def create_alert(db: Session, **fields) -> PriceAlert:
    row = PriceAlert(id=str(uuid.uuid4()), **fields)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_alerts(
    db: Session, tenant_id: str, unread_only: bool = False, limit: int = 100
) -> List[PriceAlert]:
    q = db.query(PriceAlert).filter(PriceAlert.tenant_id == tenant_id)
    if unread_only:
        q = q.filter(PriceAlert.is_read.is_(False))
    return q.order_by(PriceAlert.created_at.desc()).limit(limit).all()


def mark_alert_read(db: Session, tenant_id: str, alert_id: str) -> Optional[PriceAlert]:
    alert = (
        db.query(PriceAlert)
        .filter(PriceAlert.id == alert_id, PriceAlert.tenant_id == tenant_id)
        .first()
    )
    if alert is None:
        return None
    alert.is_read = True
    db.commit()
    db.refresh(alert)
    return alert
