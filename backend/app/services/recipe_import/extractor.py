"""Turn OCR text from a recipe PDF into a structured recipe draft, using Claude.

Returns: {name, yield_qty, ingredients: [{name, qty, unit}], steps, summary}

The JSON parsing/normalisation helpers are shared with the video importer so both
paths behave identically; only the system prompt differs (document vs. video
transcript). The Anthropic client is injectable for tests.
"""
from typing import Any, Dict, Optional

from app.services.ai.config import get_ai_config
# Reuse the robust JSON extraction + draft normalisation from the video importer.
from app.services.video.extractor import _parse_json, _normalize
from .errors import RecipeExtractionError

# Documents (unlike a spoken transcript) usually have explicit quantities, so the
# prompt tells the model to read them rather than estimate.
SYSTEM_PROMPT = (
    "Tu extrais une fiche recette structurée à partir du TEXTE d'un document de "
    "cuisine (PDF de recette, fiche technique, livre). Réponds UNIQUEMENT avec un "
    "objet JSON valide, sans texte autour, au format exact :\n"
    '{"name": str, "yield_qty": number, "ingredients": [{"name": str, '
    '"qty": number|null, "unit": str|null}], "steps": [str], "summary": str}\n\n'
    "Règles : noms d'ingrédients en français, courts et génériques (ex. 'tomate', "
    "'mozzarella', 'farine') — retire les marques et les mentions de préparation "
    "(ex. 'mozzarella râpée' -> 'mozzarella'). Unités via les codes g, kg, l, ml, "
    "cl, piece. Reprends FIDÈLEMENT les quantités écrites dans le document ; "
    "n'estime (qty=null) que si une quantité est réellement absente. yield_qty = "
    "nombre de portions/parts (lis 'pour 4 personnes' etc., sinon estime). steps = "
    "les étapes de préparation, dans l'ordre, concises. Si le texte n'est pas une "
    'recette, renvoie {"name": "", "ingredients": []}.'
)

DEFAULT_CHAR_LIMIT = 24000


class RecipeDocumentExtractor:
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

    def extract(self, text: str, hint_title: Optional[str] = None) -> Dict[str, Any]:
        cfg = get_ai_config()
        client = self._get_client()
        content = (text or "")[:DEFAULT_CHAR_LIMIT]
        user = (
            (f"Titre/nom du fichier : {hint_title}\n\n" if hint_title else "")
            + "Texte du document :\n"
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

        raw = ""
        for block in getattr(resp, "content", []) or []:
            if getattr(block, "type", None) == "text":
                raw += getattr(block, "text", "")
        draft = _normalize(_parse_json(raw))
        if not draft["name"] and not draft["ingredients"]:
            raise RecipeExtractionError(
                "Le document ne semble pas contenir de recette exploitable."
            )
        return draft


_extractor: Optional[RecipeDocumentExtractor] = None


def get_extractor() -> RecipeDocumentExtractor:
    global _extractor
    if _extractor is None:
        _extractor = RecipeDocumentExtractor()
    return _extractor
