"""AI assistant errors."""


class AIError(Exception):
    """Base error for the AI assistant."""


class AINotConfiguredError(AIError):
    """Raised when no LLM provider credential is configured."""


class AIProviderError(AIError):
    """Raised when the LLM provider call fails."""
