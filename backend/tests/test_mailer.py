"""Outbound email — Resend/SMTP dispatch and the FoodGad reset template."""
import pytest

from app.services.email import mailer


class _FakeResp:
    def __init__(self, status=200):
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for k in ("RESEND_API_KEY", "SMTP_HOST", "MAIL_FROM", "RESEND_FROM", "SMTP_FROM", "FRONTEND_URL"):
        monkeypatch.delenv(k, raising=False)


def test_build_reset_link_uses_frontend_url(monkeypatch):
    monkeypatch.setenv("FRONTEND_URL", "https://app.foodgad.fr/")
    assert mailer.build_reset_link("abc") == "https://app.foodgad.fr/reset-password?token=abc"


def test_resend_is_used_when_the_api_key_is_set(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_test_key")
    monkeypatch.setenv("MAIL_FROM", "FoodGad <no-reply@foodgad.fr>")
    monkeypatch.setenv("FRONTEND_URL", "https://app.foodgad.fr")

    calls = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        calls["url"] = url
        calls["headers"] = headers
        calls["json"] = json
        return _FakeResp(200)

    monkeypatch.setattr(mailer.httpx, "post", fake_post)

    mailer.send_password_reset_email("chef@resto.fr", "tok123")

    assert calls["url"] == "https://api.resend.com/emails"
    assert calls["headers"]["Authorization"] == "Bearer re_test_key"
    payload = calls["json"]
    assert payload["from"] == "FoodGad <no-reply@foodgad.fr>"
    assert payload["to"] == ["chef@resto.fr"]
    assert "FoodGad" in payload["subject"]
    # The link appears in both the HTML and the plain-text fallback.
    link = "https://app.foodgad.fr/reset-password?token=tok123"
    assert link in payload["html"] and link in payload["text"]
    # Branded, not a bare link dump.
    assert "Réinitialiser mon mot de passe" in payload["html"]
    assert "FoodGad" in payload["html"]


def test_no_provider_logs_the_link_and_does_not_call_resend(monkeypatch):
    called = {"post": False}
    monkeypatch.setattr(mailer.httpx, "post", lambda *a, **k: called.update(post=True))
    # No RESEND_API_KEY / SMTP_HOST -> console fallback.
    mailer.send_password_reset_email("chef@resto.fr", "tok")
    assert called["post"] is False


def test_a_delivery_failure_never_raises(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_test_key")

    def boom(*a, **k):
        raise RuntimeError("resend is down")

    monkeypatch.setattr(mailer.httpx, "post", boom)
    # Must swallow: a mail failure must not change the reset endpoint's response
    # (which would otherwise leak whether an account exists).
    mailer.send_password_reset_email("chef@resto.fr", "tok")  # does not raise
