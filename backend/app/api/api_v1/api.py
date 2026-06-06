from fastapi import APIRouter

from app.api.api_v1.endpoints import (
    suppliers,
    products,
    invoices,
    recipes,
    auth,
    dashboard,
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(suppliers.router, prefix="/suppliers", tags=["suppliers"])
api_router.include_router(products.router, prefix="/products", tags=["products"])
api_router.include_router(invoices.router, prefix="/invoices", tags=["invoices"])
api_router.include_router(recipes.router, prefix="/recipes", tags=["recipes"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])

# NOTE: la couche `domain/` (tables `dh_*`) est volontairement debranchee.
# Elle definit un second modele de donnees concurrent (dh_product, dh_invoice...)
# qui n'existe ni dans sql/schema.sql ni dans la migration -> tout appel plantait
# avec "relation dh_product does not exist". Le modele canonique est app/models/models.py.
# Pour reactiver le product_matcher, il faudra le porter sur les modeles canoniques.
