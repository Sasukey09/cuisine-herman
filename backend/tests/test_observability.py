import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api import health
from app.core import metrics

client = TestClient(app)


# --- liveness / health -----------------------------------------------------

def test_live():
    r = client.get("/live")
    assert r.status_code == 200
    assert r.json() == {"status": "alive"}


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# --- metrics endpoint ------------------------------------------------------

def test_metrics_endpoint_responds():
    r = client.get("/metrics")
    assert r.status_code == 200


@pytest.mark.skipif(not metrics.metrics_enabled(), reason="prometheus_client not installed")
def test_metrics_records_http_requests():
    # /openapi.json is not excluded from instrumentation
    client.get("/openapi.json")
    body = client.get("/metrics").text
    assert "request_count_total" in body
    assert "request_duration_seconds" in body


# --- readiness -------------------------------------------------------------

def _patch_all(monkeypatch, postgres=(True, None), redis=(True, None), s3=(True, None), ocr=(True, None)):
    monkeypatch.setattr(health, "check_postgres", lambda: postgres)
    monkeypatch.setattr(health, "check_redis", lambda: redis)
    monkeypatch.setattr(health, "check_s3", lambda: s3)
    monkeypatch.setattr(health, "check_ocr", lambda: ocr)


def test_ready_all_up(monkeypatch):
    _patch_all(monkeypatch)
    r = client.get("/ready")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ready"
    assert all(c["status"] == "up" for c in data["checks"].values())


def test_ready_critical_down_returns_503(monkeypatch):
    _patch_all(monkeypatch, postgres=(False, "connection refused"))
    r = client.get("/ready")
    assert r.status_code == 503
    data = r.json()
    assert data["status"] == "not_ready"
    assert data["checks"]["postgres"]["status"] == "down"


def test_ready_noncritical_down_still_ready(monkeypatch):
    # S3 down is non-critical -> overall still ready (200)
    _patch_all(monkeypatch, s3=(False, "minio unreachable"))
    r = client.get("/ready")
    assert r.status_code == 200
    assert r.json()["checks"]["s3"]["status"] == "down"


def test_ready_skipped_dependency(monkeypatch):
    _patch_all(monkeypatch, s3=(None, "not configured"))
    r = client.get("/ready")
    assert r.status_code == 200
    assert r.json()["checks"]["s3"]["status"] == "skipped"


# --- I1: /metrics access control (fail-closed in production) ----------------

from app.main import _metrics_access_status


def test_metrics_requires_matching_token_when_configured():
    # token set: exact Bearer match required
    assert _metrics_access_status("s3cr3t", "s3cr3t", "production", False) is None
    assert _metrics_access_status("s3cr3t", "wrong", "production", False) == 401
    assert _metrics_access_status("s3cr3t", "", "production", False) == 401


def test_metrics_fails_closed_in_production_without_token():
    # no token + production + not a test -> 404 (endpoint hidden, never exposed)
    assert _metrics_access_status(None, "", "production", False) == 404


def test_metrics_open_in_dev_or_under_pytest_without_token():
    assert _metrics_access_status(None, "", "development", False) is None
    assert _metrics_access_status(None, "", "production", True) is None
