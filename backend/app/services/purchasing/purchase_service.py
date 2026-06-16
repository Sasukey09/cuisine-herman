"""Record purchases, raise price/margin alerts, and shape price analytics."""
import os
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.models import (
    Unit,
    Product,
    Supplier,
    Recipe,
    RecipeVersion,
    RecipeIngredient,
    RecipeCost,
)
from app.crud import crud_purchase
from app.core import metrics

# Minimum |variation| (%) on the standardized unit cost to raise a price alert,
# and minimum cost/portion rise (%) to raise a recipe margin alert.
PRICE_VARIATION_THRESHOLD_PCT = float(os.getenv("PRICE_VARIATION_THRESHOLD_PCT", "5"))
MARGIN_COST_THRESHOLD_PCT = float(os.getenv("MARGIN_COST_THRESHOLD_PCT", "5"))


def _f(v) -> Optional[float]:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _safe_rollback(db) -> None:
    try:
        db.rollback()
    except Exception:
        pass


def _unit_info(db: Session, unit_id) -> tuple:
    """(code, ratio_to_base) for a unit id, or (None, 1.0)."""
    if unit_id is None:
        return None, 1.0
    u = db.query(Unit).filter(Unit.id == unit_id).first()
    if u is None:
        return None, 1.0
    return u.code, float(u.ratio_to_base or 1) or 1.0


# --------------------------------------------------------------------------- #
# import-time recording (called from invoice_pricing)
# --------------------------------------------------------------------------- #
def record_purchase(db: Session, tenant_id: str, line, invoice) -> Dict[str, Any]:
    """Create a purchase_history row from a matched+priced invoice line, compute
    the variation vs the previous purchase (same product + supplier), and raise a
    price alert when the move exceeds the threshold. Best-effort: never raises."""
    if not getattr(line, "product_id", None) or line.unit_price is None:
        return {}
    try:
        product_id = str(line.product_id)
        supplier_id = str(invoice.supplier_id) if invoice.supplier_id else None
        unit_code, ratio = _unit_info(db, line.unit_id)
        unit_price = _f(line.unit_price)
        qty = _f(line.qty)
        total = _f(line.line_total)
        if total is None and qty is not None and unit_price is not None:
            total = round(qty * unit_price, 4)
        std = round(unit_price / ratio, 6) if (unit_price is not None and ratio) else unit_price

        # idempotent per line: re-pricing/editing a line replaces its row
        crud_purchase.delete_for_line(db, tenant_id, str(line.id))

        prev = crud_purchase.last_purchase(
            db, tenant_id, product_id, supplier_id, exclude_line_id=str(line.id)
        )
        variation = None
        prev_std = _f(prev.unit_cost_standard) if prev else None
        if prev_std and prev_std > 0 and std is not None:
            variation = round((std - prev_std) / prev_std * 100.0, 2)

        crud_purchase.create_purchase(
            db,
            tenant_id=tenant_id,
            product_id=product_id,
            supplier_id=supplier_id,
            invoice_id=str(invoice.id),
            invoice_line_id=str(line.id),
            invoice_number=invoice.invoice_number,
            purchase_date=invoice.date,
            qty=qty,
            unit_id=line.unit_id,
            unit_code=unit_code,
            unit_price=unit_price,
            total_price=total,
            unit_cost_standard=std,
            currency=invoice.currency,
            variation_pct=variation,
        )

        alert = None
        if variation is not None and abs(variation) >= PRICE_VARIATION_THRESHOLD_PCT:
            up = variation > 0
            pname = _name(db, Product, product_id)
            sname = _name(db, Supplier, supplier_id) if supplier_id else None
            msg = (
                f"{pname} : {'hausse' if up else 'baisse'} de {abs(variation):.1f}% "
                f"({prev_std:.2f} → {std:.2f}/{unit_code or 'u'}"
                + (f" chez {sname}" if sname else "")
                + ")"
            )
            crud_purchase.create_alert(
                db,
                tenant_id=tenant_id,
                type="price_increase" if up else "price_decrease",
                product_id=product_id,
                supplier_id=supplier_id,
                old_value=prev_std,
                new_value=std,
                change_pct=variation,
                message=msg,
            )
            metrics.PRICE_CHANGES_DETECTED.inc()
            alert = msg
        return {"variation_pct": variation, "alert": alert, "raised_increase": bool(variation and variation > 0)}
    except Exception:
        # analytics must never break the invoice pipeline
        _safe_rollback(db)
        return {}


