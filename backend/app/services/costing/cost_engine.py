"""Recipe cost engine (Decimal-based).

All monetary/quantity arithmetic is done with ``decimal.Decimal`` to avoid binary
float rounding errors. Results are converted to ``float`` only at the boundary
(JSON / DB), rounded the same way as before, so existing recipes keep producing
identical numbers after the migration.

Quantities are reduced to their canonical base unit via ``units.ratio_to_base``
(sourced from ``UnitConversionService``):

    qty_base        = qty_normalized  OR  qty * unit_ratio
    price_per_base  = price / price_unit_ratio
    line_cost       = qty_base * price_per_base * (1 + loss_pct/100) / (yield_pct/100)
    total_cost      = sum(line_cost)
    cost_per_portion= total_cost / recipe.yield_qty
    food_cost_pct   = cost_per_portion / selling_price * 100      (if selling_price)
    margin          = selling_price - cost_per_portion           (if selling_price)
"""
import uuid
from datetime import date
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Optional, Dict, Any, List, Callable

from sqlalchemy.orm import Session

from app.models.models import Recipe, RecipeVersion, RecipeIngredient, RecipeCost
from app.services.units.unit_conversion import UnitConversionService

_HUNDRED = Decimal("100")


def _d(value, default="0") -> Decimal:
    """Coerce any (Decimal/float/int/str/None) value to Decimal."""
    if value is None:
        return Decimal(default)
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal(default)


def _out(value: Optional[Decimal], places: int = 4) -> Optional[float]:
    """Round a Decimal and emit a float for JSON/DB (preserves legacy results)."""
    if value is None:
        return None
    q = Decimal(1).scaleb(-places)  # e.g. places=4 -> Decimal('0.0001')
    return float(_d(value).quantize(q, rounding=ROUND_HALF_UP))


def compute_cost_breakdown(
    ingredients: List[Any],
    price_lookup: Callable[[Optional[str]], Optional[Any]],
    units: Dict[int, Any],
    yield_qty: Optional[Any],
    selling_price: Optional[Any] = None,
) -> Dict[str, Any]:
    """Pure cost computation (no DB). ``units`` maps unit_id -> ratio_to_base."""
    total_cost = Decimal("0")
    lines: List[Dict[str, Any]] = []
    price_ids: List[str] = []
    missing_prices: List[str] = []

    for ing in ingredients:
        product_id = str(ing.product_id) if ing.product_id else None
        loss_pct = _d(ing.loss_pct, "0")
        yield_pct = _d(ing.yield_pct, "100")
        if yield_pct == 0:
            yield_pct = _HUNDRED

        if ing.qty_normalized is not None:
            qty_base = _d(ing.qty_normalized)
        else:
            qty_base = _d(ing.qty) * _d(units.get(ing.unit_id, 1), "1")

        price_row = price_lookup(product_id) if product_id else None
        if price_row is None:
            missing_prices.append(product_id)
            lines.append({
                "product_id": product_id,
                "qty_base": _out(qty_base),
                "unit_price": None,
                "line_cost": None,
                "price_id": None,
                "missing_price": True,
            })
            continue

        price_unit_ratio = _d(units.get(price_row.unit_id, 1), "1") or Decimal("1")
        price_per_base = _d(price_row.price) / price_unit_ratio
        line_cost = (
            qty_base
            * price_per_base
            * (Decimal("1") + loss_pct / _HUNDRED)
            / (yield_pct / _HUNDRED)
        )

        total_cost += line_cost
        price_ids.append(str(price_row.id))
        lines.append({
            "product_id": product_id,
            "qty_base": _out(qty_base),
            "unit_price": _out(price_row.price),
            "line_cost": _out(line_cost),
            "price_id": str(price_row.id),
            "missing_price": False,
        })

    yq = _d(yield_qty)
    cost_per_portion = (total_cost / yq) if yq > 0 else None

    food_cost_pct = None
    margin = None
    sp = _d(selling_price) if selling_price is not None else None
    if sp is not None and sp > 0 and cost_per_portion is not None:
        food_cost_pct = cost_per_portion / sp * _HUNDRED
        margin = sp - cost_per_portion

    return {
        "computed_cost_total": _out(total_cost),
        "cost_per_portion": _out(cost_per_portion),
        "food_cost_pct": _out(food_cost_pct, 2),
        "margin_estimated": _out(margin),
        "has_missing_prices": bool(missing_prices),
        "breakdown": lines,
        "_price_ids": price_ids,
        "_missing_prices": missing_prices,
    }


def compute_recipe_version_cost(
    db: Session,
    tenant_id: str,
    recipe_version_id: str,
    selling_price: Optional[float] = None,
    as_of: Optional[date] = None,
    persist: bool = True,
) -> Dict[str, Any]:
    version = db.query(RecipeVersion).filter(RecipeVersion.id == recipe_version_id).first()
    if version is None:
        raise ValueError("recipe_version_not_found")

    recipe = (
        db.query(Recipe)
        .filter(Recipe.id == version.recipe_id, Recipe.tenant_id == tenant_id)
        .first()
    )
    if recipe is None:
        raise ValueError("recipe_not_found")

    ingredients = (
        db.query(RecipeIngredient)
        .filter(RecipeIngredient.recipe_version_id == recipe_version_id)
        .all()
    )

    # Unit ratios come from the canonical unit service.
    units = UnitConversionService.from_db(db).ratio_map()

    # local import avoids a circular import (crud_price -> models -> ...)
    from app.crud import crud_price

    def price_lookup(product_id):
        return crud_price.get_latest_price(db, tenant_id, product_id, as_of)

    computed = compute_cost_breakdown(
        ingredients, price_lookup, units, recipe.yield_qty, selling_price
    )

    snapshot_source = {
        "price_ids": computed.pop("_price_ids"),
        "missing_prices": computed.pop("_missing_prices"),
        "lines": computed["breakdown"],
        "as_of": as_of.isoformat() if as_of else None,
        "selling_price": selling_price,
    }

    result = {"recipe_version_id": recipe_version_id, **computed}

    if persist:
        snapshot = RecipeCost(
            id=str(uuid.uuid4()),
            recipe_version_id=recipe_version_id,
            computed_cost_total=result["computed_cost_total"],
            cost_per_portion=result["cost_per_portion"],
            food_cost_pct=result["food_cost_pct"],
            margin_estimated=result["margin_estimated"],
            snapshot_price_source=snapshot_source,
        )
        db.add(snapshot)
        db.commit()
        db.refresh(snapshot)
        result["snapshot_id"] = str(snapshot.id)

    return result


def recompute_for_product(db: Session, product_id: str, as_of: Optional[date] = None) -> List[str]:
    """Recompute (and persist) every recipe version that uses ``product_id``."""
    rows = (
        db.query(RecipeVersion.id, Recipe.tenant_id)
        .join(RecipeIngredient, RecipeIngredient.recipe_version_id == RecipeVersion.id)
        .join(Recipe, Recipe.id == RecipeVersion.recipe_id)
        .filter(RecipeIngredient.product_id == product_id)
        .distinct()
        .all()
    )
    recomputed = []
    for version_id, tenant_id in rows:
        compute_recipe_version_cost(db, str(tenant_id), str(version_id), persist=True)
        recomputed.append(str(version_id))
    if recomputed:
        from app.core import metrics

        metrics.RECIPES_RECALCULATED.inc(len(recomputed))
    return recomputed
