import uuid
from typing import Dict, List
from sqlalchemy.orm import Session

from app.models.models import Role, UserRole

# Built-in role hierarchy for a tenant.
DEFAULT_ROLES = {
    "admin": "Full access incl. user management",
    "manager": "Read + write business data",
    "viewer": "Read-only",
}
WRITER_ROLES = {"admin", "manager"}


def ensure_default_roles(db: Session, tenant_id: str) -> Dict[str, Role]:
    """Create the built-in roles for a tenant if missing; return name -> Role."""
    existing = {
        r.name: r for r in db.query(Role).filter(Role.tenant_id == tenant_id).all()
    }
    created = False
    for name, desc in DEFAULT_ROLES.items():
        if name not in existing:
            role = Role(id=str(uuid.uuid4()), tenant_id=tenant_id, name=name, description=desc)
            db.add(role)
            existing[name] = role
            created = True
    if created:
        db.commit()
        for r in existing.values():
            db.refresh(r)
    return existing


def assign_role(db: Session, user_id: str, role_id: str) -> None:
    db.add(UserRole(id=str(uuid.uuid4()), user_id=user_id, role_id=role_id))
    db.commit()


def get_user_role_names(db: Session, user_id: str, tenant_id: str) -> List[str]:
    rows = (
        db.query(Role.name)
        .join(UserRole, UserRole.role_id == Role.id)
        .filter(UserRole.user_id == user_id, Role.tenant_id == tenant_id)
        .all()
    )
    return [r.name for r in rows]
