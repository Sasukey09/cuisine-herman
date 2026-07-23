from fastapi.testclient import TestClient

from app.main import app
from app.api.deps import get_current_tenant_id, require_writer

FILES = {"file": ("invoice.pdf", b"%PDF-1.4 fake content", "application/pdf")}


def test_invoice_extract_endpoint(monkeypatch):
    """The endpoint's plumbing, exercised against the canned stub provider.

    The stub is opted into *explicitly*: production now defaults to stub OFF, so
    a provider outage surfaces as an error instead of a fabricated invoice.
    """
    monkeypatch.setenv("OCR_PROVIDER_CHAIN", "stub")
    monkeypatch.setenv("OCR_ALLOW_STUB_FALLBACK", "true")

    # Override auth so the test does not need a DB-backed user. `require_writer`
    # must be overridden too: the route now refuses read-only `viewer` accounts,
    # which used to be able to burn the paid OCR quota.
    app.dependency_overrides[get_current_tenant_id] = lambda: "test-tenant"
    app.dependency_overrides[require_writer] = lambda: ["admin"]
    try:
        client = TestClient(app)
        resp = client.post("/api/v1/invoices/extract", files=FILES)
        assert resp.status_code == 200
        data = resp.json()
        assert "supplier" in data
        assert "lines" in data
        assert isinstance(data["lines"], list)
    finally:
        app.dependency_overrides.clear()


def test_an_ocr_outage_never_fabricates_an_invoice(monkeypatch):
    """No provider available + stub disabled => a real error, not fake lines.

    This is the guarantee that matters financially: canned lines would be
    priced, written to the purchase ledger, and propagated into every recipe
    cost derived from them. Failing loudly beats corrupting silently.
    """
    monkeypatch.setenv("OCR_PROVIDER_CHAIN", "mistral,google")
    monkeypatch.setenv("OCR_ALLOW_STUB_FALLBACK", "false")
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    monkeypatch.delenv("GCP_PROJECT_ID", raising=False)

    app.dependency_overrides[get_current_tenant_id] = lambda: "test-tenant"
    app.dependency_overrides[require_writer] = lambda: ["admin"]
    try:
        client = TestClient(app)
        resp = client.post("/api/v1/invoices/extract", files=FILES)
        assert resp.status_code == 502, "an OCR outage must surface, not be papered over"
        assert "lines" not in resp.json()
    finally:
        app.dependency_overrides.clear()


def test_ocr_error_mapping_distinguishes_unreadable_from_outage():
    """Regression: a blurry/blank photo (a provider RAN but couldn't read it)
    must return 422 with an actionable message, not the misleading 502
    'Service OCR indisponible'. A real outage (no provider configured / all down)
    stays 502."""
    from app.api.api_v1.endpoints.invoices import _ocr_http_error
    from app.services.ocr.errors import (
        AllProvidersFailedError,
        OcrConfigurationError,
        OcrTransientError,
        OcrError,
    )

    # A provider ran and failed to extract -> unreadable document -> 422.
    unreadable = AllProvidersFailedError([("mistral", OcrTransientError("garbled"))])
    assert unreadable.all_configuration_errors is False
    assert _ocr_http_error(unreadable).status_code == 422

    # Every provider unusable (no key) -> genuine outage -> 502.
    outage = AllProvidersFailedError([
        ("mistral", OcrConfigurationError("no key")),
        ("google", OcrConfigurationError("no key")),
    ])
    assert outage.all_configuration_errors is True
    assert _ocr_http_error(outage).status_code == 502

    # No providers at all -> outage -> 502.
    assert _ocr_http_error(AllProvidersFailedError([])).status_code == 502
    # Any other OCR error -> 502.
    assert _ocr_http_error(OcrError("generic")).status_code == 502


def test_a_read_only_viewer_cannot_burn_the_ocr_quota():
    """The RBAC hole this closed.

    /invoices/extract was the ONLY expensive route without `require_writer`, so
    an account documented as "read-only" could call a paid OCR provider on loop.
    """
    from app.api.deps import get_current_roles

    app.dependency_overrides[get_current_tenant_id] = lambda: "test-tenant"
    app.dependency_overrides[get_current_roles] = lambda: ["viewer"]
    try:
        client = TestClient(app)
        resp = client.post("/api/v1/invoices/extract", files=FILES)
        assert resp.status_code == 403
    finally:
        app.dependency_overrides.clear()
