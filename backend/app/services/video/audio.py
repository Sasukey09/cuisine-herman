"""Audio download via yt-dlp (+ ffmpeg) for non-caption platforms.

Lazy-imports yt-dlp so the app runs without it. Probes duration first to enforce
the configured max, then downloads the audio track to a temp mp3.

Uses anti-detection options (alternate YouTube player clients + a desktop
User-Agent) to reduce YouTube's "confirm you're not a bot" blocks. These help
but are not guaranteed — YouTube actively blocks datacenter IPs; for those,
captions (subtitled videos) or other platforms (TikTok/Instagram) are more
reliable, and a cookies file is the robust workaround.
"""
import glob
import os
import subprocess
import tempfile
from typing import Any, Dict

from .config import get_video_config
from .errors import AudioDownloadError, VideoTooLongError


def transcode_to_mp3(input_path: str) -> str:
    """Transcode an uploaded media file to a small mono 16kHz mp3 with ffmpeg.

    Strips video and keeps the result well under Whisper's 25MB cap (~0.5MB/min).
    """
    out_path = input_path + ".out.mp3"
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", input_path, "-vn", "-ac", "1", "-ar", "16000",
             "-b:a", "64k", out_path],
            check=True, capture_output=True, timeout=900,
        )
    except FileNotFoundError as exc:  # pragma: no cover - ffmpeg ships in the image
        raise AudioDownloadError("ffmpeg n'est pas disponible sur le serveur.") from exc
    except subprocess.TimeoutExpired as exc:
        raise AudioDownloadError("Conversion audio trop longue (fichier trop volumineux ?).") from exc
    except subprocess.CalledProcessError as exc:
        raise AudioDownloadError(
            "Impossible de lire ce fichier (format vidéo/audio non reconnu)."
        ) from exc
    return out_path


# Try alternate clients first (often bypass the bot check), then the default web.
_BASE_OPTS: Dict[str, Any] = {
    "quiet": True,
    "noplaylist": True,
    "extractor_args": {"youtube": {"player_client": ["android", "web"]}},
    "http_headers": {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        )
    },
}


def _ydl():
    try:
        import yt_dlp
    except ImportError as exc:  # pragma: no cover - depends on install
        raise AudioDownloadError("yt-dlp is not installed") from exc
    return yt_dlp


def _friendly_error(exc: Exception) -> str:
    msg = str(exc)
    low = msg.lower()
    if "bot" in low and ("sign in" in low or "confirm" in low):
        return (
            "YouTube a bloqué le téléchargement (protection anti-robot). "
            "Essaie une vidéo YouTube avec sous-titres, ou un lien TikTok/Instagram."
        )
    if "private" in low or "unavailable" in low:
        return "Vidéo indisponible ou privée."
    return f"Impossible de lire la vidéo : {msg}"


def probe_duration(url: str) -> Dict[str, Any]:
    """Return {duration, title, ...} without downloading (raises on failure)."""
    yt_dlp = _ydl()
    opts = {**_BASE_OPTS, "skip_download": True}
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:
        raise AudioDownloadError(_friendly_error(exc)) from exc
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
        **_BASE_OPTS,
        "format": "bestaudio/best",
        "outtmpl": out_template,
        "postprocessors": [
            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "128"}
        ],
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.extract_info(url, download=True)
    except Exception as exc:
        raise AudioDownloadError(_friendly_error(exc)) from exc

    matches = glob.glob(os.path.join(tmp_dir, "audio.*"))
    mp3 = [m for m in matches if m.endswith(".mp3")]
    path = (mp3 or matches or [None])[0]
    if not path or not os.path.exists(path):
        raise AudioDownloadError("Fichier audio introuvable après téléchargement")
    return path
