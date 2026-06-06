"""HTTP metrics middleware: request_count, request_duration, request_errors."""
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core import metrics

# Paths excluded from metrics to avoid self-instrumentation / noise.
_EXCLUDED = {"/metrics", "/health", "/live", "/ready", "/favicon.ico"}


def _endpoint_label(request: Request) -> str:
    """Use the matched route template (low cardinality), not the raw URL."""
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    if path:
        return path
    return "unmatched"


class PrometheusMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in _EXCLUDED:
            return await call_next(request)

        method = request.method
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            endpoint = _endpoint_label(request)
            duration = time.perf_counter() - start
            metrics.REQUEST_COUNT.labels(method, endpoint, str(status)).inc()
            metrics.REQUEST_DURATION.labels(method, endpoint).observe(duration)
            if status >= 500:
                metrics.REQUEST_ERRORS.labels(method, endpoint).inc()
