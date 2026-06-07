from sqlalchemy.orm import Session
from app.models.models import Recipe, RecipeVersion
from app.schemas.schemas import RecipeCreate, RecipeUpdate
import uuid


def create_recipe(db: Session, payload: RecipeCreate, tenant_id: str) -> Recipe:
    obj = Recipe(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        name=payload.name,
        yield_qty=payload.yield_qty,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_recipe(db: Session, recipe_id: str, tenant_id: str, payload: RecipeUpdate):
    obj = get_recipe(db, recipe_id, tenant_id)
    if obj is None:
        return None
    for field, value in payload.dict(exclude_unset=True).items():
        setattr(obj, field, value)
    db.commit()
    db.refresh(obj)
    return obj


def delete_recipe(db: Session, recipe_id: str, tenant_id: str) -> bool:
    obj = get_recipe(db, recipe_id, tenant_id)
    if obj is None:
        return False
    # Delete versions explicitly; the DB cascades ingredients + cost rows
    # (recipe_version_id FKs use ondelete=CASCADE). Bulk deletes avoid the ORM
    # trying to null recipe_id on orphaned versions.
    db.query(RecipeVersion).filter(RecipeVersion.recipe_id == recipe_id).delete(
        synchronize_session=False
    )
    db.query(Recipe).filter(
        Recipe.id == recipe_id, Recipe.tenant_id == tenant_id
    ).delete(synchronize_session=False)
    db.commit()
    return True


def get_recipe(db: Session, recipe_id: str, tenant_id: str):
    return (
        db.query(Recipe)
        .filter(Recipe.id == recipe_id, Recipe.tenant_id == tenant_id)
        .first()
    )


def list_recipes(db: Session, tenant_id: str, skip: int = 0, limit: int = 50):
    return (
        db.query(Recipe)
        .filter(Recipe.tenant_id == tenant_id)
        .offset(skip)
        .limit(limit)
        .all()
    )
