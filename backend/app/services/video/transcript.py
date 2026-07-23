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


def _segments_to_text(segments) -> Optional[str]:
    text = " ".join(
        (s.get("text", "") if isinstance(s, dict) else getattr(s, "text", ""))
        for s in segments
    )
    return text.strip() or None


def _proxy_config():
    """Build a youtube-transcript-api proxy config from the environment, or None.

    A residential proxy is the reliable way past YouTube's datacenter-IP bot
    check (Render). Supports a Webshare account or a generic http(s) proxy URL.
    """
    cfg = get_video_config()
    try:
        if cfg.webshare_user and cfg.webshare_pass:
            from youtube_transcript_api.proxies import WebshareProxyConfig
            return WebshareProxyConfig(
                proxy_username=cfg.webshare_user, proxy_password=cfg.webshare_pass
            )
        if cfg.http_proxy or cfg.https_proxy:
            from youtube_transcript_api.proxies import GenericProxyConfig
            return GenericProxyConfig(http_url=cfg.http_proxy, https_url=cfg.https_proxy)
    except Exception:  # proxies module absent (old lib) — proceed without
        return None
    return None


def _list_transcripts(video_id: str):
    """Version-agnostic transcript listing.

    youtube-transcript-api 1.0 removed the static ``list_transcripts`` /
    ``get_transcript`` and replaced them with an *instance* ``list`` / ``fetch``.
    The code used to call only the old ones, so a version bump (the requirement
    was unpinned) silently broke every caption fetch with an AttributeError. We
    now support BOTH APIs so it cannot break on a bump again.
    """
    from youtube_transcript_api import YouTubeTranscriptApi

    if hasattr(YouTubeTranscriptApi, "list_transcripts"):
        return YouTubeTranscriptApi.list_transcripts(video_id)  # old (<1.0)
    proxy = _proxy_config()
    api = YouTubeTranscriptApi(proxy_config=proxy) if proxy else YouTubeTranscriptApi()
    return api.list(video_id)  # new (>=1.0)


def _youtube_captions(video_id: str) -> Optional[str]:
    """Return joined caption text, or None if unavailable.

    Coverage is deliberately broad so we call yt-dlp (which YouTube blocks from
    datacenter IPs) as rarely as possible: preferred-language manual captions,
    then preferred-language auto-generated, then ANY available track translated
    to a preferred language. A recipe video almost always has captions in *some*
    language, so this avoids the audio download for the vast majority of cases.
    """
    try:
        import youtube_transcript_api  # noqa: F401
    except ImportError:  # pragma: no cover - depends on install
        return None
    langs = get_video_config().youtube_caption_languages or ["en"]
    try:
        tl = _list_transcripts(video_id)
        transcript = None
        for finder in (tl.find_manually_created_transcript, tl.find_generated_transcript):
            try:
                transcript = finder(langs)
                break
            except Exception:
                continue
        if transcript is None:
            # No preferred-language track: take any and translate it.
            any_t = next(iter(tl), None)
            if any_t is None:
                return None
            transcript = any_t.translate(langs[0]) if getattr(any_t, "is_translatable", False) else any_t
        return _segments_to_text(transcript.fetch())
    except Exception as exc:
        log_event(logger, logging.INFO, "video.captions.unavailable", video_id=video_id, error=str(exc))
        return None


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
