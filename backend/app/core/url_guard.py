"""SSRF guard for URLs the *server* is about to fetch.

The video importer hands a user-supplied URL to yt-dlp, which will happily go
and read `http://169.254.169.254/latest/meta-data/` (cloud credentials), an
internal admin panel, or a database sitting on the private network — and hand
the body back to the caller. Two layers, because either alone has a hole:

1. **Host allowlist** — only the platforms the product actually advertises.
   This is what closes the attack: those hosts are public by construction.
2. **Resolved-IP check** — every address the host resolves to must be a public
   one. This still holds if someone points a public-looking name at 127.0.0.1,
   and it is the only protection left when the allowlist is opened up.

Known residual risk: DNS rebinding (we resolve, then yt-dlp resolves again and
could get a different answer). The host allowlist makes that academic here; if
the allowlist is ever disabled, pin the IP instead.
"""
import ipaddress
import os
import socket
from typing import Iterable
from urllib.parse import urlparse


class UnsafeURLError(Exception):
    """The server refused to fetch this URL."""


# Hosts the product supports. A leading dot means "and any subdomain".
ALLOWED_VIDEO_HOSTS: tuple = (
    "youtube.com",
    "youtu.be",
    "tiktok.com",
    "instagram.com",
    "facebook.com",
    "fb.watch",
    "fb.com",
    "vimeo.com",
    "dailymotion.com",
    "dai.ly",
)


def _host_allowed(host: str, allowed: Iterable[str]) -> bool:
    host = host.lower().rstrip(".")
    return any(host == h or host.endswith("." + h) for h in allowed)


def _assert_public_ips(host: str, port: int) -> None:
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise UnsafeURLError(f"Hôte introuvable : {host}") from exc

    for info in infos:
        addr = info[4][0]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:  # pragma: no cover - getaddrinfo always yields an IP
            raise UnsafeURLError(f"Adresse illisible pour {host}")
        # is_global is False for private, loopback, link-local (incl. the cloud
        # metadata address 169.254.169.254), reserved and unspecified ranges.
        if not ip.is_global or ip.is_multicast:
            raise UnsafeURLError(
                "Cette URL pointe vers une adresse interne — refusée."
            )


def assert_safe_fetch_url(url: str, allowed_hosts: Iterable[str] = ALLOWED_VIDEO_HOSTS) -> None:
    """Raise :class:`UnsafeURLError` unless the server may fetch ``url``.

    Set ``VIDEO_ALLOW_ANY_HOST=true`` to drop the host allowlist (the private-IP
    check still applies — it is never optional).
    """
    parsed = urlparse((url or "").strip())

    if parsed.scheme not in ("http", "https"):
        raise UnsafeURLError("Seules les URL http(s) sont acceptées.")
    if parsed.username or parsed.password:
        raise UnsafeURLError("Les identifiants dans l'URL ne sont pas acceptés.")

    host = parsed.hostname
    if not host:
        raise UnsafeURLError("URL sans nom d'hôte.")

    allow_any = os.getenv("VIDEO_ALLOW_ANY_HOST", "false").strip().lower() in ("1", "true", "yes")
    if not allow_any and not _host_allowed(host, allowed_hosts):
        raise UnsafeURLError(
            "Plateforme non supportée. Collez un lien YouTube, TikTok, "
            "Instagram, Facebook, Vimeo ou Dailymotion."
        )

    _assert_public_ips(host, parsed.port or (443 if parsed.scheme == "https" else 80))
