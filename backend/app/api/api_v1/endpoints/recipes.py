from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, File, UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core.uploads import validate_upload
import logging

from app.core.logging import get_logger, log_event
from app.db.session import get_db
from app.api.deps import get_current_tenant_id, require_writer, quota, daily_quota
from app.schemas.schemas import (
    RecipeCreate,
    RecipeUpdate,
    RecipeRead,
    RecipeVersionCreate,
    RecipeVersionRead,
    ComputeCostRequest,
    RecipeCostRead,
    RecipeImportStatus,
    RecipeImportSaveRequest,
    RecipeInstructionRead,
)
from app.crud.crud_recipe import (
    create_recipe,
    get_recipe,
    list_recipes,
    update_recipe,
    delete_recipe,
    get_instructions,
)
from app.crud import crud_recipe_version
from app.services.costing import cost_engine
from app.services.recipe_import import service as recipe_import_service

router = APIRouter()

logger = get_logger(__name__)


@router.post("/", response_model=RecipeRead, status_code=201)
def api_create_recipe(
    payload: RecipeCreate,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    _: list = Depends(require_writer),
):
    return create_recipe(db, payload, tenant_id)


@router.get("/", response_model=List[RecipeRead])
def api_list_recipes(
    skip: int = 0,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
):
    return list_recipes(db, tenant_id, skip=skip, limit=limit)


