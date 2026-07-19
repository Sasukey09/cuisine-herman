"""I2 — registration hardening: email format, strong password, rate limiting."""
from types import SimpleNamespace as N

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.core import security
from app.schemas.schemas import RegisterRequest, CreateUserRequest
from app.db.session import get_db
from app.core.rate_limit import reset_quota_guard


# --- password policy -------------------------------------------------------- #
def test_password_policy_rejects_weak_and_accepts_strong():
    assert security.password_error("") is not None
    assert security.password_error("court") is not None          # < 8
    assert security.password_error("abcdefgh") is not None        # no digit
    assert security.password_error("12345678") is not None        # no letter
    assert security.password_error("motdepasse1") is None         # 8+, letter+digit


def test_email_policy_and_normalization():
    assert security.email_error("pasunemail") is not None
    assert security.email_error("a@b") is not None
    assert security.email_error("chef@resto.fr") is None
    assert security.normalize_email("  CHEF@Resto.FR ") == "chef@resto.fr"


# --- schema validation (422 path) ------------------------------------------- #
def test_register_schema_rejects_weak_password():
    with pytest.raises(ValidationError):
        RegisterRequest(email="chef@resto.fr", password="court", org_name="Resto")


def test_register_schema_rejects_bad_email():
    with pytest.raises(ValidationError):
        RegisterRequest(email="pasunemail", password="motdepasse1", org_name="Resto")


def test_register_schema_normalizes_email():
    r = RegisterRequest(email="  CHEF@Resto.FR ", password="motdepasse1", org_name="Resto")
    assert r.email == "chef@resto.fr"


def test_create_user_schema_enforces_same_policy():
    with pytest.raises(ValidationError):
        CreateUserRequest(email="chef@resto.fr", password="weak")   # no digit / short
    ok = CreateUserRequest(email="X@Resto.FR", password="motdepasse1", role="manager")
    assert ok.email == "x@resto.fr"


# --- rate limiting (429 after the per-IP hourly cap) ------------------------ #
def test_register_is_rate_limited_per_ip(monkeypatch):
    monkeypatch.setenv("REGISTER_PER_HOUR", "2")
    reset_quota_guard()  # start from a clean window

    from app.api.api_v1.endpoints import auth as endpoint

    monkeypatch.setattr(endpoint.crud_user, "get_user_by_email", lambda db, e: None)
    monkeypatch.setattr(
        endpoint.crud_user, "create_organization", lambda db, name: N(id="org1")
    )
    monkeypatch.setattr(
        endpoint.crud_rbac, "ensure_default_roles", lambda db, oid: {"admin": N(id="role1")}
    )
    monkeypatch.setattr(
        endpoint.crud_user, "create_user",
        lambda db, tenant_id, email, password, name=None: N(
            id="u1", email=email, name=name, tenant_id=tenant_id
        ),
    )
    monkeypatch.setattr(endpoint.crud_rbac, "assign_role", lambda db, uid, rid: None)

    app.dependency_overrides[get_db] = lambda: object()
    try:
        client = TestClient(app)
        body = {"email": "chef@resto.fr", "password": "motdepasse1", "org_name": "Resto"}

        statuses = [client.post("/api/v1/auth/register", json=body).status_code
                    for _ in range(3)]
        # 2 allowed per hour, the 3rd from the same IP is throttled
        assert statuses[0] == 201 and statuses[1] == 201
        assert statuses[2] == 429
    finally:
        app.dependency_overrides.pop(get_db, None)
        reset_quota_guard()


# --- login email normalization (regression: iOS case/space) ----------------- #
def test_login_normalizes_email_like_registration(monkeypatch):
    """An account is stored with a lowercased email at signup. Login used to
    compare the RAW username (case/space sensitive), so the same account typed
    with a capital (common on iOS) failed to log in while register still said
    'email already used'. Login must normalize the email the same way."""
    from app.api.api_v1.endpoints import auth as endpoint
    from app.core.rate_limit import reset_login_guard

    reset_login_guard()
    seen = {}
    fake_user = N(id="u1", tenant_id="t1", token_version=0, password_hash="hash")

    def fake_get(db, email):
        seen["email"] = email
        return fake_user

    monkeypatch.setattr(endpoint.crud_user, "get_user_by_email", fake_get)
    monkeypatch.setattr(endpoint.security, "verify_password_constant_time", lambda p, h: True)
    monkeypatch.setattr(endpoint.rgpd, "record", lambda *a, **k: None)

    app.dependency_overrides[get_db] = lambda: object()
    try:
        client = TestClient(app)
        resp = client.post(
            "/api/v1/auth/token",
            data={"username": "  Mixed.Case@Example.COM ", "password": "whatever"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json().get("access_token")
        # The lookup must have received the normalized (stripped + lowercased) email.
        assert seen["email"] == "mixed.case@example.com"
    finally:
        app.dependency_overrides.pop(get_db, None)
        reset_login_guard()
