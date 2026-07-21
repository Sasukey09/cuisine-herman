"""OCR error hierarchy.

- OcrConfigurationError : provider not usable (missing key/SDK) -> skip, no retry.
- OcrTransientError     : recoverable failure (network/5xx/timeout) -> retry then fallback.
- OcrTimeoutError       : a single attempt exceeded the timeout budget.
- CircuitOpenError      : provider short-circuited by its breaker.
- AllProvidersFailedError: every provider in the chain failed -> surface to user.
"""


class OcrError(Exception):
    pass


class OcrConfigurationError(OcrError):
    pass


class OcrTransientError(OcrError):
    pass


class OcrTimeoutError(OcrTransientError):
    pass


class CircuitOpenError(OcrError):
    pass


class AllProvidersFailedError(OcrError):
    def __init__(self, failures):
        # failures: list of (provider_name, exception). When EVERY failure is a
        # configuration error (or there are no providers at all), this is a
        # service/outage problem; otherwise a provider actually ran and could not
        # read the document — i.e. the file is likely unreadable, not an outage.
        self.failures = failures

        # Outage = every provider was skipped/unusable and none actually
        # processed the document: not configured, circuit open, or a config
        # error. If ANY provider RAN and failed, the document itself (blurry/
        # blank photo) is the likely cause, not an outage.
        def _is_outage(reason) -> bool:
            return reason in ("not_configured", "circuit_open") or isinstance(
                reason, OcrConfigurationError
            )

        self.all_configuration_errors = all(_is_outage(r) for _, r in failures)
        detail = "; ".join(f"{name}: {r}" for name, r in failures) or "no providers"
        super().__init__(f"All OCR providers failed ({detail})")