@router.get("/enriched")
def api_list_recipes_enriched(
    skip: int = 0,
    limit: int = Query(200, ge=1, le=500),
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Recipes + computed matter cost/portion, selling price, food cost % and
    gross margin % (so the recipe cards show real figures)."""
    recipes = list_recipes(db, tenant_id, skip=skip, limit=limit)

    # One batch instead of a cost computation per recipe (which re-queried every
    # unit, every conversion and one price per ingredient, every time).
    try:
        costs = cost_engine.compute_costs_for_recipes(db, tenant_id, recipes)
    except Exception as exc:
        # Degrade to "no figures" rather than a 500 — but say so, instead of the
        # silent `except: pass` that made this impossible to debug in production.
        log_event(
            logger, logging.ERROR, "recipes.enriched.cost_failed",
            tenant_id=tenant_id, error=str(exc),
        )
        costs = {}

    out = []
    for r in recipes:
        version_id = str(r.current_version_id) if r.current_version_id else None
        selling = float(r.selling_price) if r.selling_price is not None else None
        res = costs.get(version_id) or {}
        cost_per_portion = res.get("cost_per_portion")
        food_cost = res.get("food_cost_pct")
        has_missing_prices = bool(res.get("has_missing_prices"))
        margin_pct = round(100.0 - float(food_cost), 1) if food_cost is not None else None
        out.append(
            {
                "id": str(r.id),
                "name": r.name,
                "yield_qty": float(r.yield_qty) if r.yield_qty is not None else None,
                "selling_price": selling,
                "cost_per_portion": cost_per_portion,
                "food_cost_pct": food_cost,
                "margin_pct": margin_pct,
                "has_missing_prices": has_missing_prices,
                "defined": version_id is not None,
            }
        )
    return out


@router.post("/import-pdf", response_model=RecipeImportStatus, status_code=201)
async def api_import_recipe_pdf(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    _: list = Depends(require_writer),
    _q: None = Depends(quota("pdf_import", "PDF_IMPORT_PER_MIN", 10)),
    _qd: None = Depends(daily_quota("pdf_import", "PDF_IMPORT_PER_DAY", 100)),
):
    """Upload a recipe PDF -> OCR -> AI extraction -> product matching -> cost
    preview. Returns a job with status + an editable preview (nothing is saved as
    a recipe yet — validate via POST /recipes/import-save)."""
    content = await file.read()
    validate_upload(content, file.content_type)
    filename, ctype = file.filename, file.content_type

    def _work():
        # OCR + an AI extraction: tens of seconds of blocking network calls.
        job = recipe_import_service.process_import(db, tenant_id, content, ctype, filename)
        return recipe_import_service.get_status(db, tenant_id, str(job.id))

    return await run_in_threadpool(_work)


@router.get("/import-status/{job_id}", response_model=RecipeImportStatus)
def api_recipe_import_status(
    job_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Poll an import job: status (queued/processing/done/error) + preview."""
    status = recipe_import_service.get_status(db, tenant_id, job_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Import job not found")
    return status


@router.post("/import-save", status_code=201)
def api_recipe_import_save(
    payload: RecipeImportSaveRequest,
    job_id: Optional[str] = None,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    _: list = Depends(require_writer),
):
    """Validate a preview: create the recipe + version + ingredients (honoring
    user-corrected product mappings), store the steps, and compute the cost."""
    name = (payload.recipe_name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Nom de recette requis")
    if not payload.ingredients:
        raise HTTPException(status_code=400, detail="Au moins un ingrédient est requis")
    ingredients = [i.model_dump() for i in payload.ingredients]
    return recipe_import_service.save_import(
        db,
        tenant_id,
        name=name,
        servings=payload.servings,
        instructions=payload.instructions,
        ingredients=ingredients,
        selling_price=payload.selling_price,
        job_id=job_id,
    )


@router.get("/{recipe_id}", response_model=RecipeRead)
def api_get_recipe(
    recipe_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
):
    recipe = get_recipe(db, recipe_id, tenant_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return recipe


@router.get("/{recipe_id}/instructions", response_model=List[RecipeInstructionRead])
def api_recipe_instructions(
    recipe_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Ordered preparation steps (procedure) of a recipe."""
    if not get_recipe(db, recipe_id, tenant_id):
        raise HTTPException(status_code=404, detail="Recipe not found")
    return get_instructions(db, recipe_id)


@router.get("/{recipe_id}/full")
def api_recipe_full(
    recipe_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Complete recipe in one call: {recipe, ingredients, instructions}."""
    recipe = get_recipe(db, recipe_id, tenant_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    version_id = str(recipe.current_version_id) if recipe.current_version_id else None
    ingredients = crud_recipe_version.get_ingredients(db, version_id) if version_id else []
    return {
        "recipe": {
            "id": str(recipe.id),
            "name": recipe.name,
            "yield_qty": float(recipe.yield_qty) if recipe.yield_qty is not None else None,
            "current_version_id": version_id,
        },
        "ingredients": [
            {
                "id": str(i.id),
                "product_id": str(i.product_id) if i.product_id else None,
                "ingredient_name": i.ingredient_name,
                "qty": float(i.qty) if i.qty is not None else None,
                "unit_id": i.unit_id,
                "loss_pct": float(i.loss_pct) if i.loss_pct is not None else None,
                "yield_pct": float(i.yield_pct) if i.yield_pct is not None else None,
            }
            for i in ingredients
        ],
        "instructions": [
            {"step_number": s.step_number, "content": s.content}
            for s in get_instructions(db, recipe_id)
        ],
    }


@router.put("/{recipe_id}", response_model=RecipeRead)
def api_update_recipe(
    recipe_id: str,
    payload: RecipeUpdate,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    _: list = Depends(require_writer),
):
    recipe = update_recipe(db, recipe_id, tenant_id, payload)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return recipe


@router.delete("/{recipe_id}", status_code=204)
def api_delete_recipe(
    recipe_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    _: list = Depends(require_writer),
):
    try:
        deleted = delete_recipe(db, recipe_id, tenant_id)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Recette référencée — suppression impossible.",
        )
    if not deleted:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return None


@router.post("/{recipe_id}/versions", response_model=RecipeVersionRead, status_code=201)
def api_create_version(
    recipe_id: str,
    payload: RecipeVersionCreate,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    _: list = Depends(require_writer),
):
    version = crud_recipe_version.create_version(db, tenant_id, recipe_id, payload)
    if version is None:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return version


@router.get("/{recipe_id}/versions/{version_id}", response_model=RecipeVersionRead)
def api_get_version(
    recipe_id: str,
    version_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
):
    version = crud_recipe_version.get_version(db, tenant_id, recipe_id, version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="Recipe version not found")
    return version


@router.post("/{recipe_id}/versions/{version_id}/compute-cost", response_model=RecipeCostRead)
def api_compute_cost(
    recipe_id: str,
    version_id: str,
    payload: ComputeCostRequest = ComputeCostRequest(),
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    _: list = Depends(require_writer),
):
    # ensure the version belongs to this tenant/recipe before computing
    version = crud_recipe_version.get_version(db, tenant_id, recipe_id, version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="Recipe version not found")
    try:
        return cost_engine.compute_recipe_version_cost(
            db,
            tenant_id,
            version_id,
            selling_price=payload.selling_price,
            as_of=payload.as_of,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
