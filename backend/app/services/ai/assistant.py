"""AI assistant — Claude-backed, tenant-scoped, tool-using.

Runs a *manual* agentic loop (rather than the SDK tool runner) on purpose: each
tool call must execute against the caller's ``db`` session and ``tenant_id``, so
the loop owns dispatch and keeps that context out of the model's reach.

Model: ``claude-opus-4-8`` by default (configurable via ``AI_MODEL``). Advanced
knobs (``thinking``, ``output_config.effort``) are sent ONLY to models that opt
in via ``AI_THINKING_MODELS`` / ``AI_EFFORT_MODELS`` and that haven't rejected
them at runtime — so the assistant never sends a parameter a model refuses (the
"adaptive thinking is not supported on this model" 400). The anthropic client is
injectable so the loop is unit-testable without network access or an API key.
"""
import json
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.logging import get_logger, log_event
from .config import AIConfig, get_ai_config, select_model
from .errors import AINotConfiguredError, AIProviderError
from . import context as ai_context
from . import tools as ai_tools

logger = get_logger("ai.assistant")

# Models observed at runtime to reject an advanced knob -> never offer it to that
# model again this process, even if the config allowlist still names it. This is
# the safety net behind the config allowlist: one 400 is enough to stop sending
# the incompatible parameter for good.
_UNSUPPORTED_THINKING: set = set()
_UNSUPPORTED_EFFORT: set = set()

# Substrings that identify a "the model doesn't accept this parameter" failure
# (SDK TypeError message or Anthropic invalid_request_error body) — as opposed to
# a genuine outage/auth/rate-limit error, which must NOT be retried.
_INCOMPATIBLE_PARAM_HINTS = (
    "thinking", "adaptive", "output_config", "effort",
    "not supported", "unsupported", "unexpected keyword",
)


def _is_incompatible_param_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(hint in msg for hint in _INCOMPATIBLE_PARAM_HINTS)


def _remember_unsupported(model: str, advanced: Dict[str, Any]) -> None:
    """Record which knob(s) this model just rejected so future calls skip them."""
    if "thinking" in advanced:
        _UNSUPPORTED_THINKING.add(model)
    if "output_config" in advanced:
        _UNSUPPORTED_EFFORT.add(model)

SYSTEM_PROMPT = (
    "Tu es l'assistant IA de FoodGad, une plateforme de gestion de "
    "restauration. Tu aides à analyser les recettes, optimiser les coûts "
    "matière, suggérer des remplacements d'ingrédients moins chers, détecter les "
    "erreurs de fiches techniques et répondre aux questions de gestion.\n\n"
    "Tu disposes d'outils pour lire les données réelles du restaurant (recettes, "
    "coûts, produits, prix, alertes). Utilise-les pour fonder tes réponses sur "
    "des chiffres réels plutôt que de deviner. N'invente jamais de prix, de "
    "recette ou d'identifiant : si une donnée manque, dis-le.\n\n"
    "Quand une fiche a des prix manquants (champ 'missing_price' / "
    "'has_missing_prices'), signale-le explicitement car le coût est alors "
    "sous-estimé.\n\n"
    "Tu peux aussi créer des produits (create_product) et une fiche technique "
    "brouillon (create_recipe_draft) — mais UNIQUEMENT si l'utilisateur le "
    "demande explicitement. Avant de créer une fiche : demande le nombre de "
    "portions s'il manque, et préviens toujours que les quantités sont estimées "
    "et doivent être validées. Après création, indique les ingrédients non "
    "reconnus et le coût obtenu. IMPORTANT : pour qu'une nouvelle recette soit "
    "chiffrée, crée d'abord les produits manquants (avec leur prix) PUIS la "
    "fiche — le rapprochement ingrédient→produit se fait par nom au moment de la "
    "création de la fiche. Si une fiche a été créée AVANT ses produits, crée les "
    "produits manquants puis appelle link_recipe_products pour relier la fiche et "
    "recalculer son coût.\n\n"
    "Réponds en français, de façon concise et actionnable, en citant les "
    "chiffres clés (coût par portion, food cost %, marge)."
)


