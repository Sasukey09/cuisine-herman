from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_tenant_id, get_current_user, require_admin
from app.db.session import get_db
from app.models.models import User
from app.schemas.schemas import AuditLogRead, DeleteOrganizationRequest
from app.services.rgpd import service as rgpd

router = APIRouter()


@router.get("/export")
def api_export_data(
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _: list = Depends(require_admin),
) -> Dict[str, Any]:
    """RGPD art. 15 & 20 — everything we hold on this organization, as JSON.

    Portability means the customer can walk away with their data and load it
    elsewhere, not that they receive a PDF they cannot use. Password hashes are
    excluded: they are ours to protect, not theirs to carry.
    """
    payload = rgpd.export_organization(db, tenant_id)
    rgpd.record(
        db, tenant_id, str(current_user.id), rgpd.ACTION_DATA_EXPORTED,
        {"tables": len(payload)},
    )
    return payload


@router.get("/audit", response_model=List[AuditLogRead])
def api_audit_log(
    limit: int = 200,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    _: list = Depends(require_admin),
):
    """RGPD art. 30 — who did what, and when.

    The `audit_logs` table has existed since the first migration and had never
    been written to, nor read.
    """
    return rgpd.list_audit(db, tenant_id, limit=min(limit, 500))


@router.post("/delete-organization", status_code=204)
def api_delete_organization(
    payload: DeleteOrganizationRequest,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _: list = Depends(require_admin),
):
    """RGPD art. 17 — right to erasure. Irreversible.

    The caller must retype the organization's exact name. This is not
    bureaucracy: it is the only thing between a mis-click and every invoice,
    recipe and price this restaurant has ever recorded.
    """
    from app.models.models import Organization

    org = db.query(Organization).filter(Organization.id == tenant_id).first()
    if org is None:
        raise HTTPException(status_code=404, detail="Organisation introuvable")

    if (payload.confirm_name or "").strip() != (org.name or "").strip():
        raise HTTPException(
            status_code=400,
            detail=(
                "Le nom saisi ne correspond pas. Retapez exactement le nom de "
                "l'organisation pour confirmer la suppression définitive."
            ),
        )

    # Written BEFORE: afterwards there is no organization left to attach it to,
    # and "we erased everything" is exactly the event you must still be able to
    # prove a year later.
    rgpd.record(
        db, tenant_id, str(current_user.id), rgpd.ACTION_ORG_DELETED,
        {"organization": org.name, "requested_by": current_user.email},
    )
    rgpd.delete_organization(db, tenant_id)
