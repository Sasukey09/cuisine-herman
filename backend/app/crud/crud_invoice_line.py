import uuid
from sqlalchemy.orm import Session

from app.models.models import InvoiceLine, Invoice


def create_invoice_line(db: Session, invoice_id: str, **kwargs) -> InvoiceLine:
    line = InvoiceLine(id=str(uuid.uuid4()), invoice_id=invoice_id, **kwargs)
    db.add(line)
    db.commit()
    db.refresh(line)
    return line


def list_lines(db: Session, invoice_id: str):
    return db.query(InvoiceLine).filter(InvoiceLine.invoice_id == invoice_id).all()


def get_line(db: Session, tenant_id: str, line_id: str) -> InvoiceLine:
    """Fetch a line, scoped to tenant via its parent invoice."""
    return (
        db.query(InvoiceLine)
        .join(Invoice, Invoice.id == InvoiceLine.invoice_id)
        .filter(InvoiceLine.id == line_id, Invoice.tenant_id == tenant_id)
        .first()
    )
