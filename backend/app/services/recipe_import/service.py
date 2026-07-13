"""Orchestrates: PDF -> OCR -> AI extraction -> product matching -> cost preview,
then (after user validation) persists the recipe and costs it.

Inline processing (no Celery worker required); the job row tracks status so the
API can expose the documented upload + poll flow.
"""
import uuid
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.tenancy import assert_products_in_tenant
from app.models.models import Product, Recipe, RecipeVersion, RecipeIngredient
from app.crud import crud_price, crud_recipe_import
from app.services.ocr.service import extract_text
from app.services.ocr.errors import OcrError
from app.services.matching.product_matcher import match_product
from app.services.costing import cost_engine
from app.services.costing.cost_engine import compute_cost_breakdown
from app.services.units.unit_conversion import UnitConversionService

from .extractor import get_extractor
from .errors import RecipeImportError, PdfUnreadableError, RecipeExtractionError


# --------------------------------------------------------------------------- #
# preview building (read-only, no recipe is created yet)
# --------------------------------------------------------------------------- #
def _product_names(db: Session, tenant_id: str) -> Dict[str, str]:
    return {
        str(p.id): p.name
        for p in db.query(Product.id, Product.name)
        .filter(Product.tenant_id == tenant_id)
        .all()
    }


def _estimate_cost(db: Session, tenant_id: str, ingredients: List[Dict[str, Any]],
                   servings: Optional[float]) -> Dict[str, Any]:
    """Cost preview that reuses the real cost engine on transient (unsaved) lines."""
    units = UnitConversionService.from_db(db).ratio_map()
    units_by_code = crud_price.get_units_by_code(db)
    rows = []
    for ing in ingredients:
        code = (ing.get("unit") or "").strip().lower()
        rows.append(
            SimpleNamespace(
                product_id=ing.get("matched_product_id"),
                qty=ing.get("quantity"),
                unit_id=units_by_code.get(code) if code else None,
                qty_normalized=None,
                loss_pct=0,
                yield_pct=100,
            )
        )

    def price_lookup(product_id):
        return crud_price.get_latest_price(db, tenant_id, product_id)

    breakdown = compute_cost_breakdown(rows, price_lookup, units, servings or 1, None)
    return {
        "computed_cost_total": breakdown.get("computed_cost_total"),
        "cost_per_portion": breakdown.get("cost_per_portion"),
        "food_cost_pct": breakdown.get("food_cost_pct"),
        "margin_estimated": breakdown.get("margin_estimated"),
        "has_missing_prices": breakdown.get("has_missing_prices", False),
    }


def _build_preview(db: Session, tenant_id: str, draft: Dict[str, Any]) -> Dict[str, Any]:
    names = _product_names(db, tenant_id)
    units_by_code = crud_price.get_units_by_code(db)

    ingredients: List[Dict[str, Any]] = []
    unmatched: List[str] = []
    unknown_units: List[str] = []

    for ing in draft.get("ingredients") or []:
        name = (ing.get("name") or "").strip()
        if not name:
            continue
        code = (ing.get("unit") or "").strip().lower()
        unit_id = units_by_code.get(code) if code else None
        if code and unit_id is None and code not in unknown_units:
            unknown_units.append(code)

        res = match_product(db, tenant_id, name)
        pid = res.get("product_id")
        if not pid:
            unmatched.append(name)

        ingredients.append(
            {
                "name": name,
                "quantity": ing.get("qty"),
                "unit": code or None,
                "matched_product_id": pid,
                "matched_product_name": names.get(pid) if pid else None,
                "match_confidence": res.get("confidence_score"),
                "unit_recognized": unit_id is not None or not code,
            }
        )

    servings = draft.get("yield_qty")
    cost = _estimate_cost(db, tenant_id, ingredients, servings)
    return {
        "recipe_name": draft.get("name") or "",
        "servings": servings,
        "ingredients": ingredients,
        "instructions": draft.get("steps") or [],
        "cost": cost,
        "unmatched_ingredients": unmatched,
        "unknown_units": unknown_units,
        "note": (
            "Fiche générée automatiquement depuis le PDF. Vérifiez les quantités, "
            "les unités et les correspondances produits avant d'enregistrer. Les "
            "ingrédients sans produit/prix rendent le coût incomplet."
        ),
    }


