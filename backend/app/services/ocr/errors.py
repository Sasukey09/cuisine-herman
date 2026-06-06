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
        self.failures = failures
        detail = "; ".join(f"{name}: {reason}" for name, reason in failures) or "no providers"
        super().__init__(f"All OCR providers failed ({detail})")
