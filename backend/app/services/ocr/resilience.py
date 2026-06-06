"""Resilience primitives: timeout, retry with exponential backoff, circuit breaker."""
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from typing import Callable, Iterable, Optional, Tuple, Type

from .errors import OcrTimeoutError, OcrTransientError

# Bounded pool so a slow provider can't exhaust resources.
_executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="ocr")


def call_with_timeout(fn: Callable, timeout: float, *args, **kwargs):
    """Run ``fn`` in a worker thread and abort (from the caller's view) after
    ``timeout`` seconds. Raises OcrTimeoutError on timeout."""
    future = _executor.submit(fn, *args, **kwargs)
    try:
        return future.result(timeout=timeout)
    except FuturesTimeout:
        raise OcrTimeoutError(f"operation exceeded {timeout}s timeout")


def retry_call(
    fn: Callable,
    max_retries: int = 2,
    backoff: float = 0.5,
    retry_on: Tuple[Type[BaseException], ...] = (OcrTransientError,),
    on_retry: Optional[Callable[[int, BaseException, float], None]] = None,
):
    """Call ``fn`` retrying on ``retry_on`` exceptions with exponential backoff."""
    attempt = 0
    while True:
        try:
            return fn()
        except retry_on as exc:
            attempt += 1
            if attempt > max_retries:
                raise
            sleep = backoff * (2 ** (attempt - 1))
            if on_retry:
                on_retry(attempt, exc, sleep)
            if sleep > 0:
                time.sleep(sleep)


class CircuitBreaker:
    """Per-provider circuit breaker.

    closed  -> calls allowed; opens after ``fail_threshold`` consecutive failures.
    open    -> calls blocked until ``reset_seconds`` elapse, then half-open.
    half-open -> one trial call; success closes, failure re-opens.
    """

    def __init__(self, name: str, fail_threshold: int = 3, reset_seconds: float = 30.0):
        self.name = name
        self.fail_threshold = fail_threshold
        self.reset_seconds = reset_seconds
        self._failures = 0
        self._state = "closed"
        self._opened_at = 0.0
        self._lock = threading.Lock()

    @property
    def state(self) -> str:
        return self._state

    def allow(self) -> bool:
        with self._lock:
            if self._state == "open":
                if time.monotonic() - self._opened_at >= self.reset_seconds:
                    self._state = "half_open"
                    return True
                return False
            return True

    def record_success(self) -> None:
        with self._lock:
            self._failures = 0
            self._state = "closed"

    def record_failure(self) -> None:
        with self._lock:
            self._failures += 1
            if self._state == "half_open" or self._failures >= self.fail_threshold:
                self._state = "open"
                self._opened_at = time.monotonic()
