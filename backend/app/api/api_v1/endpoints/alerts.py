from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_current_tenant_id, require_writer
from app.crud import crud_purchase
from app.services.purchasing import purchase_service

router = APIRouter()


@router.get("/prices")
def api_price_alerts(
    unread_only: bool = False,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Persisted price/margin alerts (newest first)."""
    return purchase_service.list_price_alerts(db, tenant_id, unread_only=unread_only)


@router.post("/{alert_id}/read", status_code=204)
def api_mark_alert_read(
    alert_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    _: list = Depends(require_writer),
):
    if crud_purchase.mark_alert_read(db, tenant_id, alert_id) is None:
        raise HTTPException(status_code=404, detail="Alert not found")