def detect_margin_alerts(db: Session, tenant_id: str, product_id: str) -> List[str]:
    """After a product price change + recipe recompute, raise a margin alert for
    each recipe whose cost/portion rose by >= MARGIN_COST_THRESHOLD_PCT (compares
    the two most recent cost snapshots of the affected version)."""
    raised: List[str] = []
    try:
        versions = (
            db.query(RecipeVersion.id, Recipe.id, Recipe.name)
            .join(RecipeIngredient, RecipeIngredient.recipe_version_id == RecipeVersion.id)
            .join(Recipe, Recipe.id == RecipeVersion.recipe_id)
            .filter(RecipeIngredient.product_id == product_id, Recipe.tenant_id == tenant_id)
            .distinct()
            .all()
        )
        for version_id, recipe_id, recipe_name in versions:
            snaps = (
                db.query(RecipeCost)
                .filter(RecipeCost.recipe_version_id == version_id)
                .order_by(RecipeCost.computed_at.desc())
                .limit(2)
                .all()
            )
            if len(snaps) < 2:
                continue
            new_c, old_c = _f(snaps[0].cost_per_portion), _f(snaps[1].cost_per_portion)
            if not old_c or old_c <= 0 or new_c is None:
                continue
            rise = (new_c - old_c) / old_c * 100.0
            if rise >= MARGIN_COST_THRESHOLD_PCT:
                msg = (
                    f"{recipe_name} : coût/portion +{rise:.1f}% "
                    f"({old_c:.2f} → {new_c:.2f}) — marge sous pression"
                )
                crud_purchase.create_alert(
                    db,
                    tenant_id=tenant_id,
                    type="margin",
                    recipe_id=str(recipe_id),
                    old_value=old_c,
                    new_value=new_c,
                    change_pct=round(rise, 2),
                    message=msg,
                )
                raised.append(msg)
    except Exception:
        _safe_rollback(db)
    return raised


def _name(db: Session, model, obj_id) -> Optional[str]:
    if not obj_id:
        return None
    row = db.query(model.name).filter(model.id == obj_id).first()
    return row[0] if row else None


# --------------------------------------------------------------------------- #
# analytics (read)
# --------------------------------------------------------------------------- #
def _supplier_names(db: Session, tenant_id: str) -> Dict[str, str]:
    return {str(s.id): s.name for s in db.query(Supplier).filter(Supplier.tenant_id == tenant_id).all()}


def _product_names(db: Session, tenant_id: str) -> Dict[str, str]:
    return {str(p.id): p.name for p in db.query(Product.id, Product.name).filter(Product.tenant_id == tenant_id).all()}


def _row(p, supplier_names) -> Dict[str, Any]:
    return {
        "id": str(p.id),
        "purchase_date": p.purchase_date.isoformat() if p.purchase_date else None,
        "supplier_id": str(p.supplier_id) if p.supplier_id else None,
        "supplier_name": supplier_names.get(str(p.supplier_id)) if p.supplier_id else None,
        "qty": _f(p.qty),
        "unit_code": p.unit_code,
        "unit_price": _f(p.unit_price),
        "total_price": _f(p.total_price),
        "unit_cost_standard": _f(p.unit_cost_standard),
        "currency": p.currency,
        "variation_pct": _f(p.variation_pct),
    }


def product_price_history(db: Session, tenant_id: str, product_id: str) -> Dict[str, Any]:
    supplier_names = _supplier_names(db, tenant_id)
    rows = [_row(p, supplier_names) for p in crud_purchase.product_purchases(db, tenant_id, product_id)]
    return {"product_id": product_id, "purchases": rows, "count": len(rows)}


def supplier_comparison(db: Session, tenant_id: str, product_id: str) -> Dict[str, Any]:
    """Latest standardized cost per supplier; cheapest flagged."""
    supplier_names = _supplier_names(db, tenant_id)
    latest: Dict[str, Any] = {}
    for p in crud_purchase.product_purchases(db, tenant_id, product_id):  # asc -> last wins
        latest[str(p.supplier_id)] = p
    items = []
    for sid, p in latest.items():
        items.append(
            {
                "supplier_id": None if sid == "None" else sid,
                "supplier_name": supplier_names.get(sid),
                "unit_cost_standard": _f(p.unit_cost_standard),
                "unit_code": p.unit_code,
                "currency": p.currency,
                "purchase_date": p.purchase_date.isoformat() if p.purchase_date else None,
            }
        )
    priced = [i for i in items if i["unit_cost_standard"] is not None]
    priced.sort(key=lambda i: i["unit_cost_standard"])
    cheapest_id = priced[0]["supplier_id"] if priced else None
    for i in items:
        i["is_cheapest"] = (
            i["unit_cost_standard"] is not None
            and priced
            and i["unit_cost_standard"] == priced[0]["unit_cost_standard"]
        )
    return {"product_id": product_id, "suppliers": items, "cheapest_supplier_id": cheapest_id}


