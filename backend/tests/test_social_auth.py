"""Google / Apple identity-token verification (no Firebase, no network here).

The real JWKS verification is exercised end-to-end against the providers; here
we test the configuration gate and the claims -> SocialIdentity mapping, which
is the logic we own.
"""
import pytest

from app.services import social_auth


def test_google_raises_when_no_client_ids_configured(monkeypatch):
    monkeypatch.delenv("GOOGLE_CLIENT_IDS", raising=False)
    with pytest.raises(social_auth.SocialAuthNotConfigured):
        social_auth.verify_google("a.b.c")


def test_apple_raises_when_no_client_ids_configured(monkeypatch):
    monkeypatch.delenv("APPLE_CLIENT_IDS", raising=False)
    with pytest.raises(social_auth.SocialAuthNotConfigured):
        social_auth.verify_apple("a.b.c")


def test_google_claims_are_mapped_and_email_normalized(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_IDS", "client-1")
    monkeypatch.setattr(
        social_auth, "_verify",
        lambda *a, **k: {"sub": "123", "email": "  User@Ex.COM ",
                         "email_verified": True, "name": "U"},
    )
    ident = social_auth.verify_google("tok")
    assert ident.provider == "google"
    assert ident.subject == "123"
    assert ident.email == "user@ex.com"        # normalized (strip + lower)
    assert ident.email_verified is True
    assert ident.name == "U"


def test_apple_email_verified_accepts_the_string_true(monkeypatch):
    # Apple sends email_verified as the string "true"/"false".
    monkeypatch.setenv("APPLE_CLIENT_IDS", "bundle-1")
    monkeypatch.setattr(
        social_auth, "_verify",
        lambda *a, **k: {"sub": "a1", "email": "x@y.com", "email_verified": "true"},
    )
    ident = social_auth.verify_apple("tok")
    assert ident.provider == "apple"
    assert ident.subject == "a1"
    assert ident.email_verified is True


def test_audiences_parses_comma_separated_env(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_IDS", " a , b ,, c ")
    assert social_auth._audiences("GOOGLE_CLIENT_IDS") == ["a", "b", "c"]
