"""Lecture/écriture des commandes fournisseur.

La sérialisation vit ici plutôt que dans les endpoints : le web et le mobile
consomment la même forme, et deux surfaces qui recomposent chacune leur JSON
finissent par diverger sur un détail (le libellé d'un statut, un total arrondi).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.models import (
    Product,
    PurchaseOrder,
    PurchaseOrderLine,
    Supplier,
)
from app.services.purchasing import order_service, reception_service


def _f(v: Any) -> Optional[float]:
    return float(v) if v is not None else None


def list_orders(
    db: Session,
    tenant_id: str,
    status: Optional[str] = None,
    supplier_id: Optional[str] = None,
    limit: int = 200,
) -> List[Dict[str, Any]]:
    counts = dict(
        db.query(PurchaseOrderLine.order_id, func.count(PurchaseOrderLine.id))
        .filter(PurchaseOrderLine.tenant_id == tenant_id)
        .group_by(PurchaseOrderLine.order_id)
        .all()
    )
    q = (
        db.query(PurchaseOrder, Supplier.name)
        .outerjoin(Supplier, Supplier.id == PurchaseOrder.supplier_id)
        .filter(PurchaseOrder.tenant_id == tenant_id)
    )
    if status:
        q = q.filter(PurchaseOrder.status == status)
    if supplier_id:
        q = q.filter(PurchaseOrder.supplier_id == supplier_id)
    rows = q.order_by(PurchaseOrder.created_at.desc()).limit(limit).all()
    return [_head(o, name, counts.get(o.id, 0)) for o, name in rows]


def get_order(db: Session, tenant_id: str, order_id: str) -> Optional[PurchaseOrder]:
    return (
        db.query(PurchaseOrder)
        .filter(PurchaseOrder.tenant_id == tenant_id, PurchaseOrder.id == order_id)
        .first()
    )


def _head(order: PurchaseOrder, supplier_name: Optional[str], line_count: int) -> Dict[str, Any]:
    return {
        "id": str(order.id),
        "reference": order.reference,
        "supplier_id": str(order.supplier_id) if order.supplier_id else None,
        "supplier_name": supplier_name,
        "status": order.status,
        # Le libellé est calculé côté serveur : sinon web et mobile tiennent
        # chacun leur table de traduction, et elles divergent.
        "status_label": order_service.STATUS_LABELS.get(order.status or "", order.status),
        "expected_date": order.expected_date,
        "ordered_at": order.ordered_at,
        "total_amount": _f(order.total_amount),
        "currency": order.currency,
        "delivery_fee": _f(order.delivery_fee),
        "discount_total": _f(order.discount_total),
        "conditions": order.conditions,
        "notes": order.notes,
        "line_count": line_count,
        "created_at": order.created_at,
    }


def detail(db: Session, tenant_id: str, order: PurchaseOrder) -> Dict[str, Any]:
    supplier_name = (
        db.query(Supplier.name).filter(Supplier.id == order.supplier_id).scalar()
        if order.supplier_id
        else None
    )
    lines = (
        db.query(PurchaseOrderLine)
        .filter(
            PurchaseOrderLine.tenant_id == tenant_id,
            PurchaseOrderLine.order_id == order.id,
        )
        .order_by(PurchaseOrderLine.created_at)
        .all()
    )
    names = dict(
        db.query(Product.id, Product.name)
        .filter(Product.id.in_([l.product_id for l in lines if l.product_id]))
        .all()
    ) if lines else {}

    # Reçu par ligne : calculé, jamais stocké — une seule vérité. Et lu par le
    # service réception, parce que « reçu » veut dire ACCEPTÉ : une somme SQL
    # brute compterait aussi ce qui est reparti ou a été détruit.
    received = (
        reception_service.received_by_order_line(db, tenant_id, str(order.id))
        if lines
        else {}
    )

    head = _head(order, supplier_name, len(lines))
    head["lines"] = [
        {
            "id": str(l.id),
            "product_id": str(l.product_id) if l.product_id else None,
            "product_name": names.get(l.product_id),
            "description": l.description,
            "qty_ordered": _f(l.qty_ordered),
            "unit_id": l.unit_id,
            "unit_price": _f(l.unit_price),
            "vat_rate": _f(l.vat_rate),
            "discount_pct": _f(l.discount_pct),
            "line_total": _f(l.line_total),
            "pack_size": l.pack_size,
            "brand": l.brand,
            "source_quote_line_id": str(l.source_quote_line_id)
            if l.source_quote_line_id
            else None,
            "qty_received": received.get(str(l.id), 0.0),
        }
        for l in lines
    ]
    return head


def delete_order(db: Session, order: PurchaseOrder) -> None:
    db.delete(order)
    db.commit()
