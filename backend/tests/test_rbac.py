import pytest
from fastapi import HTTPException

from fastapi.testclient import TestClient

from app.api.deps import require_roles
from app.main import app


def test_writer_allows_manager():
    checker = require_roles("admin", "manager")
    assert checker(roles=["manager"]) == ["manager"]


def test_writer_allows_admin():
    checker = require_roles("admin", "manager")
    assert checker(roles=["admin", "viewer"]) == ["admin", "viewer"]


def test_writer_rejects_viewer():
    checker = require_roles("admin", "manager")
    with pytest.raises(HTTPException) as exc:
        checker(roles=["viewer"])
    assert exc.value.status_code == 403


def test_writer_rejects_no_roles():
    checker = require_roles("admin", "manager")
    with pytest.raises(HTTPException) as exc:
        checker(roles=[])
    assert exc.value.status_code == 403


# --------------------------------------------------------------------------- #
# Admin password reset — the "mot de passe oublié" screen now points here
# --------------------------------------------------------------------------- #
def test_reset_password_requires_admin():
    from app.api.deps import get_current_roles, get_current_user
    from types import SimpleNamespace as N

    app.dependency_overrides[get_current_user] = lambda: N(
        id="u1", tenant_id="t1", token_version=0
    )
    app.dependency_overrides[get_current_roles] = lambda: ["manager"]  # not admin
    try:
        client = TestClient(app)
        resp = client.post(
            "/api/v1/auth/users/u2/reset-password", json={"password": "unNouveauMdp1"}
        )
        assert resp.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_reset_password_refuses_a_weak_password():
    from app.api.deps import get_current_roles, get_current_user
    from types import SimpleNamespace as N

    app.dependency_overrides[get_current_user] = lambda: N(
        id="u1", tenant_id="t1", token_version=0
    )
    app.dependency_overrides[get_current_roles] = lambda: ["admin"]
    try:
        client = TestClient(app)
        resp = client.post("/api/v1/auth/users/u2/reset-password", json={"password": "court"})
        # 400 (too short) or 404 (user not found) — never 200 on a 5-char password
        assert resp.status_code in (400, 404)
    finally:
        app.dependency_overrides.clear()
