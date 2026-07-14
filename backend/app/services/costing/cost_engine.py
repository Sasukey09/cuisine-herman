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

    # The recipe knows what it sells for. Asking the caller to tell it again is how
    # you end up with nothing.
    #
    # Until now this function used ONLY the selling price it was handed. The cost
    # panel offers an empty box labelled "(optionnel)", so a chef who simply clicks
    # "Calculer" — the obvious thing to do — persisted a snapshot with
    # `food_cost_pct = NULL` and `margin = NULL`. The dashboard's margin alerts read
    # those snapshots and keep the ones above 35 %; NULL is not above 35 %. So **no
    # margin alert could ever fire**, and nobody would notice, because an alert that
    # never fires looks exactly like a restaurant with healthy margins.
    #
    # The batch path (`compute_costs_for_recipes`, used by the listing) already fell
    # back to `recipe.selling_price`. The two disagreed: the list showed a food cost,
    # the detail panel showed nothing, for the same recipe.
    #
    # An explicit price still wins — that is the whole point of the box: simulating
    # "what if I sold it at 15 €?" without touching the recipe.
    if selling_price is None and recipe.selling_price is not None:
        selling_price = float(recipe.selling_price)

    ingredients = (
        db.query(RecipeIngredient)
        .filter(RecipeIngredient.recipe_version_id == recipe_version_id)
        .all()
    )

    units = unit_ratios(db)

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


def recompute_for_product(
    db: Session, product_id: str, tenant_id: str, as_of: Optional[date] = None
) -> List[str]:
    """Recompute (and persist) every recipe version of ``tenant_id`` using ``product_id``.

    ``tenant_id`` is mandatory: without it, a tenant who planted a foreign
    product id in one of their own recipes could trigger recomputation across
    another organization's recipes.
    """
    rows = (
        db.query(RecipeVersion.id)
        .join(RecipeIngredient, RecipeIngredient.recipe_version_id == RecipeVersion.id)
        .join(Recipe, Recipe.id == RecipeVersion.recipe_id)
        .filter(
            RecipeIngredient.product_id == product_id,
            Recipe.tenant_id == tenant_id,
        )
        .distinct()
        .all()
    )
    recomputed = []
    for (version_id,) in rows:
        compute_recipe_version_cost(db, str(tenant_id), str(version_id), persist=True)
        recomputed.append(str(version_id))
    if recomputed:
        from app.core import metrics

        metrics.RECIPES_RECALCULATED.inc(len(recomputed))
    return recomputed


# --------------------------------------------------------------------------- #
# Units are reference data (seeded by a migration, never written at runtime), yet
# `UnitConversionService.from_db` reloaded EVERY unit and EVERY conversion on
# every single cost computation — twice per recipe, inside a loop over recipes.
# Cached per process. `reset_unit_cache()` exists for tests and for the day a
# unit is ever added.
# --------------------------------------------------------------------------- #
_UNIT_RATIOS = None


def unit_ratios(db: Session) -> dict:
    global _UNIT_RATIOS
    if _UNIT_RATIOS is None:
        _UNIT_RATIOS = UnitConversionService.from_db(db).ratio_map()
    return _UNIT_RATIOS


def reset_unit_cache() -> None:
    global _UNIT_RATIOS
    _UNIT_RATIOS = None


def compute_costs_for_recipes(
    db: Session, tenant_id: str, recipes: list, as_of: Optional[date] = None
) -> dict:
    """Cost every recipe of a list in a constant number of queries.

    The listing endpoint used to call `compute_recipe_version_cost` per recipe.
    Each call re-queried the version, the recipe, its ingredients, ALL units, ALL
    conversions, then one price per ingredient: with 500 recipes x 10 ingredients
    that is roughly 7 500 queries for a single page.

    Here: 1 query for the ingredients of every version, 1 for the latest price of
    every product referenced, units from cache. The costing itself is the same
    pure function, so the numbers are identical.
    """
    from app.crud import crud_price, crud_recipe_version

    version_ids = [str(r.current_version_id) for r in recipes if r.current_version_id]
    if not version_ids:
        return {}

    ingredients_by_version = crud_recipe_version.list_ingredients_for_versions(db, version_ids)

    product_ids = {
        str(i.product_id)
        for ings in ingredients_by_version.values()
        for i in ings
        if i.product_id
    }
    prices = crud_price.get_latest_prices(db, tenant_id, product_ids, as_of)
    units = unit_ratios(db)

    out = {}
    for recipe in recipes:
        version_id = str(recipe.current_version_id) if recipe.current_version_id else None
        if not version_id:
            continue
        selling = float(recipe.selling_price) if recipe.selling_price is not None else None
        computed = compute_cost_breakdown(
            ingredients_by_version.get(version_id, []),
            lambda pid: prices.get(str(pid)),
            units,
            recipe.yield_qty,
            selling,
        )
        computed.pop("_price_ids", None)
        computed.pop("_missing_prices", None)
        out[version_id] = computed
    return out
