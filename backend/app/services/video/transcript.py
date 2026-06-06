"""Obtain a transcript for a video URL.

Strategy:
  1. YouTube with captions → fetch captions directly (no download, no STT key).
  2. Otherwise (or no captions) → download audio (yt-dlp) and transcribe via STT.

Returns ``(text, source)`` where source ∈ {"youtube_captions", "stt"}.
Heavy deps (youtube-transcript-api, yt-dlp, openai) are lazy-imported so the
service module imports cleanly without them; an injectable STT provider keeps
the orchestration unit-testable.
"""
import logging
import os
from typing import Any, Optional, Tuple

from app.core.logging import get_logger, log_event
from .config import get_video_config
from .errors import STTNotConfiguredError, TranscriptUnavailableError
from .platforms import detect_platform, youtube_video_id

logger = get_logger("video.transcript")


def _youtube_captions(video_id: str) -> Optional[str]:
    """Return joined caption text, or None if unavailable."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:  # pragma: no cover - depends on install
        return None
    langs = get_video_config().youtube_caption_languages or ["en"]
    try:
        segments = YouTubeTranscriptApi.get_transcript(video_id, languages=langs)
    except Exception as exc:
        log_event(logger, logging.INFO, "video.captions.unavailable", video_id=video_id, error=str(exc))
        return None
    text = " ".join(s.get("text", "") for s in segments if s.get("text"))
    return text.strip() or None


def _audio_stt(url: str, stt_provider: Any) -> str:
    from . import audio as audio_mod

    provider = stt_provider
    if provider is None:
        from .stt.openai_stt import OpenAISTTProvider

        provider = OpenAISTTProvider()
    if not provider.is_configured():
        raise STTNotConfiguredError(
            "Transcription audio indisponible : configurez un service STT "
            "(OPENAI_API_KEY) pour les plateformes sans sous-titres."
        )

    audio_path = audio_mod.download_audio(url)
    try:
        return provider.transcribe(audio_path)
    finally:
        try:
            os.remove(audio_path)
        except OSError:
            pass


def get_transcript(url: str, stt_provider: Any = None) -> Tuple[str, str]:
    """Return (transcript_text, source). Raises TranscriptUnavailableError."""
    cfg = get_video_config()
    platform = detect_platform(url)

    if platform == "youtube":
        vid = youtube_video_id(url)
        if vid:
            captions = _youtube_captions(vid)
            if captions:
                log_event(logger, logging.INFO, "video.transcript.ok", source="youtube_captions", chars=len(captions))
                return captions, "youtube_captions"

    if not cfg.allow_audio_stt:
        raise TranscriptUnavailableError(
            "Aucun sous-titre disponible et la transcription audio est désactivée."
        )

    text = _audio_stt(url, stt_provider)
    if not text:
        raise TranscriptUnavailableError("Transcription vide.")
    log_event(logger, logging.INFO, "video.transcript.ok", source="stt", chars=len(text))
    return text, "stt"
