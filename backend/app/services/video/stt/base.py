"""Speech-to-text provider interface."""
from typing import Protocol


class STTProvider(Protocol):
    def is_configured(self) -> bool:
        ...

    def transcribe(self, audio_path: str, language: str = None) -> str:
        """Return the transcript text for the audio file at ``audio_path``."""
        ...
