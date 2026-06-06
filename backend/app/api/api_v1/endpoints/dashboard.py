from typing import List, Optional
from datetime import date
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_current_tenant_id
from app.schemas.schemas import (
    CostTrendPoint,
    TopProduct,
    PriceTrendPoint,
    MarginAlert,
    PriceAlert,
)
from app.services.dashboard import dashboard_service

router = APIRouter()


@router.get("/cost-trends", response_model=List[CostTrendPoint])
def api_cost_trends(
    date_from: Optional[date] = Query(None, alias="from"),
    date_to: Optional[date] = Query(None, alias="to"),
    recipe_id: Optional[str] = None,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
):
    return dashboard_service.cost_trends(db, tenant_id, date_from, date_to, recipe_id)


@router.get("/top-products", response_model=List[TopProduct])
def api_top_products(
    limit: int = 10,
    date_from: Optional[date] = Query(None, alias="from"),
    date_to: Optional[date] = Query(None, alias="to"),
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
):
    return dashboard_service.top_products(db, tenant_id, limit, date_from, date_to)


@router.get("/price-trends", response_model=List[PriceTrendPoint])
def api_price_trends(
    product_id: str,
    date_from: Optional[date] = Query(None, alias="from"),
    date_to: Optional[date] = Query(None, alias="to"),
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
):
    return dashboard_service.price_trends(db, tenant_id, product_id, date_from, date_to)


@router.get("/margin-alerts", response_model=List[MarginAlert])
def api_margin_alerts(
    max_food_cost_pct: float = 35.0,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
):
    return dashboard_service.margin_alerts(db, tenant_id, max_food_cost_pct)


@router.get("/price-alerts", response_model=List[PriceAlert])
def api_price_alerts(
    min_increase_pct: float = 10.0,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
):
    return dashboard_service.price_alerts(db, tenant_id, min_increase_pct)
