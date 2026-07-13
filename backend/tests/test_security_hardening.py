"""Phase 2 — OWASP hardening: SSRF guard, upload validation, per-tenant quotas."""
import pytest

from app.core.rate_limit import QuotaGuard, _MemoryStore
from app.core.uploads import UnsupportedUploadError, sniff_kind, validate_upload
from app.core.url_guard import UnsafeURLError, assert_safe_fetch_url


# --------------------------------------------------------------------------- #
# SSRF — the video importer hands this URL to yt-dlp
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ",
        "https://www.instagram.com/reel/xyz/",
        "https://vimeo.com/123456",
    ],
)
def test_supported_platforms_are_allowed(url):
    assert_safe_fetch_url(url)  # must not raise


@pytest.mark.parametrize(
    "url",
    [
        "http://169.254.169.254/latest/meta-data/",  # cloud credentials
        "http://127.0.0.1:8000/api/v1/auth/users",  # the app talking to itself
        "http://localhost/admin",
        "http://10.0.0.5/",  # private network
        "http://192.168.1.1/",
        "http://[::1]/",
    ],
)
def test_internal_addresses_are_refused(url):
    """The whole point: the server must never fetch its own network."""
    with pytest.raises(UnsafeURLError):
        assert_safe_fetch_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "gopher://evil.test/",
        "ftp://evil.test/x",
        "https://user:pass@www.youtube.com/watch?v=x",  # credentials in URL
        "https://evil.test/video.mp4",  # not a supported platform
        "",
    ],
)
def test_other_dangerous_shapes_are_refused(url):
    with pytest.raises(UnsafeURLError):
        assert_safe_fetch_url(url)


def test_a_lookalike_host_does_not_slip_through():
    """`youtube.com.evil.test` must not match the allowlist."""
    with pytest.raises(UnsafeURLError):
        assert_safe_fetch_url("https://youtube.com.evil.test/watch?v=x")


def test_the_allowlist_can_be_opened_but_private_ips_still_cannot(monkeypatch):
    monkeypatch.setenv("VIDEO_ALLOW_ANY_HOST", "true")
    # A private address stays refused even with the allowlist off.
    with pytest.raises(UnsafeURLError):
        assert_safe_fetch_url("http://169.254.169.254/latest/meta-data/")


# --------------------------------------------------------------------------- #
# Uploads — neither the filename nor the declared Content-Type is trustworthy
# --------------------------------------------------------------------------- #
PDF = b"%PDF-1.4\n..."
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 16
WEBP = b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"\x00" * 8


def test_real_documents_are_accepted():
    assert validate_upload(PDF, "application/pdf") == "pdf"
    assert validate_upload(PNG, "image/png") == "png"
    assert validate_upload(JPEG, "image/jpeg") == "jpeg"
    assert validate_upload(WEBP, "image/webp") == "webp"


def test_content_type_alone_never_decides():
    """A shell script announced as a PDF is still a shell script."""
    with pytest.raises(UnsupportedUploadError):
        validate_upload(b"#!/bin/sh\nrm -rf /", "application/pdf")


def test_mime_spoofing_is_refused():
    """Real PNG bytes declared as a PDF: the parser would be the wrong one."""
    with pytest.raises(UnsupportedUploadError):
        validate_upload(PNG, "application/pdf")


def test_html_disguised_as_an_invoice_is_refused():
    with pytest.raises(UnsupportedUploadError):
        validate_upload(b"<html><body>not an invoice</body></html>", "application/pdf")


def test_an_empty_file_is_refused():
    with pytest.raises(UnsupportedUploadError):
        validate_upload(b"", "application/pdf")


def test_an_oversized_file_is_refused(monkeypatch):
    monkeypatch.setenv("MAX_UPLOAD_MB", "1")
    with pytest.raises(UnsupportedUploadError) as err:
        validate_upload(PDF + b"\x00" * (2 * 1024 * 1024), "application/pdf")
    assert "volumineux" in str(err.value)


def test_octet_stream_is_tolerated_when_the_bytes_are_right():
    """Many clients send application/octet-stream; the bytes decide."""
    assert validate_upload(PDF, "application/octet-stream") == "pdf"


def test_sniff_kind_returns_none_for_junk():
    assert sniff_kind(b"just some text") is None


# --------------------------------------------------------------------------- #
# Quotas — /ai/chat bills Anthropic on every call
# --------------------------------------------------------------------------- #
def test_a_tenant_is_throttled_after_its_quota():
    guard = QuotaGuard(_MemoryStore())
    for _ in range(5):
        assert guard.check("ai:tenant-a", limit=5, window_seconds=60) == 0
    wait = guard.check("ai:tenant-a", limit=5, window_seconds=60)
    assert wait > 0, "the 6th call must be refused"


def test_one_tenant_cannot_exhaust_another_tenants_quota():
    guard = QuotaGuard(_MemoryStore())
    for _ in range(6):
        guard.check("ai:noisy-tenant", limit=5, window_seconds=60)
    assert guard.check("ai:quiet-tenant", limit=5, window_seconds=60) == 0


def test_buckets_are_independent():
    """Burning the OCR quota must not block the assistant."""
    guard = QuotaGuard(_MemoryStore())
    for _ in range(6):
        guard.check("ocr:t1", limit=5, window_seconds=60)
    assert guard.check("ai:t1", limit=5, window_seconds=60) == 0


def test_quota_fails_open_when_the_store_is_broken():
    class Broken:
        def incr(self, *a, **k):
            raise ConnectionError("redis down")

        def ttl(self, *a, **k):
            raise ConnectionError("redis down")

    assert QuotaGuard(Broken()).check("ai:t1", limit=1, window_seconds=60) == 0
