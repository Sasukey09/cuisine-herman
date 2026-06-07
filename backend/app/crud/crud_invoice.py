from sqlalchemy.orm import Session
from app.models.models import Invoice
from fastapi import UploadFile
import uuid


def create_invoice_from_upload(db: Session, file: UploadFile, tenant_id: str) -> dict:
    """Create the invoice row. The file itself is stored separately by the
    endpoint (storage key persisted via set_invoice_file_url)."""
    inv = Invoice(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        parsed=False,
    )
    db.add(inv)
    db.commit()
    db.refresh(inv)
    return {"id": str(inv.id), "status": "uploaded"}


def set_invoice_file_url(db: Session, invoice_id: str, tenant_id: str, file_url):
    inv = get_invoice(db, invoice_id, tenant_id)
    if inv is None:
        return None
    inv.file_url = file_url
    db.commit()
    db.refresh(inv)
    return inv


def set_invoice_ocr_status(db: Session, invoice_id: str, tenant_id: str, status: str):
    inv = get_invoice(db, invoice_id, tenant_id)
    if inv is None:
        return None
    inv.ocr_status = status
    db.commit()
    db.refresh(inv)
    return inv


def update_invoice(db: Session, invoice_id: str, tenant_id: str, **fields):
    inv = get_invoice(db, invoice_id, tenant_id)
    if inv is None:
        return None
    for key in ("invoice_number", "date", "total_amount", "currency", "supplier_id"):
        if key in fields and fields[key] is not None:
            setattr(inv, key, fields[key])
    db.commit()
    db.refresh(inv)
    return inv


def get_invoice(db: Session, invoice_id: str, tenant_id: str):
    return (
        db.query(Invoice)
        .filter(Invoice.id == invoice_id, Invoice.tenant_id == tenant_id)
        .first()
    )


def list_invoices(db: Session, tenant_id: str, skip: int = 0, limit: int = 50):
    return (
        db.query(Invoice)
        .filter(Invoice.tenant_id == tenant_id)
        .order_by(Invoice.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
