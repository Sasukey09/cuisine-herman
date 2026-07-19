import logging
import os
import sys
from typing import Optional

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

APP_NAME = "FoodGad API"

logger = get_logger(__name__)


def _metrics_access_status(
    expected: Optional[str], sent: str, app_env: str, under_pytest: bool
) -> Optional[int]:
    """Decide whether a /metrics request may pass. Returns None to allow, or the
    HTTP status to deny with.

    - a token is configured  -> require an exact Bearer match (else 401)
    - no token, production    -> fail CLOSED (404, hides the endpoint) so a missing
                                 METRICS_TOKEN can never expose the scrape surface
    - no token, dev/pytest    -> open (developer convenience)
    """
    if expected:
        return None if sent == expected else 401
    if under_pytest:
        return None
    if app_env == "production":
        return 404
    return None


def _docs_config(app_env: str, under_pytest: bool) -> dict:
    """FastAPI docs/redoc/openapi URLs. Interactive docs + the OpenAPI schema map
    every route/param/schema (auth, RBAC, RGPD erase, invoice ingest) — free
    reconnaissance in prod — so they are served only outside production (dev or
    pytest), mirroring the /metrics fail-closed posture."""
    if under_pytest or app_env != "production":
        return {
            "docs_url": "/docs",
            "redoc_url": "/redoc",
            "openapi_url": "/openapi.json",
        }
    return {"docs_url": None, "redoc_url": None, "openapi_url": None}


def _init_sentry() -> None:
    """Error reporting. Inert until SENTRY_DSN is set, so nothing changes for a
    deployment that has not opted in — and `console.error` stops being the only
    place a production crash is ever seen."""
    dsn = os.getenv("SENTRY_DSN")
    if not dsn:
        return
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration

        sentry_sdk.init(
            dsn=dsn,
            environment=os.getenv("APP_ENV", "production"),
            traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.05")),
            # Bodies can carry an invoice, a password reset, a chat message.
            send_default_pii=False,
            integrations=[FastApiIntegration()],
        )
        log_event(logger, logging.INFO, "sentry.enabled")
    except Exception as exc:  # a broken reporter must not take the app down
        log_event(logger, logging.WARNING, "sentry.init_failed", error=str(exc))


def create_app() -> FastAPI:
    _init_sentry()

    under_pytest = "PYTEST_CURRENT_TEST" in os.environ or "pytest" in sys.modules
    app = FastAPI(
        title=APP_NAME,
        **_docs_config(os.getenv("APP_ENV", "production"), under_pytest),
    )

    @app.middleware("http")
    async def _security_headers(request: Request, call_next):
        """Defence-in-depth response headers. This API answers JSON to a
        Bearer-authenticated SPA/mobile client, so none of these alter a body,
        status or behaviour — they only harden the browser that receives them."""
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault(
            "Referrer-Policy", "strict-origin-when-cross-origin"
        )
        response.headers.setdefault("Content-Security-Policy", "frame-ancestors 'none'")
        # The platform terminates TLS in prod; harmless when already HTTPS.
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=63072000; includeSubDomains"
        )
        return response

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
    def prometheus_metrics(request: Request):
        """Prometheus scrape endpoint.

        Request counts, latencies and error rates per route are a free map of the
        app for anyone probing it. Access rules (see `_metrics_access_status`):
        with METRICS_TOKEN set, the scraper must send `Authorization: Bearer
        <token>`; with no token in production the endpoint fails CLOSED (404), so
        a forgotten token can never expose it; open only in dev/pytest.
        In production METRICS_TOKEN is provisioned automatically (render.yaml).
        """
        expected = os.getenv("METRICS_TOKEN")
        sent = (request.headers.get("authorization") or "").removeprefix("Bearer ").strip()
        under_pytest = "PYTEST_CURRENT_TEST" in os.environ or "pytest" in sys.modules
        deny = _metrics_access_status(
            expected, sent, os.getenv("APP_ENV", "production"), under_pytest
        )
        if deny is not None:
            return JSONResponse(status_code=deny, content={"detail": "Not found"})
        payload, content_type = metrics.render_latest()
        return Response(content=payload, media_type=content_type)

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)), reload=True)
