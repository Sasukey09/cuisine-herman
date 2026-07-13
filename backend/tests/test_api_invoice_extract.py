from fastapi.testclient import TestClient

from app.main import app
from app.api.deps import get_current_tenant_id

FILES = {"file": ("invoice.pdf", b"%PDF-1.4 fake content", "application/pdf")}


def test_invoice_extract_endpoint(monkeypatch):
    """The endpoint's plumbing, exercised against the canned stub provider.

    The stub is opted into *explicitly*: production now defaults to stub OFF, so
    a provider outage surfaces as an error instead of a fabricated invoice.
    """
    monkeypatch.setenv("OCR_PROVIDER_CHAIN", "stub")
    monkeypatch.setenv("OCR_ALLOW_STUB_FALLBACK", "true")

    # Override auth so the test does not need a DB-backed user.
    app.dependency_overrides[get_current_tenant_id] = lambda: "test-tenant"
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
    try:
        client = TestClient(app)
        resp = client.post("/api/v1/invoices/extract", files=FILES)
        assert resp.status_code == 502, "an OCR outage must surface, not be papered over"
        assert "lines" not in resp.json()
    finally:
        app.dependency_overrides.clear()
