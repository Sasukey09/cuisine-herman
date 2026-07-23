"""AI assistant runtime configuration, read from environment.

Read fresh on each access so tests (and live re-config) can override env vars
without restarting the process. Mirrors the pattern used by the OCR module.
"""
import os
from dataclasses import dataclass, field
from typing import FrozenSet, Optional


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _csv_set(raw: str) -> FrozenSet[str]:
    return frozenset(p.strip() for p in (raw or "").split(",") if p.strip())


@dataclass
class AIConfig:
    api_key: Optional[str]
    model: str            # default / complex model (Opus)
    simple_model: str     # cheaper model for simple questions (Haiku)
    routing_enabled: bool
    max_tokens: int
    effort: str
    max_tool_iterations: int
    # Model-compatibility allowlists. A model NOT listed here is called WITHOUT
    # the corresponding advanced parameter, so the assistant never sends a knob
    # the model rejects (the "adaptive thinking is not supported on this model"
    # 400). Both default to EMPTY: the knobs are strictly opt-in per model.
    thinking_models: FrozenSet[str] = field(default_factory=frozenset)  # -> `thinking`
    effort_models: FrozenSet[str] = field(default_factory=frozenset)    # -> `output_config`

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)


def get_ai_config() -> AIConfig:
    return AIConfig(
        # The anthropic SDK reads ANTHROPIC_API_KEY itself; we read it too only
        # to know whether the assistant is configured (and to fail fast / 503).
        api_key=os.getenv("ANTHROPIC_API_KEY"),
        model=os.getenv("AI_MODEL", "claude-opus-4-8"),
        # I6 — cost: a short factual question ("mon food cost moyen ?") does not
        # need Opus. Haiku is ~5x cheaper. Opus stays the default for anything
        # ambiguous or analytical.
        simple_model=os.getenv("AI_SIMPLE_MODEL", "claude-haiku-4-5"),
        routing_enabled=os.getenv("AI_MODEL_ROUTING", "true").lower() == "true",
        max_tokens=_int("AI_MAX_TOKENS", 4096),
        # low | medium | high | max — "medium" is a good cost/quality balance
        # for a chat assistant working over a small, structured dataset.
        effort=os.getenv("AI_EFFORT", "medium"),
        max_tool_iterations=_int("AI_MAX_TOOL_ITERATIONS", 8),
        # Comma-separated model ids that accept the advanced knobs. Empty by
        # default -> the assistant sends neither `thinking` nor `output_config`,
        # which is the safe baseline every current Claude model accepts. Opt a
        # capable model in explicitly, e.g. AI_THINKING_MODELS=claude-opus-4-8.
        thinking_models=_csv_set(os.getenv("AI_THINKING_MODELS", "")),
        effort_models=_csv_set(os.getenv("AI_EFFORT_MODELS", "")),
    )


# Words that signal an analytical / multi-step request -> keep Opus.
_COMPLEX_HINTS = (
    "analyse", "analyser", "compare", "comparer", "pourquoi", "optimise",
    "optimiser", "recommande", "recommandation", "stratégie", "strategie",
    "explique", "expliquer", "simule", "scénario", "scenario", "prévois",
    "prevois", "rentabilité", "rentabilite", "marge", "et si",
)
_SIMPLE_MAX_LEN = 160


def is_simple_message(message: str) -> bool:
    """Conservative: only clearly-simple, short, single-intent questions qualify
    for the cheaper model. Anything longer or analytical stays on Opus."""
    text = (message or "").strip()
    if not text or len(text) > _SIMPLE_MAX_LEN:
        return False
    low = text.lower()
    if any(hint in low for hint in _COMPLEX_HINTS):
        return False
    # more than one sentence usually means more than one intent
    if text.count(".") + text.count("?") + text.count("!") > 1:
        return False
    return True


def select_model(message: str, cfg: AIConfig) -> str:
    """Pick the model for a chat turn. Chosen ONCE per conversation (keeps the
    prompt cache valid across the tool loop) and defaults to Opus when unsure."""
    if cfg.routing_enabled and is_simple_message(message):
        return cfg.simple_model
    return cfg.model
