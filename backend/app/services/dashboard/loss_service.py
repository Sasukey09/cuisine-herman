"""Dishes that lose money on every plate.

The cost engine has always computed `margin_estimated` for every recipe, and it
has always been stored. Nothing ever compared it to zero. So the platform knew,
recipe by recipe, that a dish cost more to make than it was sold for — and told
nobody. That is the one number a cost-management tool exists to surface.

This is not a threshold to tune. A dish whose portion costs more than its selling
price is losing money on every plate, and no restaurant would call that
acceptable at 4 % or at 40 %. The tunable question (`is my food cost above 30 %?`)
already has an endpoint; this is the one that does not.

Two things are deliberately reported and not hidden:

* a recipe with **no selling price** is not "fine" — it is *unknown*, and a dish
  you cannot evaluate is exactly where the loss hides. It is listed separately.
* a recipe whose cost is **incomplete** (an ingredient has no price) is worse than
  useless as a margin figure: its cost is understated by construction, so it can
  only make a dish look more profitable than it is. Reporting it as a loss would
  be dishonest, and reporting it as healthy would be dangerous — so it is listed
  as what it is: not costable yet.
"""
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.models import Recipe
from app.services.costing import cost_engine


def _f(value) -> Optional[float]:
    return float(value) if value is not None else None


def loss_report(db: Session, tenant_id: str) -> Dict[str, Any]:
    """Every dish of the restaurant, sorted by what it actually costs it.

    Costs are recomputed live, in a constant number of queries — not read from
    the last snapshot. A snapshot goes stale the moment a chef edits a selling
    price without recosting, and a stale margin is precisely the kind of number
    that reassures you while you lose money.
    """
    recipes = db.query(Recipe).filter(Recipe.tenant_id == tenant_id).all()
    costs = cost_engine.compute_costs_for_recipes(db, tenant_id, recipes)

    losing: List[Dict[str, Any]] = []
    no_price: List[Dict[str, Any]] = []
    not_costable: List[Dict[str, Any]] = []

    for recipe in recipes:
        if not recipe.current_version_id:
            continue
        cost = costs.get(str(recipe.current_version_id))
        if not cost:
            continue

        cost_per_portion = cost.get("cost_per_portion")
        entry = {
            "recipe_id": str(recipe.id),
            "name": recipe.name,
            "cost_per_portion": cost_per_portion,
            "selling_price": _f(recipe.selling_price),
        }

        if cost.get("has_missing_prices"):
            # Understated by construction: it can only flatter the dish.
            not_costable.append(entry)
            continue
        if cost_per_portion is None:
            continue
        if recipe.selling_price is None:
            no_price.append(entry)
            continue

        margin = _f(recipe.selling_price) - cost_per_portion
        if margin < 0:
            entry["loss_per_portion"] = round(-margin, 2)
            entry["food_cost_pct"] = (
                round(cost_per_portion / _f(recipe.selling_price) * 100, 1)
                if recipe.selling_price
                else None
            )
            losing.append(entry)

    losing.sort(key=lambda e: e["loss_per_portion"], reverse=True)

    return {
        "losing_money": losing,
        "loss_per_portion_total": round(sum(e["loss_per_portion"] for e in losing), 2),
        "no_selling_price": sorted(no_price, key=lambda e: e["name"]),
        "not_costable": sorted(not_costable, key=lambda e: e["name"]),
    }
