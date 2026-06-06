import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import Response

from app.api.api_v1.api import api_router
from app.api.health import router as health_router
from app.core.middleware import PrometheusMiddleware
from app.core import metrics

APP_NAME = "CuisineHerman API"


def create_app() -> FastAPI:
    app = FastAPI(title=APP_NAME)

    # HTTP metrics first so it wraps everything below it.
    app.add_middleware(PrometheusMiddleware)

    origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in origins if o.strip()],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix="/api/v1")
    app.include_router(health_router)

    @app.get("/metrics")
    def prometheus_metrics():
        payload, content_type = metrics.render_latest()
        return Response(content=payload, media_type=content_type)

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)), reload=True)
