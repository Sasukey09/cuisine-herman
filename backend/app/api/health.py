"""Health & readiness endpoints.

- GET /live   : process is up (no dependency checks) — for liveness probes.
- GET /health : lightweight OK — for simple uptime checks / load balancers.
- GET /ready  : checks PostgreSQL, Redis, S3/MinIO and OCR providers — for
                readiness probes. Returns 503 if a *critical* dependency is down.
"""
import os
from typing import Optional, Tuple

from fastapi import APIRouter, Response
from sqlalchemy import text

from app.db.session import engine
from app.core import metrics
from app.core.logging import get_logger
from app.services.ocr.config import get_ocr_config

logger = get_logger(__name__)

router = APIRouter(tags=["health"])

# (ok, detail): ok True=up, False=down, None=skipped (not configured)
CheckResult = Tuple[Optional[bool], Optional[object]]


def _safe_detail(exc: Exception) -> str:
    """`/ready` is public. A raw exception on it hands out the connection string,
    the database host and the driver stack trace to anyone who asks. The full
    error goes to the logs, where it belongs; the probe answers with the class
    name, which is enough to tell postgres-down from redis-down."""
    logger.warning("readiness check failed: %s", exc, exc_info=True)
    return type(exc).__name__


def check_postgres() -> CheckResult:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, None
    except Exception as exc:  # pragma: no cover - needs a live DB
        return False, _safe_detail(exc)


def check_redis() -> CheckResult:
    url = os.getenv("CELERY_BROKER_URL") or os.getenv("REDIS_URL")
    if not url:
        return None, "not configured"
    try:
        import redis

        client = redis.from_url(url, socket_connect_timeout=2, socket_timeout=2)
        client.ping()
        return True, None
    except Exception as exc:  # pragma: no cover
        return False, _safe_detail(exc)


def check_s3() -> CheckResult:
    endpoint = os.getenv("S3_ENDPOINT")
    if not endpoint:
        return None, "not configured"
    try:
        import boto3
        from botocore.config import Config

        client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=os.getenv("MINIO_ACCESS_KEY"),
            aws_secret_access_key=os.getenv("MINIO_SECRET_KEY"),
            config=Config(connect_timeout=2, read_timeout=2, retries={"max_attempts": 1}),
        )
        client.list_buckets()
        return True, None
    except Exception as exc:  # pragma: no cover
        return False, _safe_detail(exc)


def check_ocr() -> CheckResult:
    cfg = get_ocr_config()
    try:
        from app.services.ocr.orchestrator import get_orchestrator

        orch = get_orchestrator()
        configured = [
            name
            for name in cfg.chain
            if (p := orch._provider(name)) is not None and p.is_configured()
        ]
    except Exception as exc:  # pragma: no cover
        return False, _safe_detail(exc)
    if configured:
        return True, {"configured": configured}
    if cfg.allow_stub_fallback:
        return True, {"stub_fallback": True}
    return False, "no OCR provider configured"


@router.get("/live")
def live():
    return {"status": "alive"}


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/ready")
def ready(response: Response):
    # Built at call time (not import) so the check functions can be monkeypatched.
    # name -> (check fn, critical for readiness)
    checks_spec = [
        ("postgres", check_postgres, True),
        ("redis", check_redis, True),
        ("s3", check_s3, False),
        ("ocr", check_ocr, False),
    ]
    checks = {}
    ready_ok = True
    for name, fn, critical in checks_spec:
        ok, detail = fn()
        if ok is None:
            status = "skipped"
        elif ok:
            status = "up"
        else:
            status = "down"
        checks[name] = {"status": status, "detail": detail}
        if ok is not None:
            metrics.DEPENDENCY_UP.labels(name).set(1 if ok else 0)
        if critical and ok is False:
            ready_ok = False
    response.status_code = 200 if ready_ok else 503
    return {"status": "ready" if ready_ok else "not_ready", "checks": checks}
