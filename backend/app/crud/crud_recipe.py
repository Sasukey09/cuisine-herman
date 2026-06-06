from sqlalchemy.orm import Session
from app.models.models import Recipe
from app.schemas.schemas import RecipeCreate
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
