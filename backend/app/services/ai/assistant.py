"""AI assistant — Claude-backed, tenant-scoped, tool-using.

Runs a *manual* agentic loop (rather than the SDK tool runner) on purpose: each
tool call must execute against the caller's ``db`` session and ``tenant_id``, so
the loop owns dispatch and keeps that context out of the model's reach.

Model: ``claude-opus-4-8`` by default (configurable via ``AI_MODEL``), adaptive
thinking + ``effort`` for cost/quality control. The anthropic client is
injectable so the loop is unit-testable without network access or an API key.
"""
import json
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.logging import get_logger, log_event
from .config import AIConfig, get_ai_config
from .errors import AINotConfiguredError, AIProviderError
from . import context as ai_context
from . import tools as ai_tools

logger = get_logger("ai.assistant")

SYSTEM_PROMPT = (
    "Tu es l'assistant IA de Cuisine Herman, une plateforme de gestion de "
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

    def _create(self, cfg: AIConfig, messages: List[Dict[str, Any]], system_prompt: str):
        client = self._get_client()
        kwargs: Dict[str, Any] = {
            "model": cfg.model,
            "max_tokens": cfg.max_tokens,
            "system": system_prompt,
            "messages": messages,
            "tools": ai_tools.tool_schemas(),
            "thinking": {"type": "adaptive"},
            "output_config": {"effort": cfg.effort},
        }
        try:
            return client.messages.create(**kwargs)
        except TypeError:
            # Older anthropic SDK builds may not accept thinking/output_config as
            # kwargs. Retry without the advanced knobs rather than hard-failing.
            for key in ("thinking", "output_config"):
                kwargs.pop(key, None)
            return client.messages.create(**kwargs)
        except AINotConfiguredError:
            raise
        except Exception as exc:
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
        system_prompt = SYSTEM_PROMPT + ai_context.render_briefing(situation)

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
            response = self._create(cfg, messages, system_prompt)
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
