"""Video import runtime configuration, read from environment.

Read fresh on each access (tests / live re-config), mirroring the OCR/AI modules.
"""
import os
from dataclasses import dataclass
from typing import List, Optional


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


@dataclass
class VideoConfig:
    # transcript
    youtube_caption_languages: List[str]
    allow_audio_stt: bool
    max_duration_seconds: int
    # speech-to-text (OpenAI Whisper by default)
    stt_provider: str
    openai_api_key: Optional[str]
    stt_model: str
    # extraction (reuses the AI model config but kept overridable here)
    transcript_char_limit: int
    # Proxy — YouTube blocks datacenter IPs (Render) with a bot check. Routing the
    # caption / yt-dlp requests through a residential proxy fixes the block. Both
    # a Webshare account and a generic http(s) proxy URL are supported; unset =
    # direct connection (works for the many videos YouTube does not block).
    webshare_user: Optional[str]
    webshare_pass: Optional[str]
    http_proxy: Optional[str]
    https_proxy: Optional[str]
    youtube_cookies_file: Optional[str]

    @property
    def stt_configured(self) -> bool:
        if self.stt_provider == "openai":
            return bool(self.openai_api_key)
        return False

    @property
    def has_proxy(self) -> bool:
        return bool((self.webshare_user and self.webshare_pass) or self.http_proxy or self.https_proxy)


def get_video_config() -> VideoConfig:
    raw_langs = os.getenv("VIDEO_YT_CAPTION_LANGS", "fr,en")
    langs = [l.strip() for l in raw_langs.split(",") if l.strip()]
    http_proxy = os.getenv("YOUTUBE_HTTP_PROXY") or os.getenv("HTTP_PROXY") or None
    https_proxy = os.getenv("YOUTUBE_HTTPS_PROXY") or os.getenv("HTTPS_PROXY") or http_proxy
    return VideoConfig(
        youtube_caption_languages=langs,
        allow_audio_stt=_bool("VIDEO_ALLOW_AUDIO_STT", True),
        max_duration_seconds=_int("VIDEO_MAX_DURATION_SECONDS", 1800),  # 30 min
        stt_provider=os.getenv("VIDEO_STT_PROVIDER", "openai").strip().lower(),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        stt_model=os.getenv("VIDEO_STT_MODEL", "whisper-1"),
        transcript_char_limit=_int("VIDEO_TRANSCRIPT_CHAR_LIMIT", 24000),
        webshare_user=os.getenv("WEBSHARE_PROXY_USERNAME") or None,
        webshare_pass=os.getenv("WEBSHARE_PROXY_PASSWORD") or None,
        http_proxy=http_proxy,
        https_proxy=https_proxy,
        youtube_cookies_file=os.getenv("YOUTUBE_COOKIES_FILE") or None,
    )
