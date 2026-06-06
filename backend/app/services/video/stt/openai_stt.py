"""OpenAI Whisper speech-to-text provider.

Used for platforms without usable captions (TikTok / Instagram / Facebook …):
the audio is downloaded, then sent to OpenAI's transcription endpoint. Requires
``OPENAI_API_KEY`` and the ``openai`` SDK (lazy-imported so the app runs without
it). Injectable client for tests.
"""
from typing import Any, Optional

from ..config import get_video_config
from ..errors import STTNotConfiguredError, VideoError


class OpenAISTTProvider:
    def __init__(self, client: Any = None):
        self._client = client

    def is_configured(self) -> bool:
        return bool(get_video_config().openai_api_key)

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        if not self.is_configured():
            raise STTNotConfiguredError("OPENAI_API_KEY is not set")
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - depends on install
            raise STTNotConfiguredError("openai SDK is not installed") from exc
        self._client = OpenAI()
        return self._client

    def transcribe(self, audio_path: str, language: Optional[str] = None) -> str:
        client = self._get_client()
        model = get_video_config().stt_model
        try:
            with open(audio_path, "rb") as fh:
                kwargs = {"model": model, "file": fh}
                if language:
                    kwargs["language"] = language
                result = client.audio.transcriptions.create(**kwargs)
        except STTNotConfiguredError:
            raise
        except Exception as exc:
            raise VideoError(f"STT transcription failed: {exc}") from exc
        text = getattr(result, "text", None)
        if not text:
            raise VideoError("STT returned an empty transcript")
        return text
