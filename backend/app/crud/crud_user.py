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


# --- Social login (Google / Apple), no Firebase ---------------------------- #
def get_by_provider(db: Session, provider: str, subject: str):
    """Find a user previously linked to this provider identity (meta.providers)."""
    return (
        db.query(User)
        .filter(User.meta["providers"][provider].astext == subject)
        .first()
    )


def _with_provider(meta, provider: str, subject: str) -> dict:
    meta = dict(meta or {})
    providers = dict(meta.get("providers") or {})
    providers[provider] = subject
    meta["providers"] = providers
    return meta


def link_provider(db: Session, user: User, provider: str, subject: str) -> User:
    """Attach a provider identity to an existing user (e.g. an email/password
    account signing in with Google for the first time). Idempotent."""
    if (user.meta or {}).get("providers", {}).get(provider) == subject:
        return user
    user.meta = _with_provider(user.meta, provider, subject)  # reassign so ORM tracks it
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_social_user(db: Session, tenant_id: str, email: str, name: str,
                        provider: str, subject: str) -> User:
    """Create a password-less account authenticated via a social provider."""
    user = User(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        email=email,
        password_hash=None,   # social-only: never logs in with a password
        name=name,
        meta={"providers": {provider: subject}},
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
