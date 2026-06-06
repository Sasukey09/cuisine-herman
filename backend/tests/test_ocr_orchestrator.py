import pytest

from app.services.ocr.orchestrator import OcrOrchestrator
from app.services.ocr.provider import OCRProvider
from app.services.ocr.schemas import OcrResult
from app.services.ocr.errors import OcrTransientError, AllProvidersFailedError


class FakeProvider(OCRProvider):
    def __init__(self, name, behavior, configured=True):
        self.name = name
        self._behavior = behavior
        self._configured = configured
        self.calls = 0

    def is_configured(self):
        return self._configured

    def extract_document(self, file_bytes, content_type=None):
        self.calls += 1
        if isinstance(self._behavior, Exception):
            raise self._behavior
        return self._behavior


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("OCR_PROVIDER_CHAIN", "mistral,google")
    monkeypatch.setenv("OCR_ALLOW_STUB_FALLBACK", "false")
    monkeypatch.setenv("OCR_MAX_RETRIES", "1")
    monkeypatch.setenv("OCR_RETRY_BACKOFF", "0")
    monkeypatch.setenv("OCR_TIMEOUT_SECONDS", "5")
    monkeypatch.setenv("OCR_CB_FAIL_THRESHOLD", "2")


def _ok(provider):
    return OcrResult(provider=provider, text=f"text from {provider}")


def test_uses_first_provider_on_success(env):
    mistral = FakeProvider("mistral", _ok("mistral"))
    google = FakeProvider("google", _ok("google"))
    orch = OcrOrchestrator(providers={"mistral": mistral, "google": google})

    result = orch.run(b"bytes")
    assert result.provider == "mistral"
    assert google.calls == 0


def test_falls_back_to_google_on_transient_failure(env):
    mistral = FakeProvider("mistral", OcrTransientError("boom"))
    google = FakeProvider("google", _ok("google"))
    orch = OcrOrchestrator(providers={"mistral": mistral, "google": google})

    result = orch.run(b"bytes")
    assert result.provider == "google"
    assert mistral.calls == 2  # initial + 1 retry before giving up
    assert google.calls == 1


def test_skips_unconfigured_provider(env):
    mistral = FakeProvider("mistral", _ok("mistral"), configured=False)
    google = FakeProvider("google", _ok("google"))
    orch = OcrOrchestrator(providers={"mistral": mistral, "google": google})

    result = orch.run(b"bytes")
    assert result.provider == "google"
    assert mistral.calls == 0


def test_all_providers_fail_raises_user_error(env):
    mistral = FakeProvider("mistral", OcrTransientError("a"))
    google = FakeProvider("google", OcrTransientError("b"))
    orch = OcrOrchestrator(providers={"mistral": mistral, "google": google})

    with pytest.raises(AllProvidersFailedError):
        orch.run(b"bytes")


def test_stub_fallback_when_enabled(monkeypatch):
    monkeypatch.setenv("OCR_PROVIDER_CHAIN", "mistral,google")
    monkeypatch.setenv("OCR_ALLOW_STUB_FALLBACK", "true")
    monkeypatch.setenv("OCR_MAX_RETRIES", "0")
    monkeypatch.setenv("OCR_RETRY_BACKOFF", "0")
    # real (lazily-loaded) mistral/google are unconfigured -> stub serves
    orch = OcrOrchestrator()
    result = orch.run(b"bytes")
    assert result.provider == "stub"
    assert "Tomates" in result.text


def test_circuit_breaker_skips_provider_after_threshold(env, monkeypatch):
    # one failure trips the breaker; no retries so exactly one call per run
    monkeypatch.setenv("OCR_CB_FAIL_THRESHOLD", "1")
    monkeypatch.setenv("OCR_MAX_RETRIES", "0")
    mistral = FakeProvider("mistral", OcrTransientError("down"))
    google = FakeProvider("google", _ok("google"))
    orch = OcrOrchestrator(providers={"mistral": mistral, "google": google})

    orch.run(b"1")  # mistral fails once -> circuit opens
    assert mistral.calls == 1
    orch.run(b"2")  # mistral short-circuited -> not called again
    assert mistral.calls == 1
    assert google.calls == 2
