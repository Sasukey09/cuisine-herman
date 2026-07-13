"""Brute-force protection for the login endpoint.

Two independent counters guard ``POST /auth/token``:

* **per account** (the submitted email) — the real barrier, since an attacker
  cannot spoof which account they are attacking;
* **per client IP** — best effort against credential stuffing spread across many
  accounts. ``X-Forwarded-For`` is caller-controllable unless we sit behind a
  trusted proxy, so this counter only ever *adds* protection; it never replaces
  the account one.

Counters live in Redis when it is reachable, so a lockout holds across Gunicorn
workers and container restarts. Otherwise they fall back to an in-process store,
which is enough for local dev and tests.

If Redis is configured but *errors*, we fail **open** and log it: locking every
restaurateur out of their own account because of a cache blip is a worse outage
than the attack we are mitigating.
"""
import logging
import os
import threading
import time
from typing import Iterable, List, Optional, Tuple

from app.core.logging import get_logger, log_event

logger = get_logger(__name__)

# Attempts that cost nothing, per account and per IP.
FREE_ATTEMPTS = int(os.getenv("LOGIN_FREE_ATTEMPTS", "4"))
IP_FREE_ATTEMPTS = int(os.getenv("LOGIN_IP_FREE_ATTEMPTS", "20"))
# Backoff shape.
BASE_LOCK_SECONDS = int(os.getenv("LOGIN_BASE_LOCK_SECONDS", "30"))
MAX_LOCK_SECONDS = int(os.getenv("LOGIN_MAX_LOCK_SECONDS", "900"))
# How long a failure is remembered when no further failure occurs.
WINDOW_SECONDS = int(os.getenv("LOGIN_FAILURE_WINDOW_SECONDS", "900"))


def lock_seconds(failures: int, free_attempts: int) -> int:
    """Seconds to lock out after ``failures`` bad passwords.

    Doubles with each failure past the free allowance, capped:
    with the defaults, attempts 1-4 are free, then 30s, 1min, 2min, 4min, 8min,
    then 15min for every further attempt.
    """
    over = failures - free_attempts
    if over <= 0:
        return 0
    return min(BASE_LOCK_SECONDS * (2 ** (over - 1)), MAX_LOCK_SECONDS)


class _MemoryStore:
    """Process-local fallback. Good enough for dev/tests, not for many workers."""

    def __init__(self) -> None:
        self._counts: dict = {}
        self._locks: dict = {}
        self._mutex = threading.Lock()

    def _purge(self, now: float) -> None:
        for key, (_, expires) in list(self._counts.items()):
            if expires <= now:
                self._counts.pop(key, None)
        for key, expires in list(self._locks.items()):
            if expires <= now:
                self._locks.pop(key, None)

    def incr(self, key: str, ttl: int) -> int:
        now = time.monotonic()
        with self._mutex:
            self._purge(now)
            count, expires = self._counts.get(key, (0, 0.0))
            count += 1
            # Keep the original expiry: a fixed window, not a sliding one that
            # a caller could keep pushing forward.
            self._counts[key] = (count, expires if count > 1 else now + ttl)
            return count

    def ttl(self, key: str) -> int:
        now = time.monotonic()
        with self._mutex:
            _, expires = self._counts.get(key, (0, 0.0))
            return max(0, int(expires - now)) + 1 if expires > now else 0

    def lock(self, key: str, seconds: int) -> None:
        with self._mutex:
            self._locks[key] = time.monotonic() + seconds

    def locked_for(self, key: str) -> int:
        now = time.monotonic()
        with self._mutex:
            expires = self._locks.get(key)
            if expires is None or expires <= now:
                return 0
            return int(expires - now) + 1

    def clear(self, keys: Iterable[str]) -> None:
        with self._mutex:
            for key in keys:
                self._counts.pop(key, None)
                self._locks.pop(key, None)


class _RedisStore:
    """Shared across workers and restarts."""

    def __init__(self, client) -> None:
        self._r = client

    def incr(self, key: str, ttl: int) -> int:
        pipe = self._r.pipeline()
        pipe.incr(key)
        # nx=True: only set the TTL on the first hit, so the window is fixed and
        # a caller cannot keep pushing it forward with every request.
        pipe.expire(key, ttl, nx=True)
        count, _ = pipe.execute()
        return int(count)

    def ttl(self, key: str) -> int:
        value = self._r.ttl(key)
        return int(value) if value and value > 0 else 0

    def lock(self, key: str, seconds: int) -> None:
        self._r.setex(key, seconds, b"1")

    def locked_for(self, key: str) -> int:
        ttl = self._r.ttl(key)
        return int(ttl) if ttl and ttl > 0 else 0

    def clear(self, keys: Iterable[str]) -> None:
        keys = list(keys)
        if keys:
            self._r.delete(*keys)


