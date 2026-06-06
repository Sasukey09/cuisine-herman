from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_current_tenant_id, require_writer
from app.schemas.schemas import (
    RecipeCreate,
    RecipeRead,
    RecipeVersionCreate,
    RecipeVersionRead,
    ComputeCostRequest,
    RecipeCostRead,
)
from app.crud.crud_recipe import create_recipe, get_recipe, list_recipes
from app.crud import crud_recipe_version
from app.services.costing import cost_engine

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
