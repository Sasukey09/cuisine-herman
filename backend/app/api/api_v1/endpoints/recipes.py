from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_current_tenant_id, require_writer
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
)
from app.crud.crud_recipe import (
    create_recipe,
    get_recipe,
    list_recipes,
    update_recipe,
    delete_recipe,
)
from app.crud import crud_recipe_version
from app.services.costing import cost_engine
from app.services.recipe_import import service as recipe_import_service

router = APIRouter()


@router.post("/", response_model=RecipeRead)
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
    limit: int = 50,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
):
    return list_recipes(db, tenant_id, skip=skip, limit=limit)


@router.post("/import-pdf", response_model=RecipeImportStatus, status_code=201)
async def api_import_recipe_pdf(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    _: list = Depends(require_writer),
):
    """Upload a recipe PDF -> OCR -> AI extraction -> product matching -> cost
    preview. Returns a job with status + an editable preview (nothing is saved as
    a recipe yet — validate via POST /recipes/import-save)."""
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Fichier vide")
    job = recipe_import_service.process_import(
        db, tenant_id, content, file.content_type, file.filename
    )
    status = recipe_import_service.get_status(db, tenant_id, str(job.id))
    return status


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
    ingredients = [i.dict() for i in payload.ingredients]
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
