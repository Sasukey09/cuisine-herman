import time

import pytest

from app.services.ocr.resilience import CircuitBreaker, call_with_timeout, retry_call
from app.services.ocr.errors import OcrTimeoutError, OcrTransientError


# --- timeout ---------------------------------------------------------------

def test_call_with_timeout_returns_fast_result():
    assert call_with_timeout(lambda: 42, 1.0) == 42


def test_call_with_timeout_raises_on_slow():
    def slow():
        time.sleep(0.3)
        return "done"

    with pytest.raises(OcrTimeoutError):
        call_with_timeout(slow, 0.05)


# --- retry -----------------------------------------------------------------

def test_retry_succeeds_after_transient_failures():
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise OcrTransientError("temporary")
        return "ok"

    result = retry_call(flaky, max_retries=3, backoff=0)
    assert result == "ok"
    assert calls["n"] == 3


def test_retry_gives_up_after_max():
    calls = {"n": 0}

    def always_fail():
        calls["n"] += 1
        raise OcrTransientError("nope")

    with pytest.raises(OcrTransientError):
        retry_call(always_fail, max_retries=2, backoff=0)
    assert calls["n"] == 3  # initial + 2 retries


def test_retry_does_not_catch_other_exceptions():
    def boom():
        raise ValueError("not transient")

    with pytest.raises(ValueError):
        retry_call(boom, max_retries=3, backoff=0)


# --- circuit breaker -------------------------------------------------------

def test_circuit_opens_after_threshold_and_blocks():
    cb = CircuitBreaker("x", fail_threshold=2, reset_seconds=60)
    assert cb.allow() is True
    cb.record_failure()
    assert cb.state == "closed"
    cb.record_failure()
    assert cb.state == "open"
    assert cb.allow() is False


def test_circuit_half_opens_then_closes_on_success():
    cb = CircuitBreaker("x", fail_threshold=1, reset_seconds=0.05)
    cb.record_failure()
    assert cb.allow() is False
    time.sleep(0.06)
    assert cb.allow() is True  # half-open trial
    cb.record_success()
    assert cb.state == "closed"


def test_circuit_reopens_on_half_open_failure():
    cb = CircuitBreaker("x", fail_threshold=1, reset_seconds=0.05)
    cb.record_failure()
    time.sleep(0.06)
    assert cb.allow() is True
    cb.record_failure()
    assert cb.state == "open"
