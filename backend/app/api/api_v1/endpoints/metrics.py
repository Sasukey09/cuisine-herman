from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_current_tenant_id, require_writer
from app.schemas.schemas import (
    CustomMetricCreate,
    CustomMetricUpdate,
    CustomMetricRead,
    MetricVariable,
    MetricEvaluationResult,
)
from app.crud import crud_custom_metric
from app.services.customization import metrics_service

router = APIRouter()


def _to_read(m) -> dict:
    meta = m.meta or {}
    return {
        "id": str(m.id),
        "name": m.name,
        "formula": m.formula,
        "target": meta.get("target", "recipe"),
        "format": meta.get("format", "number"),
        "description": meta.get("description"),
    }


@router.get("/variables", response_model=List[MetricVariable])
def api_metric_variables(target: str = "recipe", _tenant: str = Depends(get_current_tenant_id)):
    """Variables available to formulas for a given domain (default: recipe)."""
    if target == "recipe":
        return metrics_service.RECIPE_VARIABLES
    return []


@router.get("/", response_model=List[CustomMetricRead])
def api_list_metrics(
    target: Optional[str] = None,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
):
    return [_to_read(m) for m in crud_custom_metric.list_metrics(db, tenant_id, target)]


@router.post("/", response_model=CustomMetricRead, status_code=201)
def api_create_metric(
    payload: CustomMetricCreate,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    _: list = Depends(require_writer),
):
    ok, error = metrics_service.validate_formula(payload.formula, payload.target)
    if not ok:
        raise HTTPException(status_code=400, detail=f"Formule invalide : {error}")
    m = crud_custom_metric.create_metric(
        db, tenant_id, payload.name.strip(), payload.formula.strip(),
        target=payload.target, fmt=payload.format, description=payload.description,
    )
    return _to_read(m)


@router.put("/{metric_id}", response_model=CustomMetricRead)
def api_update_metric(
    metric_id: str,
    payload: CustomMetricUpdate,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    _: list = Depends(require_writer),
):
    if payload.formula is not None:
        existing = crud_custom_metric.get_metric(db, tenant_id, metric_id)
        target = (existing.meta or {}).get("target", "recipe") if existing else "recipe"
        ok, error = metrics_service.validate_formula(payload.formula, target)
        if not ok:
            raise HTTPException(status_code=400, detail=f"Formule invalide : {error}")
    m = crud_custom_metric.update_metric(
        db, tenant_id, metric_id,
        name=payload.name, formula=payload.formula,
        format=payload.format, description=payload.description,
    )
    if m is None:
        raise HTTPException(status_code=404, detail="Indicateur introuvable")
    return _to_read(m)


@router.delete("/{metric_id}", status_code=204)
def api_delete_metric(
    metric_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    _: list = Depends(require_writer),
):
    if not crud_custom_metric.delete_metric(db, tenant_id, metric_id):
        raise HTTPException(status_code=404, detail="Indicateur introuvable")


@router.get("/evaluate/recipe/{recipe_id}", response_model=MetricEvaluationResult)
def api_evaluate_recipe(
    recipe_id: str,
    selling_price: Optional[float] = None,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Evaluate all recipe-scoped custom metrics for one recipe."""
    try:
        return metrics_service.evaluate_for_recipe(db, tenant_id, recipe_id, selling_price)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
