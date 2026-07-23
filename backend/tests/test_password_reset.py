"""Self-service password recovery — the launch blocker this closes.

The "mot de passe oublié" screen used to be a placeholder: a sole admin who
forgot their password was locked out for good. These tests pin the security
properties of the real flow (endpoint behaviour, stubbed at the DB/crud/mailer
seams so no Postgres is required — same pattern as test_rgpd.py).
"""
from types import SimpleNamespace as N

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import get_db
from app.api.api_v1.endpoints import auth as auth_ep
from app.crud import crud_password_reset


class _FakeDB:
    """Enough of a Session for the endpoints: query(...).filter(...).first()."""
    def __init__(self, user=None):
        self._user = user

    def query(self, *a):
        return self

    def filter(self, *a):
        return self

    def first(self):
        return self._user

    def add(self, *a):
        pass

    def commit(self):
        pass


# --------------------------------------------------------------------------- #
# hash_token: deterministic, and never the token itself.
# --------------------------------------------------------------------------- #
def test_only_the_hash_is_ever_stored():
    h = crud_password_reset.hash_token("abc123")
    assert h == crud_password_reset.hash_token("abc123")  # deterministic
    assert h != "abc123" and len(h) == 64  # sha256 hex, not the plaintext
    assert crud_password_reset.hash_token("abc123") != crud_password_reset.hash_token("abc124")


# --------------------------------------------------------------------------- #
# forgot-password: the same answer whether or not the account exists.
# --------------------------------------------------------------------------- #
def _client_with_db(user):
    app.dependency_overrides[get_db] = lambda: _FakeDB(user)
    return TestClient(app)


def test_forgot_password_never_reveals_whether_the_account_exists(monkeypatch):
    sent = []
    created = []
    monkeypatch.setattr(auth_ep.mailer, "send_password_reset_email", lambda to, tok: sent.append(to))
    monkeypatch.setattr(auth_ep.crud_password_reset, "create_for_user", lambda db, uid: created.append(uid) or "tok")
    monkeypatch.setattr(auth_ep.rgpd, "record", lambda *a, **k: None)

    try:
        # Unknown email -> generic 200, nothing sent.
        monkeypatch.setattr(auth_ep.crud_user, "get_user_by_email", lambda db, e: None)
        r1 = _client_with_db(None).post("/api/v1/auth/forgot-password", json={"email": "ghost@x.com"})

        # Known password account -> same generic 200, a link IS minted + sent.
        user = N(id="u1", tenant_id="t1", email="chef@x.com", password_hash="$2b$hash")
        monkeypatch.setattr(auth_ep.crud_user, "get_user_by_email", lambda db, e: user)
        r2 = _client_with_db(user).post("/api/v1/auth/forgot-password", json={"email": "chef@x.com"})

        assert r1.status_code == 200 and r2.status_code == 200
        assert r1.json() == r2.json(), "the response must be identical (no user enumeration)"
        assert sent == ["chef@x.com"] and created == ["u1"], "only the real account triggers a mail"
    finally:
        app.dependency_overrides.clear()


def test_forgot_password_ignores_social_accounts_without_a_password(monkeypatch):
    sent = []
    monkeypatch.setattr(auth_ep.mailer, "send_password_reset_email", lambda to, tok: sent.append(to))
    monkeypatch.setattr(auth_ep.crud_password_reset, "create_for_user", lambda db, uid: "tok")
    monkeypatch.setattr(auth_ep.rgpd, "record", lambda *a, **k: None)
    social = N(id="u2", tenant_id="t1", email="apple@x.com", password_hash=None)
    monkeypatch.setattr(auth_ep.crud_user, "get_user_by_email", lambda db, e: social)
    try:
        r = _client_with_db(social).post("/api/v1/auth/forgot-password", json={"email": "apple@x.com"})
        assert r.status_code == 200
        assert sent == [], "a password-less (social) account has no password to reset"
    finally:
        app.dependency_overrides.clear()


# --------------------------------------------------------------------------- #
# reset-password: strength, token validity, single-use, session revocation.
# --------------------------------------------------------------------------- #
def test_reset_password_rejects_a_weak_password(monkeypatch):
    monkeypatch.setattr(auth_ep.crud_password_reset, "get_valid", lambda db, t: N(user_id="u1"))
    try:
        r = _client_with_db(N(id="u1", tenant_id="t1", token_version=0, password_hash="x")).post(
            "/api/v1/auth/reset-password", json={"token": "a" * 20, "password": "short"}
        )
        assert r.status_code == 400
    finally:
        app.dependency_overrides.clear()


def test_reset_password_rejects_an_invalid_or_expired_token(monkeypatch):
    monkeypatch.setattr(auth_ep.crud_password_reset, "get_valid", lambda db, t: None)
    try:
        r = _client_with_db(None).post(
            "/api/v1/auth/reset-password", json={"token": "b" * 20, "password": "Strong123"}
        )
        assert r.status_code == 400
        assert "invalide ou expir" in r.json()["detail"].lower()
    finally:
        app.dependency_overrides.clear()


def test_reset_password_sets_hash_bumps_version_and_consumes_the_token(monkeypatch):
    user = N(id="u1", tenant_id="t1", token_version=3, password_hash="OLD")
    row = N(user_id="u1", used_at=None)
    monkeypatch.setattr(auth_ep.crud_password_reset, "get_valid", lambda db, t: row)
    monkeypatch.setattr(auth_ep.rgpd, "record", lambda *a, **k: None)
    app.dependency_overrides[get_db] = lambda: _FakeDB(user)
    try:
        r = TestClient(app).post(
            "/api/v1/auth/reset-password", json={"token": "c" * 20, "password": "Strong123"}
        )
        assert r.status_code == 200
        assert user.password_hash not in (None, "OLD"), "the password hash must change"
        assert user.token_version == 4, "every existing session must be revoked"
        assert row.used_at is not None, "the token must be single-use"
    finally:
        app.dependency_overrides.clear()
