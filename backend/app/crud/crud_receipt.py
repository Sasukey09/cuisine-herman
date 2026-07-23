"""Lecture/écriture des réceptions.

Comme pour les commandes, la sérialisation vit ici : web et mobile consomment
la même forme, et deux surfaces qui recomposent chacune leur JSON finissent par
diverger sur un détail.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.models import (
    Product,
    PurchaseOrder,
    Receipt,
    ReceiptLine,
    ReceiptLineIssue,
    ReceiptLinePhoto,
    Supplier,
    User,
)
from app.services.purchasing import numbering, reception_service

STATUS_LABELS = {
    reception_service.DRAFT: "Brouillon",
    reception_service.CHECKED: "Contrôlée",
}


def _f(v: Any) -> Optional[float]:
    return float(v) if v is not None else None


def create(db: Session, tenant_id: str, payload, user_id: Optional[str]) -> Receipt:
    """Crée une réception en brouillon.

    Le fournisseur est repris de la commande quand il n'est pas fourni — mais
    il reste modifiable, précisément pour pouvoir enregistrer une livraison
    faite par quelqu'un d'autre que celui commandé. C'est l'anomalie qu'on veut
    détecter, pas interdire.
    """
    supplier_id = payload.supplier_id
    if supplier_id is None and payload.order_id:
        supplier_id = (
            db.query(PurchaseOrder.supplier_id)
            .filter(
                PurchaseOrder.tenant_id == tenant_id,
                PurchaseOrder.id == payload.order_id,
            )
            .scalar()
        )

    receipt = Receipt(
        tenant_id=tenant_id,
        reference=numbering.next_reference(db, tenant_id, numbering.RECEIPT, Receipt),
        order_id=payload.order_id,
        supplier_id=supplier_id,
        received_at=payload.received_at,
        delivery_note_number=payload.delivery_note_number,
        device_info=payload.device_info,
        status=reception_service.DRAFT,
        received_by=user_id,
        notes=payload.notes,
        file_url=payload.file_url,
    )
    db.add(receipt)
    db.flush()
    _replace_lines(db, tenant_id, receipt, payload.lines or [])
    db.commit()
    db.refresh(receipt)
    return receipt


def _replace_lines(db: Session, tenant_id: str, receipt: Receipt, lines) -> None:
    db.query(ReceiptLine).filter(
        ReceiptLine.tenant_id == tenant_id, ReceiptLine.receipt_id == receipt.id
    ).delete(synchronize_session=False)
    for l in lines:
        row = ReceiptLine(
            tenant_id=tenant_id,
            receipt_id=receipt.id,
            order_line_id=l.order_line_id,
            product_id=l.product_id,
            description=l.description,
            qty_delivered=l.qty_delivered,
            unit_id=l.unit_id,
            unit_price=l.unit_price,
            pack_size=l.pack_size,
            substituted_product_id=l.substituted_product_id,
            notes=l.notes,
        )
        db.add(row)
        db.flush()  # besoin de l'id pour les anomalies et les photos
        for i in l.issues or []:
            db.add(
                ReceiptLineIssue(
                    tenant_id=tenant_id,
                    receipt_line_id=row.id,
                    qty=i.qty,
                    reason=i.reason,
                    outcome=i.outcome,
                    notes=i.notes,
                )
            )
        for ph in l.photos or []:
            db.add(
                ReceiptLinePhoto(
                    tenant_id=tenant_id,
                    receipt_line_id=row.id,
                    url=ph.url,
                    caption=ph.caption,
                )
            )


def update(db: Session, tenant_id: str, receipt: Receipt, payload) -> Receipt:
    for field in (
        "received_at",
        "delivery_note_number",
        "notes",
        "file_url",
        "supplier_id",
        "device_info",
    ):
        value = getattr(payload, field, None)
        if value is not None:
            setattr(receipt, field, value)
    if payload.lines is not None:
        _replace_lines(db, tenant_id, receipt, payload.lines)
    db.commit()
    db.refresh(receipt)
    return receipt


def get(db: Session, tenant_id: str, receipt_id: str) -> Optional[Receipt]:
    return (
        db.query(Receipt)
        .filter(Receipt.tenant_id == tenant_id, Receipt.id == receipt_id)
        .first()
    )


def list_receipts(
    db: Session,
    tenant_id: str,
    order_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 200,
) -> List[Dict[str, Any]]:
    q = (
        db.query(Receipt, Supplier.name, PurchaseOrder.reference)
        .outerjoin(Supplier, Supplier.id == Receipt.supplier_id)
        .outerjoin(PurchaseOrder, PurchaseOrder.id == Receipt.order_id)
        .filter(Receipt.tenant_id == tenant_id)
    )
    if order_id:
        q = q.filter(Receipt.order_id == order_id)
    if status:
        q = q.filter(Receipt.status == status)
    rows = q.order_by(Receipt.created_at.desc()).limit(limit).all()
    ids = [r.id for r, _, _ in rows]
    counts = {}
    if ids:
        from sqlalchemy import func

        counts = dict(
            db.query(ReceiptLine.receipt_id, func.count(ReceiptLine.id))
            .filter(ReceiptLine.receipt_id.in_(ids))
            .group_by(ReceiptLine.receipt_id)
            .all()
        )
    names = _user_names(db, [r.received_by for r, _, _ in rows] + [r.checked_by for r, _, _ in rows])
    return [
        _head(r, sup, order_ref, counts.get(r.id, 0), names) for r, sup, order_ref in rows
    ]


def _user_names(db: Session, ids) -> Dict[Any, str]:
    wanted = [i for i in ids if i]
    if not wanted:
        return {}
    return {
        u.id: (u.name or u.email)
        for u in db.query(User).filter(User.id.in_(wanted)).all()
    }


def _head(
    receipt: Receipt,
    supplier_name: Optional[str],
    order_reference: Optional[str],
    line_count: int,
    user_names: Dict[Any, str],
) -> Dict[str, Any]:
    return {
        "id": str(receipt.id),
        "reference": receipt.reference,
        "order_id": str(receipt.order_id) if receipt.order_id else None,
        "order_reference": order_reference,
        "supplier_id": str(receipt.supplier_id) if receipt.supplier_id else None,
        "supplier_name": supplier_name,
        "received_at": receipt.received_at,
        "delivery_note_number": receipt.delivery_note_number,
        "status": receipt.status,
        "status_label": STATUS_LABELS.get(receipt.status or "", receipt.status),
        "received_by": str(receipt.received_by) if receipt.received_by else None,
        # « Qui a signé ce bon de livraison ? » est la question posée trois
        # semaines plus tard, quand le fournisseur conteste un manquant.
        "received_by_name": user_names.get(receipt.received_by),
        "checked_at": receipt.checked_at,
        "checked_by_name": user_names.get(receipt.checked_by),
        "device_info": receipt.device_info,
        "notes": receipt.notes,
        "file_url": receipt.file_url,
        "line_count": line_count,
        "created_at": receipt.created_at,
    }


def detail(db: Session, tenant_id: str, receipt: Receipt) -> Dict[str, Any]:
    supplier_name = (
        db.query(Supplier.name).filter(Supplier.id == receipt.supplier_id).scalar()
        if receipt.supplier_id
        else None
    )
    order_reference = (
        db.query(PurchaseOrder.reference).filter(PurchaseOrder.id == receipt.order_id).scalar()
        if receipt.order_id
        else None
    )
    lines = (
        db.query(ReceiptLine)
        .filter(ReceiptLine.tenant_id == tenant_id, ReceiptLine.receipt_id == receipt.id)
        .order_by(ReceiptLine.created_at)
        .all()
    )
    product_ids = [l.product_id for l in lines if l.product_id] + [
        l.substituted_product_id for l in lines if l.substituted_product_id
    ]
    names = (
        dict(db.query(Product.id, Product.name).filter(Product.id.in_(product_ids)).all())
        if product_ids
        else {}
    )
    head = _head(
        receipt,
        supplier_name,
        order_reference,
        len(lines),
        _user_names(db, [receipt.received_by, receipt.checked_by]),
    )
    out = []
    for l in lines:
        # La répartition accepté / refusé / détruit et l'état de la ligne sont
        # CALCULÉS par le service : les recalculer ici, ou pire les stocker,
        # créerait une seconde vérité.
        quality = reception_service.line_quality(reception_service.line_to_dict(l))
        out.append(
            {
                "id": str(l.id),
                "order_line_id": str(l.order_line_id) if l.order_line_id else None,
                "product_id": str(l.product_id) if l.product_id else None,
                "product_name": names.get(l.product_id),
                "description": l.description,
                "qty_delivered": _f(l.qty_delivered),
                "qty_accepted": quality["qty_accepted"],
                "qty_rejected": quality["qty_rejected"],
                "qty_destroyed": quality["qty_destroyed"],
                "state": quality["state"],
                "state_label": quality["state_label"],
                "unit_id": l.unit_id,
                "unit_price": _f(l.unit_price),
                "pack_size": l.pack_size,
                "substituted_product_id": str(l.substituted_product_id)
                if l.substituted_product_id
                else None,
                "substituted_product_name": names.get(l.substituted_product_id),
                "notes": l.notes,
                "issues": [
                    {
                        "id": str(i.id),
                        "qty": _f(i.qty),
                        "reason": i.reason,
                        "reason_label": reception_service.REASON_LABELS.get(
                            i.reason or "", i.reason
                        ),
                        "outcome": i.outcome,
                        "outcome_label": reception_service.OUTCOME_LABELS.get(
                            i.outcome or "", i.outcome
                        ),
                        "notes": i.notes,
                    }
                    for i in (l.issues or [])
                ],
                "photos": [
                    {"id": str(p.id), "url": p.url, "caption": p.caption}
                    for p in (l.photos or [])
                ],
            }
        )
    head["lines"] = out
    return head


def delete(db: Session, receipt: Receipt) -> None:
    db.delete(receipt)
    db.commit()
