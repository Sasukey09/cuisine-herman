"""Audio download via yt-dlp (+ ffmpeg) for non-caption platforms.

Lazy-imports yt-dlp so the app runs without it. Probes duration first to enforce
the configured max, then downloads the audio track to a temp mp3.
"""
import glob
import os
import tempfile
from typing import Any, Dict

from .config import get_video_config
from .errors import AudioDownloadError, VideoTooLongError


def _ydl():
    try:
        import yt_dlp
    except ImportError as exc:  # pragma: no cover - depends on install
        raise AudioDownloadError("yt-dlp is not installed") from exc
    return yt_dlp


def probe_duration(url: str) -> Dict[str, Any]:
    """Return {duration, title, ...} without downloading (raises on failure)."""
    yt_dlp = _ydl()
    try:
        with yt_dlp.YoutubeDL({"quiet": True, "noplaylist": True, "skip_download": True}) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:
        raise AudioDownloadError(f"Impossible de lire la vidéo : {exc}") from exc
    return {"duration": info.get("duration"), "title": info.get("title")}


def download_audio(url: str) -> str:
    """Download the audio track to a temp mp3 and return its path.

    Enforces VIDEO_MAX_DURATION_SECONDS. Caller is responsible for cleanup.
    """
    cfg = get_video_config()
    info = probe_duration(url)
    duration = info.get("duration")
    if duration and cfg.max_duration_seconds and duration > cfg.max_duration_seconds:
        raise VideoTooLongError(
            f"Vidéo trop longue ({int(duration)}s > {cfg.max_duration_seconds}s)"
        )

    yt_dlp = _ydl()
    tmp_dir = tempfile.mkdtemp(prefix="ch_video_")
    out_template = os.path.join(tmp_dir, "audio.%(ext)s")
    opts = {
        "format": "bestaudio/best",
        "outtmpl": out_template,
        "quiet": True,
        "noplaylist": True,
        "postprocessors": [
            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "128"}
        ],
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.extract_info(url, download=True)
    except Exception as exc:
        raise AudioDownloadError(f"Échec du téléchargement audio : {exc}") from exc

    matches = glob.glob(os.path.join(tmp_dir, "audio.*"))
    mp3 = [m for m in matches if m.endswith(".mp3")]
    path = (mp3 or matches or [None])[0]
    if not path or not os.path.exists(path):
        raise AudioDownloadError("Fichier audio introuvable après téléchargement")
    return path
