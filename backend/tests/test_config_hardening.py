"""Fail-closed configuration guards: SECRET_KEY entropy and DATABASE_URL.

Both resolvers refuse to hand a deployment a weak/absent value, while keeping a
usable fallback under pytest/dev so the suite and a laptop never break.
"""
import pytest

from app.core import security
from app.db.session import _resolve_database_url, _DEV_FALLBACK


# --- SECRET_KEY entropy floor (F4) ------------------------------------------ #
def test_placeholder_secret_is_refused_in_a_deployment():
    with pytest.raises(RuntimeError):
        security._resolve_secret_key("changeme", under_pytest=False)


def test_short_secret_is_refused_in_a_deployment():
    with pytest.raises(RuntimeError):
        security._resolve_secret_key("hunter12", under_pytest=False)


def test_a_strong_secret_is_accepted():
    strong = "s" * security._MIN_SECRET_KEY_LEN
    assert security._resolve_secret_key(strong, under_pytest=False) == strong


def test_pytest_gets_a_usable_fallback_secret():
    assert security._resolve_secret_key("", under_pytest=True)
    # A short secret must not crash the test suite either.
    assert security._resolve_secret_key("short", under_pytest=True) == "short"


# --- DATABASE_URL fail-closed in production --------------------------------- #
def test_unset_database_url_fails_closed_in_production():
    with pytest.raises(RuntimeError):
        _resolve_database_url("", app_env="production", under_pytest=False)


def test_unset_database_url_falls_back_outside_production():
    assert _resolve_database_url("", "development", under_pytest=False) == _DEV_FALLBACK
    assert _resolve_database_url("", "production", under_pytest=True) == _DEV_FALLBACK


def test_an_explicit_database_url_is_always_honoured():
    url = "postgresql+psycopg2://u:p@db.example.com:5432/prod"
    assert _resolve_database_url(url, "production", under_pytest=False) == url