class AIAssistant:
    def __init__(self, client: Any = None, config: Optional[AIConfig] = None):
        self._client = client
        self._config = config

    @property
    def config(self) -> AIConfig:
        # read fresh unless explicitly injected (mirrors OCR config behaviour)
        return self._config or get_ai_config()

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        cfg = self.config
        if not cfg.is_configured:
            raise AINotConfiguredError("ANTHROPIC_API_KEY is not set")
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - depends on install
            raise AINotConfiguredError("anthropic SDK is not installed") from exc
        self._client = anthropic.Anthropic()
        return self._client

    def _advanced_kwargs(self, cfg: AIConfig, model: str) -> Dict[str, Any]:
        """The advanced knobs THIS model is known to accept — nothing more.

        A model is offered `thinking` / `output_config` only if the config
        allowlist opts it in AND it hasn't already rejected that knob at runtime.
        With the default (empty) allowlists this returns ``{}``, so the baseline
        call carries no parameter any current Claude model would reject.
        """
        kw: Dict[str, Any] = {}
        if model in cfg.thinking_models and model not in _UNSUPPORTED_THINKING:
            kw["thinking"] = {"type": "adaptive"}
        if model in cfg.effort_models and model not in _UNSUPPORTED_EFFORT:
            kw["output_config"] = {"effort": cfg.effort}
        return kw

    def _create(
        self,
        cfg: AIConfig,
        messages: List[Dict[str, Any]],
        system: Any,
        model: str,
    ):
        client = self._get_client()
        base: Dict[str, Any] = {
            "model": model,
            "max_tokens": cfg.max_tokens,
            "system": system,
            "messages": messages,
            "tools": ai_tools.tool_schemas(),
        }
        advanced = self._advanced_kwargs(cfg, model)
        try:
            return client.messages.create(**base, **advanced)
        except AINotConfiguredError:
            raise
        except Exception as exc:
            # Self-healing compatibility net: if we sent an advanced knob and the
            # failure is the model rejecting it — an older SDK `TypeError`, or a
            # provider 400 like "adaptive thinking is not supported on this model"
            # — disable that knob for this model and retry ONCE without any of the
            # advanced kwargs. Genuine failures (auth, rate limit) are not retried.
            if advanced and _is_incompatible_param_error(exc):
                _remember_unsupported(model, advanced)
                log_event(
                    logger, logging.WARNING, "ai.incompatible_params_stripped",
                    model=model, params=sorted(advanced), detail=str(exc)[:200],
                )
                try:
                    return client.messages.create(**base)
                except Exception as exc2:
                    raise AIProviderError(str(exc2)) from exc2
            raise AIProviderError(str(exc)) from exc

    def chat(
        self,
        db: Session,
        tenant_id: str,
        message: str,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        cfg = self.config

        # The assistant used to start blind: it had to guess that a tool call
        # might reveal a price spike. Now it already knows what is going wrong in
        # THIS restaurant before the chef says a word.
        situation = ai_context.build_situation(db, tenant_id)
        briefing = ai_context.render_briefing(situation)
        # Prompt caching (I6): the large, stable SYSTEM_PROMPT — and the tool
        # schemas that render before it — are cached at this breakpoint. The
        # per-tenant briefing sits AFTER it (no breakpoint) because it changes
        # every request. The cached prefix is reused across the tool loop and
        # across requests within the cache TTL, cutting input cost sharply.
        system: List[Dict[str, Any]] = [
            {"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}},
        ]
        if briefing:
            system.append({"type": "text", "text": briefing})

        # Pick the model ONCE for the whole conversation: a simple question runs
        # on Haiku, everything else on Opus. Choosing once keeps the prompt cache
        # valid (switching models mid-loop would invalidate it).
        model = select_model(message, cfg)

        messages: List[Dict[str, Any]] = []
        for turn in history or []:
            role = turn.get("role")
            content = turn.get("content")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": message})

        tool_calls: List[Dict[str, Any]] = []
        usage = {"input_tokens": 0, "output_tokens": 0}
        reply_text = ""

        for iteration in range(cfg.max_tool_iterations):
            response = self._create(cfg, messages, system, model)
            _accumulate_usage(usage, getattr(response, "usage", None))

            content_blocks = list(getattr(response, "content", []) or [])
            text_parts = [
                getattr(b, "text", "") for b in content_blocks if getattr(b, "type", None) == "text"
            ]
            if text_parts:
                reply_text = "\n".join(t for t in text_parts if t)

            if getattr(response, "stop_reason", None) != "tool_use":
                break

            # echo the assistant turn (incl. tool_use blocks) back into history
            messages.append({"role": "assistant", "content": content_blocks})

            tool_results = []
            for block in content_blocks:
                if getattr(block, "type", None) != "tool_use":
                    continue
                name = getattr(block, "name", "")
                tool_input = getattr(block, "input", {}) or {}
                log_event(logger, logging.INFO, "ai.tool_use", tool=name, tenant=tenant_id)
                result = ai_tools.execute_tool(db, tenant_id, name, tool_input)
                tool_calls.append({"name": name, "input": tool_input})
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": getattr(block, "id", None),
                        "content": json.dumps(result, ensure_ascii=False, default=str),
                    }
                )
            messages.append({"role": "user", "content": tool_results})
        else:
            log_event(
                logger, logging.WARNING, "ai.max_iterations",
                tenant=tenant_id, iterations=cfg.max_tool_iterations,
            )

        log_event(
            logger, logging.INFO, "ai.chat.done",
            tenant=tenant_id, tool_calls=len(tool_calls),
            input_tokens=usage["input_tokens"], output_tokens=usage["output_tokens"],
        )
        return {"reply": reply_text, "tool_calls": tool_calls, "usage": usage}


def _accumulate_usage(acc: Dict[str, int], usage: Any) -> None:
    if usage is None:
        return
    acc["input_tokens"] += int(getattr(usage, "input_tokens", 0) or 0)
    acc["output_tokens"] += int(getattr(usage, "output_tokens", 0) or 0)


_assistant: Optional[AIAssistant] = None


def get_assistant() -> AIAssistant:
    global _assistant
    if _assistant is None:
        _assistant = AIAssistant()
    return _assistant
