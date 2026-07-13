"""Upload validation: never trust the filename or the declared Content-Type.

Both are chosen by the caller. `facture.pdf` with `Content-Type: application/pdf`
can carry anything at all — an HTML page, a shell script, a 200 MB zip. We sniff
the actual bytes and enforce a size ceiling before the payload reaches OCR (a
paid, remote service) or object storage.
"""
import os
from typing import Iterable, Optional


class UnsupportedUploadError(Exception):
    """The uploaded bytes are not something we accept."""


# Bytes that actually identify the format, regardless of what the caller claims.
_SIGNATURES = (
    ("pdf", (b"%PDF-",), None),
    ("png", (b"\x89PNG\r\n\x1a\n",), None),
    ("jpeg", (b"\xff\xd8\xff",), None),
    # WEBP is "RIFF" + 4 size bytes + "WEBP"
    ("webp", (b"RIFF",), (8, b"WEBP")),
)

_MIME_BY_KIND = {
    "pdf": "application/pdf",
    "png": "image/png",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
}

INVOICE_KINDS = ("pdf", "png", "jpeg", "webp")
RECIPE_KINDS = ("pdf", "png", "jpeg", "webp")


def _max_bytes(env_name: str, default_mb: int) -> int:
    try:
        return int(os.getenv(env_name, str(default_mb))) * 1024 * 1024
    except ValueError:
        return default_mb * 1024 * 1024


def sniff_kind(content: bytes) -> Optional[str]:
    """Detect the format from the leading bytes. None when unrecognised."""
    for kind, prefixes, offset_check in _SIGNATURES:
        if not any(content.startswith(p) for p in prefixes):
            continue
        if offset_check:
            offset, marker = offset_check
            if content[offset:offset + len(marker)] != marker:
                continue
        return kind
    return None


def validate_upload(
    content: bytes,
    content_type: Optional[str],
    *,
    allowed: Iterable[str] = INVOICE_KINDS,
    max_mb_env: str = "MAX_UPLOAD_MB",
    default_max_mb: int = 20,
) -> str:
    """Validate an uploaded document and return its real kind.

    Raises :class:`UnsupportedUploadError` on an empty file, an oversized one,
    an unrecognised format, or a Content-Type that contradicts the bytes.
    """
    if not content:
        raise UnsupportedUploadError("Fichier vide.")

    limit = _max_bytes(max_mb_env, default_max_mb)
    if len(content) > limit:
        raise UnsupportedUploadError(
            f"Fichier trop volumineux ({len(content) // (1024 * 1024)} Mo). "
            f"Maximum : {limit // (1024 * 1024)} Mo."
        )

    kind = sniff_kind(content)
    if kind is None or kind not in allowed:
        raise UnsupportedUploadError(
            "Format non supporté. Envoyez un PDF ou une photo (JPEG, PNG, WEBP)."
        )

    # A declared type that contradicts the bytes is a spoofing attempt (or a
    # broken client): refuse rather than let the wrong parser run on it.
    declared = (content_type or "").split(";")[0].strip().lower()
    if declared and declared not in ("application/octet-stream", _MIME_BY_KIND[kind]):
        raise UnsupportedUploadError(
            f"Le type déclaré ({declared}) ne correspond pas au contenu réel ({kind})."
        )

    return kind
