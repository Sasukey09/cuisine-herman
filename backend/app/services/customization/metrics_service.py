"""Custom metrics service: evaluate user-defined formulas over recipe variables.

Exposes a fixed, documented set of variables per domain (recipe) so users can
write no-code indicators. Formulas are validated against those variable names and
evaluated with the sandboxed evaluator.
"""
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.models import Recipe, RecipeVersion
from app.services.costing import cost_engine
from app.crud import crud_custom_metric
from . import formula_eval

# Variables available to recipe-scoped formulas (name → human description).
RECIPE_VARIABLES: List[Dict[str, str]] = [
    {"name": "computed_cost_total", "description": "Coût matière total de la recette"},
    {"name": "cost_per_portion", "description": "Coût matière par portion"},
    {"name": "food_cost_pct", "description": "Food cost en % (si prix de vente fourni)"},
    {"name": "margin_estimated", "description": "Marge par portion (si prix de vente fourni)"},
    {"name": "yield_qty", "description": "Nombre de portions"},
    {"name": "selling_price", "description": "Prix de vente par portion (saisi)"},
]

_TARGET_VARIABLES = {"recipe": [v["name"] for v in RECIPE_VARIABLES]}


def allowed_names(target: str = "recipe") -> List[str]:
    return _TARGET_VARIABLES.get(target, [])


def validate_formula(formula: str, target: str = "recipe"):
    """(ok, error) — validate a formula against a domain's variables."""
    return formula_eval.validate(formula, allowed_names(target))


def _effective_version_id(db: Session, recipe: Recipe) -> Optional[str]:
    if recipe.current_version_id:
        return str(recipe.current_version_id)
    row = (
        db.query(RecipeVersion.id)
        .filter(RecipeVersion.recipe_id == recipe.id)
        .order_by(RecipeVersion.version_number.desc())
        .first()
    )
    return str(row[0]) if row else None


def recipe_variable_context(
    db: Session, tenant_id: str, recipe_id: str, selling_price: Optional[float] = None
) -> Dict[str, Any]:
    recipe = (
        db.query(Recipe)
        .filter(Recipe.id == recipe_id, Recipe.tenant_id == tenant_id)
        .first()
    )
    if recipe is None:
        raise ValueError("recipe_not_found")
    version_id = _effective_version_id(db, recipe)
    if version_id is None:
        raise ValueError("no_version")

    cost = cost_engine.compute_recipe_version_cost(
        db, tenant_id, version_id, selling_price=selling_price, persist=False
    )
    return {
        "computed_cost_total": cost.get("computed_cost_total"),
        "cost_per_portion": cost.get("cost_per_portion"),
        "food_cost_pct": cost.get("food_cost_pct"),
        "margin_estimated": cost.get("margin_estimated"),
        "yield_qty": float(recipe.yield_qty) if recipe.yield_qty is not None else None,
        "selling_price": selling_price,
    }


def evaluate_for_recipe(
    db: Session, tenant_id: str, recipe_id: str, selling_price: Optional[float] = None
) -> Dict[str, Any]:
    """Evaluate every recipe-scoped custom metric for a recipe."""
    context = recipe_variable_context(db, tenant_id, recipe_id, selling_price)
    metrics = crud_custom_metric.list_metrics(db, tenant_id, target="recipe")
    results = []
    for m in metrics:
        meta = m.meta or {}
        entry = {
            "id": str(m.id),
            "name": m.name,
            "format": meta.get("format", "number"),
            "value": None,
            "error": None,
        }
        try:
            value = formula_eval.evaluate(m.formula, context)
            entry["value"] = round(value, 4) if isinstance(value, float) else value
        except formula_eval.FormulaError as exc:
            entry["error"] = str(exc)
        results.append(entry)
    return {"recipe_id": recipe_id, "context": context, "metrics": results}
