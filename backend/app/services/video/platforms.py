"""URL → platform detection and YouTube id extraction (pure, no I/O)."""
import re
from typing import Optional
from urllib.parse import urlparse, parse_qs

from .errors import UnsupportedURLError

_YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be"}
_PLATFORM_HOSTS = {
    "tiktok": ("tiktok.com",),
    "instagram": ("instagram.com",),
    "facebook": ("facebook.com", "fb.watch", "fb.com"),
    "vimeo": ("vimeo.com",),
    "dailymotion": ("dailymotion.com", "dai.ly"),
}


def detect_platform(url: str) -> str:
    """Return a platform key: youtube | tiktok | instagram | facebook | vimeo |
    dailymotion | other. Raises UnsupportedURLError for non-http(s) input."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise UnsupportedURLError(f"URL invalide : {url!r}")
    host = parsed.netloc.lower()
    if host in _YOUTUBE_HOSTS or host.endswith(".youtube.com"):
        return "youtube"
    for platform, hosts in _PLATFORM_HOSTS.items():
        if any(host == h or host.endswith("." + h) for h in hosts):
            return platform
    return "other"


def is_youtube(url: str) -> bool:
    return detect_platform(url) == "youtube"


def youtube_video_id(url: str) -> Optional[str]:
    """Extract the 11-char YouTube video id from common URL shapes."""
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if host == "youtu.be":
        vid = parsed.path.lstrip("/").split("/")[0]
        return vid or None
    if "youtube.com" in host:
        # /watch?v=ID
        qs = parse_qs(parsed.query)
        if "v" in qs and qs["v"]:
            return qs["v"][0]
        # /shorts/ID, /embed/ID, /live/ID
        m = re.match(r"^/(?:shorts|embed|live|v)/([^/?#]+)", parsed.path)
        if m:
            return m.group(1)
    return None
