"""Dashboard read-models (Sprint 6).

Aggregations over the data produced by the invoice->price->cost pipeline:
- cost trends      : recipe cost snapshots over time
- top products     : biggest spend from invoice lines
- price trends     : price history of a single product
- margin alerts    : recipes whose latest food-cost % exceeds a threshold
"""
from typing import Optional, List, Dict, Any
from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.models import (
    Product,
    Invoice,
    InvoiceLine,
    ProductPrice,
    Recipe,
    RecipeVersion,
    RecipeCost,
)


def _f(v, default=None):
    return float(v) if v is not None else default


def cost_trends(
    db: Session,
    tenant_id: str,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    recipe_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    q = (
        db.query(
            RecipeCost.computed_at,
            RecipeCost.computed_cost_total,
            RecipeCost.cost_per_portion,
            RecipeCost.food_cost_pct,
            Recipe.id.label("recipe_id"),
            Recipe.name.label("recipe_name"),
            RecipeVersion.id.label("recipe_version_id"),
        )
        .join(RecipeVersion, RecipeVersion.id == RecipeCost.recipe_version_id)
        .join(Recipe, Recipe.id == RecipeVersion.recipe_id)
        .filter(Recipe.tenant_id == tenant_id)
    )
    if recipe_id:
        q = q.filter(Recipe.id == recipe_id)
    if date_from:
        q = q.filter(RecipeCost.computed_at >= date_from)
    if date_to:
        q = q.filter(RecipeCost.computed_at <= date_to)
    q = q.order_by(RecipeCost.computed_at.asc())

    return [
        {
            "computed_at": r.computed_at,
            "recipe_id": str(r.recipe_id),
            "recipe_name": r.recipe_name,
            "recipe_version_id": str(r.recipe_version_id),
            "computed_cost_total": _f(r.computed_cost_total),
            "cost_per_portion": _f(r.cost_per_portion),
            "food_cost_pct": _f(r.food_cost_pct),
        }
        for r in q.all()
    ]


def top_products(
    db: Session,
    tenant_id: str,
    limit: int = 10,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> List[Dict[str, Any]]:
    q = (
        db.query(
            Product.id.label("product_id"),
            Product.name.label("name"),
            func.coalesce(func.sum(InvoiceLine.line_total), 0).label("total_spend"),
            func.coalesce(func.sum(InvoiceLine.qty), 0).label("total_qty"),
            func.count(InvoiceLine.id).label("line_count"),
        )
        .join(InvoiceLine, InvoiceLine.product_id == Product.id)
        .join(Invoice, Invoice.id == InvoiceLine.invoice_id)
        .filter(Invoice.tenant_id == tenant_id)
    )
    if date_from:
        q = q.filter(Invoice.date >= date_from)
    if date_to:
        q = q.filter(Invoice.date <= date_to)
    q = q.group_by(Product.id, Product.name).order_by(
        func.coalesce(func.sum(InvoiceLine.line_total), 0).desc()
    ).limit(limit)

    return [
        {
            "product_id": str(r.product_id),
            "name": r.name,
            "total_spend": _f(r.total_spend, 0.0),
            "total_qty": _f(r.total_qty, 0.0),
            "line_count": int(r.line_count),
        }
        for r in q.all()
    ]


def price_trends(
    db: Session,
    tenant_id: str,
    product_id: str,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> List[Dict[str, Any]]:
    q = db.query(ProductPrice).filter(
        ProductPrice.tenant_id == tenant_id,
        ProductPrice.product_id == product_id,
    )
    if date_from:
        q = q.filter(ProductPrice.effective_date >= date_from)
    if date_to:
        q = q.filter(ProductPrice.effective_date <= date_to)
    q = q.order_by(ProductPrice.effective_date.asc())

    return [
        {
            "effective_date": p.effective_date,
            "price": _f(p.price),
            "currency": p.currency,
            "supplier_id": str(p.supplier_id) if p.supplier_id else None,
        }
        for p in q.all()
    ]


def select_low_margin(rows: List[Dict[str, Any]], max_food_cost_pct: float) -> List[Dict[str, Any]]:
    """Pure: keep the latest snapshot per recipe version, then those over threshold.

    ``rows`` are cost-trend dicts (computed_at, recipe_version_id, food_cost_pct, ...).
    """
    latest: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        vid = r["recipe_version_id"]
        prev = latest.get(vid)
        if prev is None or (r["computed_at"] and prev["computed_at"] and r["computed_at"] > prev["computed_at"]):
            latest[vid] = r
    alerts = [
        r
        for r in latest.values()
        if r.get("food_cost_pct") is not None and r["food_cost_pct"] > max_food_cost_pct
    ]
    return sorted(alerts, key=lambda r: r["food_cost_pct"], reverse=True)


def margin_alerts(
    db: Session, tenant_id: str, max_food_cost_pct: float = 35.0
) -> List[Dict[str, Any]]:
    rows = cost_trends(db, tenant_id)
    return select_low_margin(rows, max_food_cost_pct)


def price_alerts(
    db: Session, tenant_id: str, min_increase_pct: float = 10.0
) -> List[Dict[str, Any]]:
    """Products whose latest price rose by >= ``min_increase_pct`` vs the previous one."""
    rows = (
        db.query(ProductPrice, Product.name.label("product_name"))
        .outerjoin(Product, Product.id == ProductPrice.product_id)
        .filter(ProductPrice.tenant_id == tenant_id, ProductPrice.product_id.isnot(None))
        .order_by(
            ProductPrice.product_id,
            ProductPrice.effective_date.desc(),
            ProductPrice.created_at.desc(),
        )
        .all()
    )

    # keep the two most recent prices per product
    latest_two: Dict[str, List] = {}
    for price, name in rows:
        pid = str(price.product_id)
        bucket = latest_two.setdefault(pid, [])
        if len(bucket) < 2:
            bucket.append((price, name))

    alerts: List[Dict[str, Any]] = []
    for pid, items in latest_two.items():
        if len(items) < 2:
            continue
        (latest, name), (previous, _) = items[0], items[1]
        lp, pp = _f(latest.price), _f(previous.price)
        if not pp or pp <= 0 or lp is None:
            continue
        change = (lp - pp) / pp * 100.0
        if change >= min_increase_pct:
            alerts.append(
                {
                    "product_id": pid,
                    "product_name": name,
                    "previous_price": pp,
                    "latest_price": lp,
                    "change_pct": round(change, 1),
                    "currency": latest.currency,
                    "effective_date": latest.effective_date,
                    "supplier_id": str(latest.supplier_id) if latest.supplier_id else None,
                }
            )

    return sorted(alerts, key=lambda a: a["change_pct"], reverse=True)
