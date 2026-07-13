import logging
import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse, Response

from app.api.api_v1.api import api_router
from app.api.health import router as health_router
from app.core.logging import get_logger, log_event
from app.core.middleware import PrometheusMiddleware
from app.core.tenancy import CrossTenantReferenceError
from app.core.uploads import UnsupportedUploadError
from app.core.url_guard import UnsafeURLError
from app.core import metrics

APP_NAME = "CuisineHerman API"

logger = get_logger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(title=APP_NAME)

    @app.exception_handler(UnsafeURLError)
    async def _unsafe_url(request: Request, exc: UnsafeURLError):
        """The server refused to fetch a URL (SSRF guard). Logged: it is either
        a user pasting the wrong link, or someone probing the internal network."""
        log_event(
            logger, logging.WARNING, "security.unsafe_url_refused",
            path=request.url.path, reason=str(exc),
        )
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(UnsupportedUploadError)
    async def _bad_upload(request: Request, exc: UnsupportedUploadError):
        log_event(
            logger, logging.WARNING, "security.upload_refused",
            path=request.url.path, reason=str(exc),
        )
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(CrossTenantReferenceError)
    async def _cross_tenant(request: Request, exc: CrossTenantReferenceError):
        """Someone referenced another organization's row. Log it, then answer 404.

        404 rather than 403 on purpose: a 403 would confirm the id exists
        somewhere else. This is a security signal, so it is logged as a warning.
        """
        log_event(
            logger, logging.WARNING, "tenancy.cross_tenant_reference",
            path=request.url.path, kind=exc.kind, ids=exc.ids,
        )
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    # HTTP metrics first so it wraps everything below it.
    app.add_middleware(PrometheusMiddleware)

    origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",") if o.strip()]

    # A wildcard origin combined with allow_credentials lets any site read an
    # authenticated response. We do NOT crash on it — refusing to boot over an
    # env var would take the whole API down for a misconfiguration — but we drop
    # credentials (auth here is a Bearer header, so nothing depends on them) and
    # shout in the logs until the origin list is set properly.
    wildcard = "*" in origins
    if wildcard:
        log_event(
            logger, logging.ERROR, "security.cors_wildcard",
            detail=(
                "CORS_ORIGINS='*' — any website can call this API. Set it to your "
                "frontend origin (e.g. https://app.example.com). Credentials are "
                "disabled meanwhile."
            ),
        )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=not wildcard,
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
