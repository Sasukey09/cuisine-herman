"""RGPD: access, portability, erasure, traceability.

A French SaaS holding a restaurant's suppliers, invoices and staff accounts is a
data controller. Three obligations had no code at all:

* **Art. 15/20** — the customer can demand everything you hold on them, in a
  machine-readable form.
* **Art. 17** — the customer can demand it all be erased.
* **Art. 30** — you must be able to say *who* did *what*, and *when*.

The `audit_logs` table has existed since the first migration and had never been
written to, nor read. It is now the register.
"""
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.models import (
    AIConversation,
    AIMessage,
    AuditLog,
    Invoice,
    InvoiceLine,
    Organization,
    PriceAlert,
    Product,
    ProductPrice,
    PurchaseHistory,
    Recipe,
    RecipeIngredient,
    RecipeVersion,
    Supplier,
    User,
)

# Actions worth remembering. Deliberately short: an audit log nobody can read is
# noise, and noise is where a real event hides.
ACTION_LOGIN = "auth.login"
ACTION_LOGOUT = "auth.logout"
ACTION_USER_CREATED = "auth.user_created"
ACTION_PASSWORD_RESET = "auth.password_reset"
ACTION_DATA_EXPORTED = "rgpd.data_exported"
ACTION_ORG_DELETED = "rgpd.organization_deleted"


def record(
    db: Session,
    tenant_id: Optional[str],
    user_id: Optional[str],
    action: str,
    data: Optional[Dict[str, Any]] = None,
) -> None:
    """Write one line to the register. Never raises: an audit failure must not
    take down the action it was auditing."""
    try:
        db.add(
            AuditLog(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                user_id=user_id,
                action=action,
                data=data or {},
            )
        )
        db.commit()
    except Exception:
        db.rollback()


def list_audit(db: Session, tenant_id: str, limit: int = 200) -> List[AuditLog]:
    return (
        db.query(AuditLog)
        .filter(AuditLog.tenant_id == tenant_id)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .all()
    )


def _rows(db: Session, model, tenant_id: str) -> List[Dict[str, Any]]:
    out = []
    for row in db.query(model).filter(model.tenant_id == tenant_id).all():
        out.append(
            {
                c.name: (str(v) if isinstance(v := getattr(row, c.name), uuid.UUID) else v)
                for c in model.__table__.columns
            }
        )
    return out


def export_organization(db: Session, tenant_id: str) -> Dict[str, Any]:
    """Everything the platform holds for this organization, as plain JSON.

    Portability means the customer can walk away with their data and load it
    somewhere else — not that they receive a PDF they cannot use.
    Password hashes are excluded: they are ours to protect, not theirs to carry.
    """
    org = db.query(Organization).filter(Organization.id == tenant_id).first()

    users = []
    for u in db.query(User).filter(User.tenant_id == tenant_id).all():
        users.append(
            {
                "id": str(u.id),
                "email": u.email,
                "name": u.name,
                "created_at": u.created_at.isoformat() if u.created_at else None,
                "last_login": u.last_login.isoformat() if u.last_login else None,
                # password_hash deliberately omitted
            }
        )

    # Rows hanging off the tenant's own rows rather than carrying tenant_id.
    recipe_ids = [r.id for r in db.query(Recipe.id).filter(Recipe.tenant_id == tenant_id).all()]
    version_ids = [
        v.id
        for v in db.query(RecipeVersion.id)
        .filter(RecipeVersion.recipe_id.in_(recipe_ids))
        .all()
    ] if recipe_ids else []
    invoice_ids = [i.id for i in db.query(Invoice.id).filter(Invoice.tenant_id == tenant_id).all()]
    convo_ids = [
        c.id for c in db.query(AIConversation.id).filter(AIConversation.tenant_id == tenant_id).all()
    ]

    def _by_ids(model, column, ids):
        if not ids:
            return []
        return [
            {c.name: getattr(row, c.name) for c in model.__table__.columns}
            for row in db.query(model).filter(column.in_(ids)).all()
        ]

    return {
        "organization": {"id": str(org.id), "name": org.name} if org else None,
        "exported_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        "users": users,
        "suppliers": _rows(db, Supplier, tenant_id),
        "products": _rows(db, Product, tenant_id),
        "product_prices": _rows(db, ProductPrice, tenant_id),
        "invoices": _rows(db, Invoice, tenant_id),
        "invoice_lines": _by_ids(InvoiceLine, InvoiceLine.invoice_id, invoice_ids),
        "recipes": _rows(db, Recipe, tenant_id),
        "recipe_versions": _by_ids(RecipeVersion, RecipeVersion.recipe_id, recipe_ids),
        "recipe_ingredients": _by_ids(
            RecipeIngredient, RecipeIngredient.recipe_version_id, version_ids
        ),
        "purchase_history": _rows(db, PurchaseHistory, tenant_id),
        "price_alerts": _rows(db, PriceAlert, tenant_id),
        "ai_conversations": _rows(db, AIConversation, tenant_id),
        "ai_messages": _by_ids(AIMessage, AIMessage.conversation_id, convo_ids),
    }


def delete_organization(db: Session, tenant_id: str) -> bool:
    """Right to erasure (art. 17). Deletes the organization; the rest cascades.

    The audit rows have to go FIRST, for two reasons that point the same way:

    * their foreign keys (`tenant_id` → organizations, `user_id` → users) have no
      ON DELETE CASCADE, so they would simply **block** the deletion. This is not
      theoretical: the very act of logging in writes an audit row, so every real
      organization has some — the erasure endpoint could never have succeeded.
      A real-database test caught it; every mocked test had been green.
    * they are personal data themselves (who logged in, from which IP). Erasing
      the restaurant while keeping a log of its staff's connections would be a
      strange idea of erasure.

    The proof that the erasure happened is written afterwards by the caller, with
    a NULL tenant: there is no organization left to attach it to, yet "we erased
    everything, on this date, at this person's request" is exactly what you must
    still be able to show a year later.
    """
    org = db.query(Organization).filter(Organization.id == tenant_id).first()
    if org is None:
        return False

    db.query(AuditLog).filter(AuditLog.tenant_id == tenant_id).delete(
        synchronize_session=False
    )
    db.delete(org)
    db.commit()
    return True
