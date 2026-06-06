import os
from fastapi.testclient import TestClient
from app.main import app
from app.api.deps import get_current_tenant_id


def test_invoice_extract_endpoint():
    # Ensure provider is Mistral for predictable sample
    os.environ['OCR_PROVIDER'] = 'mistral'
    # Override auth so the test does not need a DB-backed user.
    app.dependency_overrides[get_current_tenant_id] = lambda: "test-tenant"
    try:
        client = TestClient(app)
        # create a dummy file (content irrelevant for stub provider)
        files = {"file": ("invoice.pdf", b"%PDF-1.4 fake content", "application/pdf")}
        resp = client.post("/api/v1/invoices/extract", files=files)
        assert resp.status_code == 200
        data = resp.json()
        assert 'supplier' in data
        assert 'lines' in data
        assert isinstance(data['lines'], list)
    finally:
        app.dependency_overrides.clear()