def supplier_purchase_history(db: Session, tenant_id: str, supplier_id: str) -> Dict[str, Any]:
    product_names = _product_names(db, tenant_id)
    rows = []
    for p in crud_purchase.supplier_purchases(db, tenant_id, supplier_id):
        rows.append(
            {
                "id": str(p.id),
                "purchase_date": p.purchase_date.isoformat() if p.purchase_date else None,
                "product_id": str(p.product_id) if p.product_id else None,
                "product_name": product_names.get(str(p.product_id)) if p.product_id else None,
                "qty": _f(p.qty),
                "unit_code": p.unit_code,
                "unit_price": _f(p.unit_price),
                "total_price": _f(p.total_price),
                "unit_cost_standard": _f(p.unit_cost_standard),
                "currency": p.currency,
                "variation_pct": _f(p.variation_pct),
            }
        )
    return {"supplier_id": supplier_id, "invoice_number": None, "purchases": rows, "count": len(rows)}


def price_dashboard(db: Session, tenant_id: str, limit: int = 5) -> Dict[str, Any]:
    """Most increased / decreased products (latest two standardized costs),
    supplier-switch savings opportunities, and recent recipe impacts."""
    product_names = _product_names(db, tenant_id)
    supplier_names = _supplier_names(db, tenant_id)

    by_product: Dict[str, List] = {}
    for p in crud_purchase.all_purchases(db, tenant_id):  # desc
        if not p.product_id:
            continue
        by_product.setdefault(str(p.product_id), []).append(p)

    movements: List[Dict[str, Any]] = []
    savings: List[Dict[str, Any]] = []
    for pid, purchases in by_product.items():
        # movement: latest two standardized costs
        if len(purchases) >= 2:
            new_c, old_c = _f(purchases[0].unit_cost_standard), _f(purchases[1].unit_cost_standard)
            if old_c and old_c > 0 and new_c is not None:
                change = round((new_c - old_c) / old_c * 100.0, 1)
                movements.append(
                    {
                        "product_id": pid,
                        "product_name": product_names.get(pid),
                        "old_cost": old_c,
                        "new_cost": new_c,
                        "change_pct": change,
                        "unit_code": purchases[0].unit_code,
                    }
                )
        # savings: latest cost per supplier -> gap to cheapest
        latest_by_sup: Dict[str, Any] = {}
        for p in reversed(purchases):  # asc so last wins
            latest_by_sup[str(p.supplier_id)] = p
        costs = [(_f(p.unit_cost_standard), p) for p in latest_by_sup.values() if _f(p.unit_cost_standard) is not None]
        if len(costs) >= 2:
            costs.sort(key=lambda c: c[0])
            cheapest, current_max = costs[0], costs[-1]
            gap = current_max[0] - cheapest[0]
            if gap > 0:
                savings.append(
                    {
                        "product_id": pid,
                        "product_name": product_names.get(pid),
                        "cheapest_supplier": supplier_names.get(str(cheapest[1].supplier_id)),
                        "cheapest_cost": cheapest[0],
                        "current_max_cost": current_max[0],
                        "saving_per_unit": round(gap, 4),
                        "saving_pct": round(gap / current_max[0] * 100.0, 1) if current_max[0] else None,
                        "unit_code": cheapest[1].unit_code,
                    }
                )

    increased = sorted([m for m in movements if m["change_pct"] > 0], key=lambda m: m["change_pct"], reverse=True)
    decreased = sorted([m for m in movements if m["change_pct"] < 0], key=lambda m: m["change_pct"])
    savings.sort(key=lambda s: s["saving_per_unit"], reverse=True)

    recipe_impact = [
        {
            "recipe_id": str(a.recipe_id) if a.recipe_id else None,
            "message": a.message,
            "change_pct": _f(a.change_pct),
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in crud_purchase.list_alerts(db, tenant_id, limit=50)
        if a.type == "margin"
    ][:limit]

    return {
        "most_increased": increased[:limit],
        "most_decreased": decreased[:limit],
        "savings_opportunities": savings[:limit],
        "potential_savings_total": round(sum(s["saving_per_unit"] for s in savings), 4),
        "recipe_impact": recipe_impact,
    }


def list_price_alerts(db: Session, tenant_id: str, unread_only: bool = False) -> List[Dict[str, Any]]:
    product_names = _product_names(db, tenant_id)
    out = []
    for a in crud_purchase.list_alerts(db, tenant_id, unread_only=unread_only):
        out.append(
            {
                "id": str(a.id),
                "type": a.type,
                "product_id": str(a.product_id) if a.product_id else None,
                "product_name": product_names.get(str(a.product_id)) if a.product_id else None,
                "recipe_id": str(a.recipe_id) if a.recipe_id else None,
                "old_value": _f(a.old_value),
                "new_value": _f(a.new_value),
                "change_pct": _f(a.change_pct),
                "message": a.message,
                "is_read": bool(a.is_read),
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
        )
    return out
