"""Prometheus metrics with a graceful no-op fallback.

If ``prometheus_client`` is missing, every metric becomes a no-op so the app
keeps running. Counter names are declared WITHOUT the ``_total`` suffix —
prometheus_client appends it, so the exposed series match the documented names
(e.g. ``ocr_requests`` -> ``ocr_requests_total``).
"""
from typing import Tuple

try:
    from prometheus_client import (
        Counter,
        Histogram,
        Gauge,
        generate_latest,
        CONTENT_TYPE_LATEST,
    )

    _ENABLED = True
except Exception:  # pragma: no cover - only when dependency missing
    _ENABLED = False


class _NoopMetric:
    def labels(self, *args, **kwargs):
        return self

    def inc(self, *args, **kwargs):
        pass

    def observe(self, *args, **kwargs):
        pass

    def set(self, *args, **kwargs):
        pass


def _counter(name, doc, labels=()):
    return Counter(name, doc, list(labels)) if _ENABLED else _NoopMetric()


def _histogram(name, doc, labels=(), buckets=None):
    if not _ENABLED:
        return _NoopMetric()
    if buckets is not None:
        return Histogram(name, doc, list(labels), buckets=buckets)
    return Histogram(name, doc, list(labels))


def _gauge(name, doc, labels=()):
    return Gauge(name, doc, list(labels)) if _ENABLED else _NoopMetric()


_DURATION_BUCKETS = (0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30, 60, 120)

# --- OCR metrics -----------------------------------------------------------
OCR_REQUESTS = _counter("ocr_requests", "OCR attempts by provider", ["provider"])
OCR_SUCCESS = _counter("ocr_success", "OCR successes by provider", ["provider"])
OCR_FAILURE = _counter("ocr_failure", "OCR failures by provider", ["provider"])
OCR_FALLBACK = _counter("ocr_fallback", "OCR fallbacks to the next provider", ["provider"])
OCR_TIMEOUT = _counter("ocr_timeout", "OCR timeouts by provider", ["provider"])
OCR_CIRCUIT_OPEN = _counter("ocr_circuit_open", "OCR circuit-breaker open events", ["provider"])
OCR_DURATION = _histogram(
    "ocr_processing_duration_seconds", "OCR processing duration", ["provider"], _DURATION_BUCKETS
)

# --- Restaurant business metrics ------------------------------------------
INVOICES_PROCESSED = _counter("invoices_processed", "Invoices processed through the pipeline")
INVOICE_LINES_PROCESSED = _counter("invoice_lines_processed", "Invoice lines processed")
PRODUCTS_MATCHED = _counter("products_matched", "Invoice lines auto-matched to a product")
PRODUCTS_MANUAL_REVIEW = _counter("products_manual_review", "Invoice lines flagged for manual review")
RECIPES_RECALCULATED = _counter("recipes_recalculated", "Recipe versions recomputed")
PRICE_CHANGES_DETECTED = _counter("price_changes_detected", "Price changes recorded from invoices")

# --- HTTP API metrics ------------------------------------------------------
REQUEST_COUNT = _counter("request_count", "HTTP requests", ["method", "endpoint", "status"])
REQUEST_DURATION = _histogram(
    "request_duration_seconds", "HTTP request duration", ["method", "endpoint"], _DURATION_BUCKETS
)
REQUEST_ERRORS = _counter("request_errors", "HTTP 5xx responses", ["method", "endpoint"])

# --- System / dependency health -------------------------------------------
DEPENDENCY_UP = _gauge("dependency_up", "1 if a dependency is healthy, else 0", ["dependency"])


def render_latest() -> Tuple[bytes, str]:
    """Return (payload, content_type) for the /metrics endpoint."""
    if not _ENABLED:
        return (
            b"# prometheus_client not installed; metrics disabled\n",
            "text/plain; charset=utf-8",
        )
    return generate_latest(), CONTENT_TYPE_LATEST


def metrics_enabled() -> bool:
    return _ENABLED
