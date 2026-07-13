import uuid
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.tenancy import assert_products_in_tenant
from app.models.models import Recipe, RecipeVersion, RecipeIngredient


def _next_version_number(db: Session, recipe_id: str) -> int:
    current = (
        db.query(func.max(RecipeVersion.version_number))
        .filter(RecipeVersion.recipe_id == recipe_id)
        .scalar()
    )
    return (current or 0) + 1


def create_version(db: Session, tenant_id: str, recipe_id: str, payload) -> RecipeVersion:
    """Create a new recipe version (scoped to tenant) with its ingredients."""
    recipe = (
        db.query(Recipe)
        .filter(Recipe.id == recipe_id, Recipe.tenant_id == tenant_id)
        .first()
    )
    if recipe is None:
        return None

    # Ingredient product ids come from the request body: refuse any that belong
    # to another organization (they would leak into cost recomputation).
    assert_products_in_tenant(
        db, tenant_id, [i.product_id for i in (payload.ingredients or []) if i.product_id]
    )

    version = RecipeVersion(
        id=str(uuid.uuid4()),
        recipe_id=recipe_id,
        version_number=_next_version_number(db, recipe_id),
        notes=payload.notes,
        is_published=bool(payload.is_published),
    )
    db.add(version)
    db.flush()  # get version.id without committing yet

    for ing in payload.ingredients:
        db.add(
            RecipeIngredient(
                id=str(uuid.uuid4()),
                recipe_version_id=version.id,
                product_id=ing.product_id,
                qty=ing.qty,
                unit_id=ing.unit_id,
                qty_normalized=ing.qty_normalized,
                loss_pct=ing.loss_pct if ing.loss_pct is not None else 0,
                yield_pct=ing.yield_pct if ing.yield_pct is not None else 100,
                prep_notes=ing.prep_notes,
            )
        )

    # newest version becomes the recipe's current version
    recipe.current_version_id = version.id
    db.commit()
    db.refresh(version)
    return version


def get_version(db: Session, tenant_id: str, recipe_id: str, version_id: str) -> RecipeVersion:
    return (
        db.query(RecipeVersion)
        .join(Recipe, Recipe.id == RecipeVersion.recipe_id)
        .filter(
            Recipe.tenant_id == tenant_id,
            RecipeVersion.recipe_id == recipe_id,
            RecipeVersion.id == version_id,
        )
        .first()
    )


def get_ingredients(db: Session, version_id: str):
    return (
        db.query(RecipeIngredient)
        .filter(RecipeIngredient.recipe_version_id == version_id)
        .all()
    )


def list_ingredients_for_versions(db: Session, version_ids) -> dict:
    """Ingredients of MANY versions in one query -> {version_id: [ingredients]}."""
    ids = [str(v) for v in version_ids if v]
    if not ids:
        return {}
    rows = (
        db.query(RecipeIngredient)
        .filter(RecipeIngredient.recipe_version_id.in_(ids))
        .all()
    )
    out: dict = {i: [] for i in ids}
    for row in rows:
        out.setdefault(str(row.recipe_version_id), []).append(row)
    return out
