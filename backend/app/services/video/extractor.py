"""Extract structured recipe drafts from transcript text, using Claude.

A video transcript may contain several recipes, so this returns a LIST of
editable draft dicts (never a bare dict):
    [{name, description, summary, yield_qty, ingredients: [{name, qty, unit}],
      steps: [str], prep_time_min, cook_time_min, tips: [str], variants: [str],
      allergens: [str], start_sec, end_sec}, ...]

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
    "Tu analyses la transcription d'une vidéo de cuisine qui peut contenir "
    "PLUSIEURS recettes. Détecte TOUTES les recettes présentes. Ne t'arrête "
    "JAMAIS à la première. Utilise tous les indices de changement de recette : "
    "titre annoncé, 'ensuite'/'maintenant'/'deuxième recette'/'pour la prochaine', "
    "changement d'ingrédients ou d'étapes, chapitres et timestamps fournis.\n\n"
    "Réponds UNIQUEMENT avec un objet JSON valide, sans texte autour, au format :\n"
    '{"recipes": [{"name": str, "description": str, "yield_qty": number|null, '
    '"ingredients": [{"name": str, "qty": number|null, "unit": str|null}], '
    '"steps": [str], "prep_time_min": number|null, "cook_time_min": number|null, '
    '"tips": [str], "variants": [str], "allergens": [str], '
    '"start_sec": number|null, "end_sec": number|null, "summary": str}]}\n\n'
    "Règles : noms d'ingrédients en français, courts et génériques. Unités via les "
    "codes g, kg, l, ml, piece. Estime les quantités manquantes de façon "
    "raisonnable (qty=null si impossible). yield_qty = nombre de portions. "
    "start_sec/end_sec = bornes de la recette en secondes si des chapitres ou "
    "timestamps le permettent, sinon null. allergens seulement si détectés. "
    'Chaque recette est INDÉPENDANTE, même si elles partagent des ingrédients. '
    'Si la transcription ne contient aucune recette, renvoie {"recipes": []}.'
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


def _num(v):
    try:
        return float(v) if v is not None and v != "" else None
    except (ValueError, TypeError):
        return None


def _str_list(v):
    return [s.strip() for s in (v or []) if isinstance(s, str) and s.strip()]


def _normalize_one(raw: Dict[str, Any]) -> Dict[str, Any]:
    ingredients: List[Dict[str, Any]] = []
    for ing in raw.get("ingredients") or []:
        if not isinstance(ing, dict):
            continue
        name = (ing.get("name") or "").strip()
        if not name:
            continue
        ingredients.append({
            "name": name,
            "qty": ing.get("qty"),
            "unit": (ing.get("unit") or "").strip().lower() or None,
        })
    return {
        "name": (raw.get("name") or "").strip(),
        "description": (raw.get("description") or "").strip() or None,
        "summary": (raw.get("summary") or "").strip() or None,
        "yield_qty": _num(raw.get("yield_qty")),
        "ingredients": ingredients,
        "steps": _str_list(raw.get("steps")),
        "prep_time_min": _num(raw.get("prep_time_min")),
        "cook_time_min": _num(raw.get("cook_time_min")),
        "tips": _str_list(raw.get("tips")),
        "variants": _str_list(raw.get("variants")),
        "allergens": _str_list(raw.get("allergens")),
        "start_sec": _num(raw.get("start_sec")),
        "end_sec": _num(raw.get("end_sec")),
    }


def _normalize_many(parsed: Any) -> List[Dict[str, Any]]:
    if isinstance(parsed, dict) and isinstance(parsed.get("recipes"), list):
        items = parsed["recipes"]
    elif isinstance(parsed, list):
        items = parsed
    elif isinstance(parsed, dict):
        items = [parsed]  # robustesse : le modèle a renvoyé un objet unique
    else:
        items = []
    out = []
    for it in items:
        if not isinstance(it, dict):
            continue
        r = _normalize_one(it)
        if r["name"] or r["ingredients"]:  # on filtre les recettes vides
            out.append(r)
    return out


def _build_user_message(content: str, hints: Optional[Dict[str, Any]]) -> str:
    hints = hints or {}
    parts = []
    if hints.get("title"):
        parts.append(f"Titre de la vidéo : {hints['title']}")
    if hints.get("chapters"):
        chap = "\n".join(
            f"- {c.get('start_sec')}s : {c.get('title')}" for c in hints["chapters"]
        )
        parts.append("Chapitres :\n" + chap)
    if hints.get("description_timestamps"):
        ts = "\n".join(
            f"- {t.get('sec')}s : {t.get('label')}" for t in hints["description_timestamps"]
        )
        parts.append("Timestamps de la description :\n" + ts)
    parts.append("Transcription :\n" + content)
    return "\n\n".join(parts)


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

    def extract(self, transcript: str, hints: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        cfg = get_ai_config()
        client = self._get_client()
        char_limit = get_video_config().transcript_char_limit
        content = transcript[:char_limit] if char_limit else transcript
        user = _build_user_message(content, hints)
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
        recipes = _normalize_many(_parse_json(text))
        if not recipes:
            raise RecipeExtractionError(
                "La vidéo ne semble pas contenir de recette exploitable."
            )
        return recipes


_extractor: Optional[RecipeExtractor] = None


def get_extractor() -> RecipeExtractor:
    global _extractor
    if _extractor is None:
        _extractor = RecipeExtractor()
    return _extractor
