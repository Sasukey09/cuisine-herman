import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.models.models import CustomMetric


def create_metric(
    db: Session,
    tenant_id: str,
    name: str,
    formula: str,
    target: str = "recipe",
    fmt: str = "number",
    description: Optional[str] = None,
) -> CustomMetric:
    obj = CustomMetric(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        name=name,
        formula=formula,
        meta={"target": target, "format": fmt, "description": description},
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def list_metrics(db: Session, tenant_id: str, target: Optional[str] = None):
    q = db.query(CustomMetric).filter(CustomMetric.tenant_id == tenant_id)
    rows = q.order_by(CustomMetric.created_at.asc()).all()
    if target:
        rows = [r for r in rows if (r.meta or {}).get("target", "recipe") == target]
    return rows


def get_metric(db: Session, tenant_id: str, metric_id: str) -> Optional[CustomMetric]:
    return (
        db.query(CustomMetric)
        .filter(CustomMetric.id == metric_id, CustomMetric.tenant_id == tenant_id)
        .first()
    )


def update_metric(db: Session, tenant_id: str, metric_id: str, **fields) -> Optional[CustomMetric]:
    obj = get_metric(db, tenant_id, metric_id)
    if obj is None:
        return None
    if "name" in fields and fields["name"] is not None:
        obj.name = fields["name"]
    if "formula" in fields and fields["formula"] is not None:
        obj.formula = fields["formula"]
    meta = dict(obj.meta or {})
    for key in ("target", "format", "description"):
        if key in fields and fields[key] is not None:
            meta[key] = fields[key]
    obj.meta = meta
    db.commit()
    db.refresh(obj)
    return obj


def delete_metric(db: Session, tenant_id: str, metric_id: str) -> bool:
    obj = get_metric(db, tenant_id, metric_id)
    if obj is None:
        return False
    db.delete(obj)
    db.commit()
    return True
