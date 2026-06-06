"""Extract a structured recipe draft from transcript text, using Claude.

Returns an editable draft dict:
    {name, yield_qty, ingredients: [{name, qty, unit}], steps: [str], summary}

Asks the model for JSON only and parses it tolerantly. The anthropic client is
injectable so this is unit-testable without a key/network. Quantities are
estimates by design — the caller must flag them as "to validate".
"""
import json
import re
from typing import Any, Dict, List, Optional

from app.services.ai.config import get_ai_config
from .config import get_video_config
from .errors import RecipeExtractionError

SYSTEM_PROMPT = (
    "Tu extrais une fiche recette structurée à partir de la transcription d'une "
    "vidéo de cuisine. Réponds UNIQUEMENT avec un objet JSON valide, sans texte "
    "autour, au format exact :\n"
    '{"name": str, "yield_qty": number, "ingredients": [{"name": str, '
    '"qty": number|null, "unit": str|null}], "steps": [str], "summary": str}\n\n'
    "Règles : noms d'ingrédients en français, courts et génériques (ex. 'farine', "
    "'beurre', 'fraises'). Unités via les codes g, kg, l, ml, piece. Estime les "
    "quantités manquantes de façon raisonnable (qty=null seulement si vraiment "
    "impossible). yield_qty = nombre de portions (estime si non précisé). steps = "
    "étapes principales, concises. Si la transcription n'est pas une recette, "
    'renvoie {"name": "", "ingredients": []}.'
)


def _parse_json(text: str) -> Dict[str, Any]:
    text = (text or "").strip()
    # strip ```json fences if present
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text).strip()
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        pass
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except (ValueError, TypeError):
            pass
    raise RecipeExtractionError("Réponse du modèle non parsable en JSON")


def _normalize(raw: Dict[str, Any]) -> Dict[str, Any]:
    ingredients: List[Dict[str, Any]] = []
    for ing in raw.get("ingredients") or []:
        if not isinstance(ing, dict):
            continue
        name = (ing.get("name") or "").strip()
        if not name:
            continue
        ingredients.append(
            {
                "name": name,
                "qty": ing.get("qty"),
                "unit": (ing.get("unit") or "").strip().lower() or None,
            }
        )
    steps = [s.strip() for s in (raw.get("steps") or []) if isinstance(s, str) and s.strip()]
    try:
        yield_qty = float(raw.get("yield_qty")) if raw.get("yield_qty") is not None else None
    except (ValueError, TypeError):
        yield_qty = None
    return {
        "name": (raw.get("name") or "").strip(),
        "yield_qty": yield_qty,
        "ingredients": ingredients,
        "steps": steps,
        "summary": (raw.get("summary") or "").strip() or None,
    }


class RecipeExtractor:
    def __init__(self, client: Any = None):
        self._client = client

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        cfg = get_ai_config()
        if not cfg.is_configured:
            raise RecipeExtractionError("ANTHROPIC_API_KEY is not set")
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - depends on install
            raise RecipeExtractionError("anthropic SDK is not installed") from exc
        self._client = anthropic.Anthropic()
        return self._client

    def extract(self, transcript: str, hint_title: Optional[str] = None) -> Dict[str, Any]:
        cfg = get_ai_config()
        client = self._get_client()
        char_limit = get_video_config().transcript_char_limit
        content = transcript[:char_limit] if char_limit else transcript
        user = (
            (f"Titre de la vidéo : {hint_title}\n\n" if hint_title else "")
            + "Transcription :\n"
            + content
        )
        try:
            resp = client.messages.create(
                model=cfg.model,
                max_tokens=cfg.max_tokens,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user}],
            )
        except RecipeExtractionError:
            raise
        except Exception as exc:
            raise RecipeExtractionError(f"Appel au modèle échoué : {exc}") from exc

        text = ""
        for block in getattr(resp, "content", []) or []:
            if getattr(block, "type", None) == "text":
                text += getattr(block, "text", "")
        draft = _normalize(_parse_json(text))
        if not draft["name"] and not draft["ingredients"]:
            raise RecipeExtractionError("La vidéo ne semble pas contenir de recette exploitable.")
        return draft


_extractor: Optional[RecipeExtractor] = None


def get_extractor() -> RecipeExtractor:
    global _extractor
    if _extractor is None:
        _extractor = RecipeExtractor()
    return _extractor
