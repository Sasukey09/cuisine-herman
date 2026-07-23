import pytest

from app.services.customization import reports_service as rs


# Patch the products builder with a fixed dataset so the engine is tested in isolation.
SAMPLE = [
    {"name": "Tomate", "sku": "T1", "category_id": 1, "latest_price": 2.0, "created_at": "2026-01-01"},
    {"name": "Beurre", "sku": "B1", "category_id": 2, "latest_price": 8.0, "created_at": "2026-02-01"},
    {"name": "Tomate cerise", "sku": "T2", "category_id": 1, "latest_price": 5.0, "created_at": "2026-03-01"},
]


@pytest.fixture
def patched(monkeypatch):
    monkeypatch.setitem(rs.SOURCES["products"], "builder", lambda db, t: list(SAMPLE))


def run(definition):
    return rs.run_report(db=None, tenant_id="t1", definition=definition)


def test_available_sources_shape():
    sources = rs.available_sources()
    keys = {s["key"] for s in sources}
    assert keys == {"products", "recipes", "invoices"}
    assert all("columns" in s for s in sources)


def test_projection_and_count(patched):
    out = run({"source": "products", "columns": ["name", "latest_price"]})
    assert out["count"] == 3
    assert set(out["rows"][0].keys()) == {"name", "latest_price"}
    assert [c["key"] for c in out["columns"]] == ["name", "latest_price"]


def test_filter_gte_numeric(patched):
    out = run({
        "source": "products",
        "columns": ["name"],
        "filters": [{"field": "latest_price", "op": "gte", "value": 5}],
    })
    assert sorted(r["name"] for r in out["rows"]) == ["Beurre", "Tomate cerise"]


def test_filter_contains(patched):
    out = run({
        "source": "products",
        "columns": ["name"],
        "filters": [{"field": "name", "op": "contains", "value": "tomate"}],
    })
    assert sorted(r["name"] for r in out["rows"]) == ["Tomate", "Tomate cerise"]


def test_sort_and_limit(patched):
    out = run({
        "source": "products",
        "columns": ["name", "latest_price"],
        "sort": {"field": "latest_price", "dir": "desc"},
        "limit": 2,
    })
    assert [r["latest_price"] for r in out["rows"]] == [8.0, 5.0]


def test_validate_rejects_bad_source():
    with pytest.raises(rs.ReportError):
        rs.validate_definition({"source": "secret_table", "columns": []})


def test_validate_rejects_unknown_column():
    with pytest.raises(rs.ReportError):
        rs.validate_definition({"source": "products", "columns": ["password"]})


def test_validate_rejects_bad_operator():
    with pytest.raises(rs.ReportError):
        rs.validate_definition(
            {"source": "products", "filters": [{"field": "name", "op": "DROP", "value": 1}]}
        )


def test_a_viewer_cannot_run_reports():
    """Regression: /reports/run and /{id}/run were the only report routes without
    `require_writer`. Running a report fans out to a per-product latest-price
    lookup (up to the source cap), so a read-only viewer could hammer it as a
    cheap DB-load amplifier. Both run routes must now refuse a viewer (403)."""
    from fastapi.testclient import TestClient
    from app.main import app
    from app.api.deps import get_current_tenant_id, get_current_roles

    app.dependency_overrides[get_current_tenant_id] = lambda: "t1"
    app.dependency_overrides[get_current_roles] = lambda: ["viewer"]
    try:
        client = TestClient(app)
        adhoc = client.post("/api/v1/reports/run", json={"source": "products", "columns": ["name"]})
        saved = client.get("/api/v1/reports/some-id/run")
        assert adhoc.status_code == 403, "a viewer must not run an ad-hoc report"
        assert saved.status_code == 403, "a viewer must not run a saved report"
    finally:
        app.dependency_overrides.clear()
