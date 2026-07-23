from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_current_tenant_id, require_writer
from app.schemas.schemas import (
    ReportSource,
    ReportDefinition,
    CustomReportCreate,
    CustomReportUpdate,
    CustomReportRead,
    ReportRunResult,
)
from app.crud import crud_custom_report
from app.services.customization import reports_service

router = APIRouter()


def _to_read(r) -> dict:
    return {"id": str(r.id), "name": r.name, "definition": r.definition}


@router.get("/sources", response_model=List[ReportSource])
def api_report_sources(_tenant: str = Depends(get_current_tenant_id)):
    return reports_service.available_sources()


@router.get("/", response_model=List[CustomReportRead])
def api_list_reports(
    db: Session = Depends(get_db), tenant_id: str = Depends(get_current_tenant_id)
):
    return [_to_read(r) for r in crud_custom_report.list_reports(db, tenant_id)]


@router.post("/", response_model=CustomReportRead, status_code=201)
def api_create_report(
    payload: CustomReportCreate,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    _: list = Depends(require_writer),
):
    definition = payload.definition.model_dump()
    try:
        reports_service.validate_definition(definition)
    except reports_service.ReportError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    r = crud_custom_report.create_report(db, tenant_id, payload.name.strip(), definition)
    return _to_read(r)


@router.put("/{report_id}", response_model=CustomReportRead)
def api_update_report(
    report_id: str,
    payload: CustomReportUpdate,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    _: list = Depends(require_writer),
):
    definition = None
    if payload.definition is not None:
        definition = payload.definition.model_dump()
        try:
            reports_service.validate_definition(definition)
        except reports_service.ReportError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
    r = crud_custom_report.update_report(db, tenant_id, report_id, payload.name, definition)
    if r is None:
        raise HTTPException(status_code=404, detail="Rapport introuvable")
    return _to_read(r)


@router.delete("/{report_id}", status_code=204)
def api_delete_report(
    report_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    _: list = Depends(require_writer),
):
    if not crud_custom_report.delete_report(db, tenant_id, report_id):
        raise HTTPException(status_code=404, detail="Rapport introuvable")


@router.post("/run", response_model=ReportRunResult)
def api_run_adhoc(
    definition: ReportDefinition,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    _: list = Depends(require_writer),
):
    """Run an unsaved definition (live preview in the builder).

    Writer-gated like the rest of the report CRUD: running a report fans out to
    a per-product latest-price lookup (up to the source cap), so a read-only
    viewer must not be able to trigger it on repeat as a cheap DB-load amplifier.
    """
    try:
        return reports_service.run_report(db, tenant_id, definition.model_dump())
    except reports_service.ReportError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/{report_id}/run", response_model=ReportRunResult)
def api_run_saved(
    report_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    _: list = Depends(require_writer),
):
    report = crud_custom_report.get_report(db, tenant_id, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Rapport introuvable")
    try:
        return reports_service.run_report(db, tenant_id, report.definition)
    except reports_service.ReportError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
