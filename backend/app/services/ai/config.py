"""AI assistant runtime configuration, read from environment.

Read fresh on each access so tests (and live re-config) can override env vars
without restarting the process. Mirrors the pattern used by the OCR module.
"""
import os
from dataclasses import dataclass
from typing import Optional


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


@dataclass
class AIConfig:
    api_key: Optional[str]
    model: str
    max_tokens: int
    effort: str
    max_tool_iterations: int

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)


def get_ai_config() -> AIConfig:
    return AIConfig(
        # The anthropic SDK reads ANTHROPIC_API_KEY itself; we read it too only
        # to know whether the assistant is configured (and to fail fast / 503).
        api_key=os.getenv("ANTHROPIC_API_KEY"),
        model=os.getenv("AI_MODEL", "claude-opus-4-8"),
        max_tokens=_int("AI_MAX_TOKENS", 4096),
        # low | medium | high | max — "medium" is a good cost/quality balance
        # for a chat assistant working over a small, structured dataset.
        effort=os.getenv("AI_EFFORT", "medium"),
        max_tool_iterations=_int("AI_MAX_TOOL_ITERATIONS", 8),
    )
