import re
import uuid
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.models import CustomField

_VALID_TARGETS = {"product", "recipe"}
_VALID_TYPES = {"text", "number", "boolean", "select"}


def slugify(label: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", (label or "").strip().lower()).strip("_")
    return s or "champ"


def create_field(
    db: Session,
    tenant_id: str,
    label: str,
    target: str,
    field_type: str,
    key: Optional[str] = None,
    options: Optional[List[str]] = None,
    required: bool = False,
    description: Optional[str] = None,
) -> CustomField:
    obj = CustomField(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        name=label,
        target_entity=target,
        schema={
            "key": key or slugify(label),
            "type": field_type,
            "options": options or [],
            "required": bool(required),
            "description": description,
        },
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def list_fields(db: Session, tenant_id: str, target: Optional[str] = None) -> List[CustomField]:
    q = db.query(CustomField).filter(CustomField.tenant_id == tenant_id)
    if target:
        q = q.filter(CustomField.target_entity == target)
    return q.order_by(CustomField.created_at.asc()).all()


def get_field(db: Session, tenant_id: str, field_id: str) -> Optional[CustomField]:
    return (
        db.query(CustomField)
        .filter(CustomField.id == field_id, CustomField.tenant_id == tenant_id)
        .first()
    )


def delete_field(db: Session, tenant_id: str, field_id: str) -> bool:
    obj = get_field(db, tenant_id, field_id)
    if obj is None:
        return False
    db.delete(obj)
    db.commit()
    return True
