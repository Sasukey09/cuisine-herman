"""Video import errors."""


class VideoError(Exception):
    """Base error for the video import pipeline."""


class UnsupportedURLError(VideoError):
    """The URL is not a recognised video link."""


class TranscriptUnavailableError(VideoError):
    """No transcript could be obtained (no captions and STT unavailable/failed)."""


class STTNotConfiguredError(VideoError):
    """No speech-to-text provider is configured (e.g. missing OPENAI_API_KEY)."""


class AudioDownloadError(VideoError):
    """Downloading the audio track failed (yt-dlp/ffmpeg)."""


class VideoTooLongError(VideoError):
    """The video exceeds the configured maximum duration."""


class RecipeExtractionError(VideoError):
    """The LLM could not produce a structured recipe from the transcript."""
