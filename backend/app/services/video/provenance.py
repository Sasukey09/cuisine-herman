"""Provenance & indices de segmentation d'une vidéo (best-effort).

- oEmbed YouTube : titre, créateur, miniature — sans clé API.
- Parsing des timestamps de description et des chapitres → indices pour le LLM.
Tout est best-effort : un échec réseau ne bloque jamais l'extraction.
"""
from __future__ import annotations

import json
import re
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import quote

from app.core.url_guard import assert_safe_fetch_url
from .platforms import youtube_video_id

_TS = re.compile(r"^\s*(?:(\d+):)?(\d{1,2}):(\d{2})\s+(.+?)\s*$")


def video_id_of(url: str) -> Optional[str]:
    return youtube_video_id(url)


def parse_description_timestamps(text: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for line in (text or "").splitlines():
        m = _TS.match(line)
        if not m:
            continue
        h, mm, ss, label = m.groups()
        sec = (int(h) if h else 0) * 3600 + int(mm) * 60 + int(ss)
        out.append({"sec": sec, "label": label.strip()})
    return out


def chapters_from_info(info: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = []
    for c in (info or {}).get("chapters") or []:
        if c.get("start_time") is None:
            continue
        out.append({"start_sec": int(c["start_time"]), "title": (c.get("title") or "").strip()})
    return out


def _default_fetcher(url: str) -> Dict[str, Any]:  # pragma: no cover - network
    import urllib.request
    assert_safe_fetch_url(url)
    with urllib.request.urlopen(url, timeout=6) as r:
        return json.loads(r.read().decode("utf-8"))


def fetch_oembed(url: str, fetcher: Optional[Callable[[str], Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Titre/créateur/miniature via oEmbed. Best-effort : {} si échec."""
    fetcher = fetcher or _default_fetcher
    try:
        endpoint = "https://www.youtube.com/oembed?format=json&url=" + quote(url, safe="")
        data = fetcher(endpoint)
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    return {
        "title": data.get("title"),
        "creator": data.get("author_name"),
        "thumbnail": data.get("thumbnail_url"),
    }


def build_source(url: str, platform: str, oembed: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "platform": platform,
        "url": url,
        "video_id": video_id_of(url),
        "title": oembed.get("title"),
        "creator": oembed.get("creator"),
        "thumbnail": oembed.get("thumbnail"),
    }
