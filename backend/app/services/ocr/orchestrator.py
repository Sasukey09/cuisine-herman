"""OCR orchestrator: provider chain with resilience.

Order (default): Mistral OCR -> Google Document AI -> error.

There is deliberately no silent fallback: when every provider fails the chain
raises ``AllProvidersFailedError`` and logs ``ocr.all_failed``. The canned stub
provider only joins the chain when ``OCR_ALLOW_STUB_FALLBACK=true`` is set
explicitly (local demos), because returning fake invoice lines would corrupt
prices, the purchase ledger and every recipe cost derived from them.
Each provider call is guarded by a circuit breaker, retried on transient errors,
and bounded by a timeout. Structured logs + Prometheus metrics are emitted.
"""
import logging
import time
from typing import Dict, List, Optional

from app.core.logging import get_logger, log_event
from app.core import metrics

from .config import OcrConfig, get_ocr_config
from .errors import (
    AllProvidersFailedError,
    OcrConfigurationError,
    OcrTimeoutError,
    OcrTransientError,
)
from .provider import OCRProvider
from .resilience import CircuitBreaker, call_with_timeout, retry_call
from .schemas import OcrResult

logger = get_logger("ocr.orchestrator")

_PROVIDER_FACTORIES = {
    "mistral": "app.services.ocr.providers.mistral:MistralOCRProvider",
    "google": "app.services.ocr.providers.google_docai:GoogleDocumentAIProvider",
    "stub": "app.services.ocr.providers.stub:StubOCRProvider",
}


def _load(path: str) -> OCRProvider:
    module_path, cls_name = path.split(":")
    import importlib

    module = importlib.import_module(module_path)
    return getattr(module, cls_name)()


class OcrOrchestrator:
    def __init__(self, providers: Optional[Dict[str, OCRProvider]] = None):
        # providers may be injected (tests); otherwise built lazily on demand.
        self._providers: Dict[str, OCRProvider] = providers or {}
        self._explicit = providers is not None
        self._breakers: Dict[str, CircuitBreaker] = {}

    def _provider(self, name: str) -> Optional[OCRProvider]:
        if name in self._providers:
            return self._providers[name]
        if self._explicit:
            return None
        factory = _PROVIDER_FACTORIES.get(name)
        if not factory:
            return None
        provider = _load(factory)
        self._providers[name] = provider
        return provider

    def _breaker(self, name: str, cfg: OcrConfig) -> CircuitBreaker:
        breaker = self._breakers.get(name)
        if breaker is None:
            breaker = CircuitBreaker(name, cfg.cb_fail_threshold, cfg.cb_reset_seconds)
            self._breakers[name] = breaker
        return breaker

    @staticmethod
    def _has_real_provider(cfg: OcrConfig) -> bool:
        return bool(cfg.mistral_api_key or (cfg.gcp_project and cfg.docai_processor_id))

    def _chain(self, cfg: OcrConfig) -> List[str]:
        """Build the provider chain. The stub is a *local demo* provider only.

        It is appended ONLY when no real provider is configured at all. Once a
        real one exists, a stub fallback can no longer mean "no OCR available" —
        it can only mean "OCR is down", and answering an outage with a canned
        invoice fabricates accounting data: the fake lines get priced, land in
        the purchase ledger and propagate into every recipe cost.

        This deliberately ignores ``allow_stub_fallback=true``: a single wrong
        environment variable must not be able to turn fabricated invoices back
        on in a properly configured deployment. (Exactly what happened — the
        Render blueprint pinned the flag to true, so the code default was moot.)
        """
        chain = list(cfg.chain)
        if "stub" in chain:
            return chain  # explicitly requested by name: the operator meant it

        if cfg.allow_stub_fallback and not self._has_real_provider(cfg):
            chain.append("stub")
        elif cfg.allow_stub_fallback:
            log_event(
                logger, logging.WARNING, "ocr.stub_fallback_ignored",
                reason="a real OCR provider is configured; refusing to fabricate an invoice",
            )
        return chain

    def run(self, file_bytes: bytes, content_type: Optional[str] = None) -> OcrResult:
        cfg = get_ocr_config()
        failures: List[tuple] = []

        for name in self._chain(cfg):
            provider = self._provider(name)
            if provider is None:
                continue
            if not provider.is_configured():
                log_event(logger, logging.INFO, "ocr.provider.skip", provider=name, reason="not_configured")
                failures.append((name, "not_configured"))
                continue

            breaker = self._breaker(name, cfg)
            if not breaker.allow():
                metrics.OCR_CIRCUIT_OPEN.labels(name).inc()
                metrics.OCR_FALLBACK.labels(name).inc()
                log_event(logger, logging.WARNING, "ocr.provider.circuit_open", provider=name)
                failures.append((name, "circuit_open"))
                continue

            metrics.OCR_REQUESTS.labels(name).inc()
            start = time.monotonic()
            try:
                result = retry_call(
                    lambda: call_with_timeout(
                        provider.extract_document, cfg.timeout_seconds, file_bytes, content_type
                    ),
                    max_retries=cfg.max_retries,
                    backoff=cfg.retry_backoff,
                    retry_on=(OcrTransientError,),
                    on_retry=lambda attempt, exc, sleep: log_event(
                        logger, logging.WARNING, "ocr.retry",
                        provider=name, attempt=attempt, error=str(exc), backoff_s=sleep,
                    ),
                )
            except OcrConfigurationError as exc:
                log_event(logger, logging.INFO, "ocr.provider.skip", provider=name, reason="config_error", error=str(exc))
                failures.append((name, exc))
                continue
            except Exception as exc:
                elapsed = time.monotonic() - start
                breaker.record_failure()
                metrics.OCR_FAILURE.labels(name).inc()
                metrics.OCR_DURATION.labels(name).observe(elapsed)
                metrics.OCR_FALLBACK.labels(name).inc()
                if isinstance(exc, OcrTimeoutError):
                    metrics.OCR_TIMEOUT.labels(name).inc()
                if breaker.state == "open":
                    metrics.OCR_CIRCUIT_OPEN.labels(name).inc()
                log_event(
                    logger, logging.ERROR, "ocr.provider.failure",
                    provider=name, elapsed_ms=round(elapsed * 1000), error=str(exc),
                    circuit=breaker.state,
                )
                failures.append((name, exc))
                continue

            elapsed = time.monotonic() - start
            breaker.record_success()
            metrics.OCR_SUCCESS.labels(name).inc()
            metrics.OCR_DURATION.labels(name).observe(elapsed)
            log_event(
                logger, logging.INFO, "ocr.provider.success",
                provider=name, elapsed_ms=round(elapsed * 1000),
                pages=result.pages, lines=len(result.lines), tables=len(result.tables),
            )
            return result

        log_event(logger, logging.ERROR, "ocr.all_failed", failures=failures)
        raise AllProvidersFailedError(failures)


_orchestrator: Optional[OcrOrchestrator] = None


def get_orchestrator() -> OcrOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = OcrOrchestrator()
    return _orchestrator


def run_ocr(file_bytes: bytes, content_type: Optional[str] = None) -> OcrResult:
    return get_orchestrator().run(file_bytes, content_type)
