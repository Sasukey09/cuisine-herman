from fastapi import APIRouter

from app.api.api_v1.endpoints import (
    suppliers,
    products,
    invoices,
    recipes,
    auth,
    dashboard,
    ai,
    video,
    metrics,
    custom_fields,
    reports,
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(suppliers.router, prefix="/suppliers", tags=["suppliers"])
api_router.include_router(products.router, prefix="/products", tags=["products"])
api_router.include_router(invoices.router, prefix="/invoices", tags=["invoices"])
api_router.include_router(recipes.router, prefix="/recipes", tags=["recipes"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(ai.router, prefix="/ai", tags=["ai"])
api_router.include_router(video.router, prefix="/video", tags=["video"])
api_router.include_router(metrics.router, prefix="/metrics", tags=["metrics"])
api_router.include_router(custom_fields.router, prefix="/custom-fields", tags=["custom-fields"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
