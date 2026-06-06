import uuid
from sqlalchemy.orm import Session

from app.models.models import User, Organization
from app.core import security


def get_user_by_email(db: Session, email: str):
    return db.query(User).filter(User.email == email).first()


def list_users(db: Session, tenant_id: str):
    return (
        db.query(User)
        .filter(User.tenant_id == tenant_id)
        .order_by(User.created_at.asc())
        .all()
    )


def create_user(db: Session, tenant_id: str, email: str, password: str, name: str = None) -> User:
    user = User(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        email=email,
        password_hash=security.get_password_hash(password),
        name=name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_organization(db: Session, name: str) -> Organization:
    org = Organization(id=str(uuid.uuid4()), name=name)
    db.add(org)
    db.commit()
    db.refresh(org)
    return org
