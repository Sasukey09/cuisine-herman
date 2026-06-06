"""S3 / MinIO object storage for invoice files.

Degrades gracefully: if S3 is not configured (no S3_ENDPOINT/S3_BUCKET), uploads
return ``None`` and the pipeline keeps working without persisting the file.

Presigned download URLs are generated against ``S3_PUBLIC_ENDPOINT`` (the address
the browser can reach, e.g. http://localhost:9000) — distinct from the internal
``S3_ENDPOINT`` (e.g. http://minio:9000) used server-side.
"""
import logging
import os
from typing import Optional

from app.core.logging import get_logger, log_event

logger = get_logger("storage.s3")

_bucket_ready = False


def is_enabled() -> bool:
    return bool(os.getenv("S3_ENDPOINT") and os.getenv("S3_BUCKET"))


def _bucket() -> str:
    return os.getenv("S3_BUCKET", "")


def _client(endpoint: Optional[str] = None):
    import boto3
    from botocore.config import Config

    return boto3.client(
        "s3",
        endpoint_url=endpoint or os.getenv("S3_ENDPOINT"),
        aws_access_key_id=os.getenv("MINIO_ACCESS_KEY") or os.getenv("S3_ACCESS_KEY"),
        aws_secret_access_key=os.getenv("MINIO_SECRET_KEY") or os.getenv("S3_SECRET_KEY"),
        region_name=os.getenv("S3_REGION", "us-east-1"),
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            connect_timeout=5,
            read_timeout=15,
            retries={"max_attempts": 2},
        ),
    )


def ensure_bucket() -> None:
    global _bucket_ready
    if _bucket_ready or not is_enabled():
        return
    from botocore.exceptions import ClientError

    client = _client()
    try:
        client.head_bucket(Bucket=_bucket())
    except ClientError:
        try:
            client.create_bucket(Bucket=_bucket())
            log_event(logger, logging.INFO, "storage.bucket.created", bucket=_bucket())
        except ClientError as exc:  # pragma: no cover
            log_event(logger, logging.ERROR, "storage.bucket.error", error=str(exc))
            return
    _bucket_ready = True


def upload_invoice(
    tenant_id: str,
    invoice_id: str,
    filename: Optional[str],
    content: bytes,
    content_type: Optional[str] = None,
) -> Optional[str]:
    """Store the invoice file and return its object key (or None if disabled)."""
    if not is_enabled():
        return None
    from botocore.exceptions import ClientError

    ensure_bucket()
    safe_name = (filename or "invoice").replace("/", "_").replace("\\", "_")
    key = f"invoices/{tenant_id}/{invoice_id}/{safe_name}"
    try:
        _client().put_object(
            Bucket=_bucket(),
            Key=key,
            Body=content,
            ContentType=content_type or "application/octet-stream",
        )
        log_event(logger, logging.INFO, "storage.upload", key=key, size=len(content))
        return key
    except ClientError as exc:  # pragma: no cover
        # non-blocking: log and continue without a stored file
        log_event(logger, logging.ERROR, "storage.upload.error", key=key, error=str(exc))
        return None


def download_invoice(key: Optional[str]) -> Optional[bytes]:
    """Fetch the stored invoice file bytes by key (used by the async OCR worker)."""
    if not is_enabled() or not key:
        return None
    from botocore.exceptions import ClientError

    try:
        obj = _client().get_object(Bucket=_bucket(), Key=key)
        return obj["Body"].read()
    except ClientError as exc:  # pragma: no cover
        log_event(logger, logging.ERROR, "storage.download.error", key=key, error=str(exc))
        return None


def presigned_url(key: Optional[str], expires: int = 3600) -> Optional[str]:
    """Return a time-limited download URL reachable from the browser."""
    if not is_enabled() or not key:
        return None
    public = os.getenv("S3_PUBLIC_ENDPOINT") or os.getenv("S3_ENDPOINT")
    try:
        return _client(endpoint=public).generate_presigned_url(
            "get_object", Params={"Bucket": _bucket(), "Key": key}, ExpiresIn=expires
        )
    except Exception as exc:  # pragma: no cover
        log_event(logger, logging.ERROR, "storage.presign.error", key=key, error=str(exc))
        return None
