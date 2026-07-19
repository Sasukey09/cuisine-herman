import os
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Local/dev/test default only. In production an unset DATABASE_URL must fail
# loudly rather than silently connect to a localhost DB with default creds.
_DEV_FALLBACK = "postgresql+psycopg2://postgres:password@localhost:5432/cuisine"
_UNDER_PYTEST = "PYTEST_CURRENT_TEST" in os.environ or "pytest" in sys.modules


def _resolve_database_url(url: str, app_env: str, under_pytest: bool) -> str:
    if url:
        return url
    if under_pytest or app_env != "production":
        return _DEV_FALLBACK
    raise RuntimeError(
        "DATABASE_URL is required in production but is unset — refusing to start "
        "rather than connect to an unintended default database. Set DATABASE_URL "
        "in the environment (Render provisions it automatically)."
    )


DATABASE_URL = _resolve_database_url(
    os.getenv("DATABASE_URL", ""), os.getenv("APP_ENV", "production"), _UNDER_PYTEST
)


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


# Connection budget: (pool_size + max_overflow) x WEB_CONCURRENCY, plus the
# Celery worker's own pool. Keep the total under the database's limit (Render's
# smaller plans allow around 100 connections).
engine = create_engine(
    DATABASE_URL,
    future=True,
    # A managed Postgres — and any proxy in front of it — closes idle
    # connections. Without pre_ping the pool hands out a dead socket, and the
    # FIRST request after a quiet period fails with "server closed the
    # connection unexpectedly". On a free plan that spins down, that is every
    # morning. One cheap SELECT 1 per checkout avoids it.
    pool_pre_ping=True,
    # Recycle before the server or a load balancer decides to hang up on us.
    pool_recycle=_int("DB_POOL_RECYCLE_SECONDS", 1800),
    pool_size=_int("DB_POOL_SIZE", 5),
    max_overflow=_int("DB_MAX_OVERFLOW", 10),
    # Fail fast instead of queueing: waiting 30s for a connection only turns a
    # saturated pool into a timed-out client.
    pool_timeout=_int("DB_POOL_TIMEOUT_SECONDS", 10),
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
