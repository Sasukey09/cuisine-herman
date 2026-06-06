import uuid
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.models import CustomReport


def create_report(db: Session, tenant_id: str, name: str, definition: dict) -> CustomReport:
    obj = CustomReport(
        id=str(uuid.uuid4()), tenant_id=tenant_id, name=name, definition=definition
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def list_reports(db: Session, tenant_id: str) -> List[CustomReport]:
    return (
        db.query(CustomReport)
        .filter(CustomReport.tenant_id == tenant_id)
        .order_by(CustomReport.created_at.asc())
        .all()
    )


def get_report(db: Session, tenant_id: str, report_id: str) -> Optional[CustomReport]:
    return (
        db.query(CustomReport)
        .filter(CustomReport.id == report_id, CustomReport.tenant_id == tenant_id)
        .first()
    )


def update_report(
    db: Session, tenant_id: str, report_id: str, name: Optional[str], definition: Optional[dict]
) -> Optional[CustomReport]:
    obj = get_report(db, tenant_id, report_id)
    if obj is None:
        return None
    if name is not None:
        obj.name = name
    if definition is not None:
        obj.definition = definition
    db.commit()
    db.refresh(obj)
    return obj


def delete_report(db: Session, tenant_id: str, report_id: str) -> bool:
    obj = get_report(db, tenant_id, report_id)
    if obj is None:
        return False
    db.delete(obj)
    db.commit()
    return True
