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
    email, ip = "chef@foodgad.fr", "1.2.3.4"
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
        guard.record_failure("victim@foodgad.fr", ip)

    assert guard.retry_after("victim@foodgad.fr", None) > 0
    assert guard.retry_after("someone-else@foodgad.fr", None) == 0


def test_email_case_and_padding_do_not_bypass_the_lock(guard):
    for _ in range(FREE_ATTEMPTS + 1):
        guard.record_failure("chef@foodgad.fr", None)
    assert guard.retry_after("  CHEF@Foodgad.FR ", None) > 0


def test_successful_login_clears_the_account_counter(guard):
    email, ip = "chef@foodgad.fr", "1.2.3.4"
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
        guard.record_failure(f"user{i}@foodgad.fr", ip)

    # A brand-new account from that IP is refused too.
    assert guard.retry_after("fresh@foodgad.fr", ip) > 0
    # …but the same account from elsewhere is fine.
    assert guard.retry_after("fresh@foodgad.fr", "5.5.5.5") == 0


def test_success_does_not_reset_the_ip_budget(guard):
    """Otherwise an attacker with one valid account resets their IP budget."""
    ip = "9.9.9.9"
    for i in range(IP_FREE_ATTEMPTS + 1):
        guard.record_failure(f"user{i}@foodgad.fr", ip)
    guard.record_success("attacker-own-account@foodgad.fr", ip)

    assert guard.retry_after("fresh@foodgad.fr", ip) > 0


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
    assert broken.retry_after("chef@foodgad.fr", "1.2.3.4") == 0
    assert broken.record_failure("chef@foodgad.fr", "1.2.3.4") == 0
    broken.record_success("chef@foodgad.fr", "1.2.3.4")  # must not raise


# --- client IP resolution behind a proxy (anti-spoofing, F1) ----------------

class _Peer:
    def __init__(self, host):
        self.host = host


class _Req:
    """Minimal stand-in for a Starlette Request for client_ip()."""

    def __init__(self, xff=None, peer="10.0.0.9", headers=None):
        h = dict(headers or {})
        if xff is not None:
            h["x-forwarded-for"] = xff
        self.headers = h
        self.client = _Peer(peer)


def test_cf_connecting_ip_is_trusted_over_the_forwarded_chain():
    # Real Cloudflare->Render shape: the real client (37.65.9.209) is NOT the
    # right-most public entry (Cloudflare's 172.71.x is), so we must trust the
    # CF-Connecting-IP header Cloudflare sets.
    req = _Req(
        xff="8.8.8.8, 37.65.9.209, 172.71.151.232, 10.26.130.4",
        headers={"cf-connecting-ip": "37.65.9.209"},
    )
    assert rate_limit.client_ip(req) == "37.65.9.209"


def test_rotating_cloudflare_edge_ip_does_not_change_the_key():
    # Same client, Cloudflare's edge IP rotates per request: the key must stay
    # pinned to CF-Connecting-IP, not the rotating 172.71.x / 141.101.x hop.
    a = _Req(xff="37.65.9.209, 172.71.1.1, 10.0.0.5",
             headers={"cf-connecting-ip": "37.65.9.209"})
    b = _Req(xff="37.65.9.209, 141.101.69.30, 10.0.0.9",
             headers={"cf-connecting-ip": "37.65.9.209"})
    assert rate_limit.client_ip(a) == rate_limit.client_ip(b) == "37.65.9.209"


def test_client_ip_skips_renders_private_trailing_hops():
    """Render appends its own private (10.x/192.168.x) hop on the right; the
    real client is the right-most PUBLIC address, not that shared edge IP."""
    req = _Req(xff="70.1.2.3, 10.28.252.3")  # [real client, Render edge]
    assert rate_limit.client_ip(req) == "70.1.2.3"


def test_client_ip_ignores_a_forged_public_ip_to_the_left():
    """A caller-forged public IP is always LEFT of the real client (which Render
    appends), so the right-most-public scan must ignore the forgery."""
    req = _Req(xff="8.8.8.8, 70.1.2.3, 10.0.0.5")  # [forged, real, private edge]
    assert rate_limit.client_ip(req) == "70.1.2.3"


def test_rotating_the_forwarded_header_does_not_change_the_rate_limit_key():
    """The proven bypass: a caller rotating X-Forwarded-For must resolve to the
    SAME key, so the per-IP counter still bites."""
    a = _Req(xff="1.1.1.1, 70.1.2.3, 10.0.0.5")
    b = _Req(xff="2.2.2.2, 70.1.2.3, 10.0.0.5")
    assert rate_limit.client_ip(a) == rate_limit.client_ip(b) == "70.1.2.3"


def test_client_ip_supports_ipv6_clients():
    req = _Req(xff="2a02:8429:8841:5a01::1, 10.28.252.3")
    assert rate_limit.client_ip(req) == "2a02:8429:8841:5a01::1"


def test_client_ip_falls_back_to_the_peer_without_a_forwarded_header():
    assert rate_limit.client_ip(_Req(xff=None, peer="42.42.42.42")) == "42.42.42.42"


def test_client_ip_falls_back_to_the_peer_when_the_chain_is_all_private():
    # No public IP anywhere (local dev / fully-private network): use the socket.
    req = _Req(xff="10.0.0.5, 192.168.1.1", peer="203.0.113.9")
    assert rate_limit.client_ip(req) == "203.0.113.9"


def test_a_single_public_entry_is_returned():
    assert rate_limit.client_ip(_Req(xff="70.1.2.3")) == "70.1.2.3"
