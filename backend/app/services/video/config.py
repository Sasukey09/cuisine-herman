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

    @property
    def stt_configured(self) -> bool:
        if self.stt_provider == "openai":
            return bool(self.openai_api_key)
        return False


def get_video_config() -> VideoConfig:
    raw_langs = os.getenv("VIDEO_YT_CAPTION_LANGS", "fr,en")
    langs = [l.strip() for l in raw_langs.split(",") if l.strip()]
    return VideoConfig(
        youtube_caption_languages=langs,
        allow_audio_stt=_bool("VIDEO_ALLOW_AUDIO_STT", True),
        max_duration_seconds=_int("VIDEO_MAX_DURATION_SECONDS", 1800),  # 30 min
        stt_provider=os.getenv("VIDEO_STT_PROVIDER", "openai").strip().lower(),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        stt_model=os.getenv("VIDEO_STT_MODEL", "whisper-1"),
        transcript_char_limit=_int("VIDEO_TRANSCRIPT_CHAR_LIMIT", 24000),
    )