class LoginGuard:
    """Decides whether a login attempt is allowed, and records its outcome."""

    def __init__(self, store) -> None:
        self._store = store

    # --- keys ---------------------------------------------------------------
    @staticmethod
    def _scopes(email: str, ip: Optional[str]) -> List[Tuple[str, int]]:
        scopes = [(f"login:acct:{(email or '').strip().lower()}", FREE_ATTEMPTS)]
        if ip:
            scopes.append((f"login:ip:{ip}", IP_FREE_ATTEMPTS))
        return scopes

    # --- API ----------------------------------------------------------------
    def retry_after(self, email: str, ip: Optional[str]) -> int:
        """Seconds the caller must wait. 0 means the attempt may proceed."""
        try:
            waits = [self._store.locked_for(f"{key}:lock") for key, _ in self._scopes(email, ip)]
        except Exception as exc:  # Redis down → do not lock legitimate users out
            log_event(logger, logging.WARNING, "login.guard.unavailable", error=str(exc))
            return 0
        return max(waits) if waits else 0

    def record_failure(self, email: str, ip: Optional[str]) -> int:
        """Count a bad password. Returns the lockout applied, in seconds."""
        applied = 0
        try:
            for key, free in self._scopes(email, ip):
                failures = self._store.incr(f"{key}:fail", WINDOW_SECONDS)
                seconds = lock_seconds(failures, free)
                if seconds:
                    self._store.lock(f"{key}:lock", seconds)
                    applied = max(applied, seconds)
            if applied:
                log_event(
                    logger, logging.WARNING, "login.locked",
                    email=(email or "").strip().lower(), ip=ip, lock_seconds=applied,
                )
        except Exception as exc:
            log_event(logger, logging.WARNING, "login.guard.unavailable", error=str(exc))
        return applied

    def record_success(self, email: str, ip: Optional[str]) -> None:
        """Clear the *account* counters.

        The IP counter is deliberately left alone: otherwise an attacker holding
        one valid account could reset their IP budget between every burst.
        """
        try:
            key = self._scopes(email, None)[0][0]
            self._store.clear([f"{key}:fail", f"{key}:lock"])
        except Exception as exc:
            log_event(logger, logging.WARNING, "login.guard.unavailable", error=str(exc))


class QuotaGuard:
    """Fixed-window quota for the endpoints that cost real money or CPU.

    ``/ai/chat`` bills Anthropic on every call, OCR bills Mistral, and
    ``/products/match`` runs a fuzzy score against the whole catalogue. Without
    a ceiling, one scripted account can drain the budget or pin a worker — and
    Gunicorn workers are shared, so the blast radius is every tenant.
    """

    def __init__(self, store) -> None:
        self._store = store

    def check(self, key: str, limit: int, window_seconds: int) -> int:
        """Count this call. Returns seconds to wait, 0 when it may proceed."""
        try:
            full_key = f"quota:{key}"
            count = self._store.incr(full_key, window_seconds)
            if count > limit:
                return self._store.ttl(full_key) or window_seconds
        except Exception as exc:  # a cache outage must not take the app down
            log_event(logger, logging.WARNING, "quota.unavailable", error=str(exc))
        return 0


_quota: Optional[QuotaGuard] = None


def get_quota_guard() -> QuotaGuard:
    global _quota
    if _quota is None:
        _quota = QuotaGuard(_build_store())
    return _quota


def reset_quota_guard() -> None:
    """Test hook."""
    global _quota
    _quota = None


def _build_store():
    url = os.getenv("REDIS_URL") or os.getenv("CELERY_BROKER_URL")
    if url:
        try:
            import redis  # type: ignore

            client = redis.from_url(url, socket_connect_timeout=1, socket_timeout=1)
            client.ping()
            log_event(logger, logging.INFO, "login.guard.backend", backend="redis")
            return _RedisStore(client)
        except Exception as exc:
            log_event(
                logger, logging.WARNING, "login.guard.backend",
                backend="memory", reason=f"redis unavailable: {exc}",
            )
    return _MemoryStore()


_guard: Optional[LoginGuard] = None


def get_login_guard() -> LoginGuard:
    global _guard
    if _guard is None:
        _guard = LoginGuard(_build_store())
    return _guard


def reset_login_guard() -> None:
    """Test hook: drop the cached guard so the next call rebuilds it."""
    global _guard
    _guard = None


def client_ip(request) -> Optional[str]:
    """Best-effort client IP behind Render/Vercel's proxy."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip() or None
    return request.client.host if request.client else None
