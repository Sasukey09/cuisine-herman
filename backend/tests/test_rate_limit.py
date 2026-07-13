"""Brute-force protection on the login endpoint."""
import pytest

from app.core import rate_limit
from app.core.rate_limit import (
    FREE_ATTEMPTS,
    IP_FREE_ATTEMPTS,
    MAX_LOCK_SECONDS,
    LoginGuard,
    _MemoryStore,
    lock_seconds,
)


@pytest.fixture
def guard():
    return LoginGuard(_MemoryStore())


# --- backoff curve ----------------------------------------------------------

def test_free_attempts_are_not_locked():
    for failures in range(1, FREE_ATTEMPTS + 1):
        assert lock_seconds(failures, FREE_ATTEMPTS) == 0


def test_backoff_doubles_then_caps():
    base = rate_limit.BASE_LOCK_SECONDS
    assert lock_seconds(FREE_ATTEMPTS + 1, FREE_ATTEMPTS) == base
    assert lock_seconds(FREE_ATTEMPTS + 2, FREE_ATTEMPTS) == base * 2
    assert lock_seconds(FREE_ATTEMPTS + 3, FREE_ATTEMPTS) == base * 4
    # never grows without bound
    assert lock_seconds(FREE_ATTEMPTS + 50, FREE_ATTEMPTS) == MAX_LOCK_SECONDS


# --- per-account guard ------------------------------------------------------

def test_account_is_locked_after_the_free_attempts(guard):
    email, ip = "chef@herman.fr", "1.2.3.4"
    assert guard.retry_after(email, ip) == 0

    for _ in range(FREE_ATTEMPTS):
        guard.record_failure(email, ip)
    assert guard.retry_after(email, ip) == 0, "free attempts must not lock"

    applied = guard.record_failure(email, ip)
    assert applied > 0
    assert guard.retry_after(email, ip) > 0, "the account must now be locked"


def test_lock_is_scoped_to_the_attacked_account(guard):
    ip = "1.2.3.4"
    for _ in range(FREE_ATTEMPTS + 1):
        guard.record_failure("victim@herman.fr", ip)

    assert guard.retry_after("victim@herman.fr", None) > 0
    assert guard.retry_after("someone-else@herman.fr", None) == 0


def test_email_case_and_padding_do_not_bypass_the_lock(guard):
    for _ in range(FREE_ATTEMPTS + 1):
        guard.record_failure("chef@herman.fr", None)
    assert guard.retry_after("  CHEF@Herman.FR ", None) > 0


def test_successful_login_clears_the_account_counter(guard):
    email, ip = "chef@herman.fr", "1.2.3.4"
    for _ in range(FREE_ATTEMPTS):
        guard.record_failure(email, ip)
    guard.record_success(email, ip)

    # The counter restarted: the next failures are free again.
    for _ in range(FREE_ATTEMPTS):
        guard.record_failure(email, ip)
    assert guard.retry_after(email, ip) == 0


# --- per-IP guard (credential stuffing) -------------------------------------

def test_ip_is_locked_after_many_failures_across_accounts(guard):
    ip = "9.9.9.9"
    for i in range(IP_FREE_ATTEMPTS + 1):
        guard.record_failure(f"user{i}@herman.fr", ip)

    # A brand-new account from that IP is refused too.
    assert guard.retry_after("fresh@herman.fr", ip) > 0
    # …but the same account from elsewhere is fine.
    assert guard.retry_after("fresh@herman.fr", "5.5.5.5") == 0


def test_success_does_not_reset_the_ip_budget(guard):
    """Otherwise an attacker with one valid account resets their IP budget."""
    ip = "9.9.9.9"
    for i in range(IP_FREE_ATTEMPTS + 1):
        guard.record_failure(f"user{i}@herman.fr", ip)
    guard.record_success("attacker-own-account@herman.fr", ip)

    assert guard.retry_after("fresh@herman.fr", ip) > 0


# --- availability -----------------------------------------------------------

def test_guard_fails_open_when_the_store_is_broken():
    """A Redis outage must not lock every restaurateur out of their account."""

    class BrokenStore:
        def incr(self, *a, **k):
            raise ConnectionError("redis down")

        def lock(self, *a, **k):
            raise ConnectionError("redis down")

        def locked_for(self, *a, **k):
            raise ConnectionError("redis down")

        def clear(self, *a, **k):
            raise ConnectionError("redis down")

    broken = LoginGuard(BrokenStore())
    assert broken.retry_after("chef@herman.fr", "1.2.3.4") == 0
    assert broken.record_failure("chef@herman.fr", "1.2.3.4") == 0
    broken.record_success("chef@herman.fr", "1.2.3.4")  # must not raise