# --------------------------------------------------------------------------- #
# entry points
# --------------------------------------------------------------------------- #
def process_import(db: Session, tenant_id: str, file_bytes: bytes,
                   content_type: Optional[str], filename: Optional[str],
                   extractor: Any = None):
    """Run the full pipeline inline and return the (done|error) job row."""
    job = crud_recipe_import.create_job(db, tenant_id, filename, content_type)
    try:
        text = extract_text(file_bytes, content_type)
        if not (text or "").strip():
            raise PdfUnreadableError(
                "Impossible de lire du texte dans ce PDF. Essayez un PDF de meilleure qualité."
            )
        draft = (extractor or get_extractor()).extract(text, hint_title=filename)
        preview = _build_preview(db, tenant_id, draft)
        crud_recipe_import.save_result(db, job, text, preview)
        crud_recipe_import.set_status(db, job, "done")
    except (RecipeImportError, OcrError) as exc:
        crud_recipe_import.set_status(db, job, "error", error=str(exc))
    except Exception as exc:  # never leave a job stuck in "processing"
        crud_recipe_import.set_status(db, job, "error", error=f"Erreur inattendue : {exc}")
    return job


def get_status(db: Session, tenant_id: str, job_id: str) -> Optional[Dict[str, Any]]:
    job = crud_recipe_import.get_job(db, tenant_id, job_id)
    if job is None:
        return None
    result = crud_recipe_import.get_result(db, job_id)
    return {
        "job_id": str(job.id),
        "status": job.status,
        "error": job.error,
        "recipe_id": str(result.recipe_id) if result and result.recipe_id else None,
        "preview": result.data if result else None,
    }


def save_import(db: Session, tenant_id: str, name: str, servings: Optional[float],
                instructions: List[str], ingredients: List[Dict[str, Any]],
                selling_price: Optional[float] = None,
                job_id: Optional[str] = None) -> Dict[str, Any]:
    """Persist the (validated) preview as a recipe + version + ingredients, store
    the steps, then compute and persist the cost. Honors an explicit product_id
    per ingredient (user correction); otherwise re-matches by name."""
    # The corrected product ids come from the client: refuse any that belong to
    # another organization.
    assert_products_in_tenant(
        db, tenant_id, [ing.get("product_id") for ing in (ingredients or [])]
    )
    units_by_code = crud_price.get_units_by_code(db)

    recipe = Recipe(
        id=str(uuid.uuid4()), tenant_id=tenant_id, name=name, yield_qty=servings or 1
    )
    db.add(recipe)
    db.flush()

    steps = [s for s in (instructions or []) if (s or "").strip()]
    version = RecipeVersion(
        id=str(uuid.uuid4()),
        recipe_id=recipe.id,
        version_number=1,
        is_published=False,
        notes="\n".join(steps) or None,
        meta={"steps": steps, "imported_from": "pdf"},
    )
    db.add(version)
    db.flush()

    unmatched: List[str] = []
    unknown_units: List[str] = []
    for ing in ingredients:
        ing_name = (ing.get("name") or "").strip()
        if not ing_name:
            continue
        code = (ing.get("unit") or "").strip().lower()
        unit_id = units_by_code.get(code) if code else None
        if code and unit_id is None and code not in unknown_units:
            unknown_units.append(code)

        product_id = ing.get("product_id")
        if not product_id:
            res = match_product(db, tenant_id, ing_name)
            product_id = res.get("product_id")
        if not product_id:
            unmatched.append(ing_name)

        db.add(
            RecipeIngredient(
                id=str(uuid.uuid4()),
                recipe_version_id=version.id,
                product_id=product_id,
                ingredient_name=ing_name,
                qty=ing.get("quantity"),
                unit_id=unit_id,
                loss_pct=0,
                yield_pct=100,
            )
        )

    recipe.current_version_id = version.id
    db.commit()

    # Persist the procedure as first-class RecipeInstruction rows (so it's read
    # back like a manual recipe), in addition to version.notes/meta above.
    from app.crud import crud_recipe
    crud_recipe.replace_instructions(db, str(recipe.id), steps)

    cost = cost_engine.compute_recipe_version_cost(
        db, tenant_id, str(version.id), selling_price=selling_price, persist=True
    )

    if job_id:
        result = crud_recipe_import.get_result(db, job_id)
        if result is not None:
            crud_recipe_import.attach_recipe(db, result, str(recipe.id))

    return {
        "recipe_id": str(recipe.id),
        "version_id": str(version.id),
        "name": name,
        "yield_qty": float(servings) if servings else 1.0,
        "unmatched_ingredients": unmatched,
        "unknown_units": unknown_units,
        "cost": {
            "computed_cost_total": cost.get("computed_cost_total"),
            "cost_per_portion": cost.get("cost_per_portion"),
            "food_cost_pct": cost.get("food_cost_pct"),
            "margin_estimated": cost.get("margin_estimated"),
            "has_missing_prices": cost.get("has_missing_prices"),
        },
    }
