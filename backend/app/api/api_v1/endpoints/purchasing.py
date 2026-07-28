from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_current_tenant_id
from app.services.purchasing import kpi_service

router = APIRouter()


@router.get("/kpi")
def api_purchasing_kpi(
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Pilotage Achats : KPI tenant-wide (12 mois), assemblés depuis les moteurs
    Achats existants. Lecture seule."""
    return kpi_service.purchasing_kpi(db, tenant_id, date.today())
