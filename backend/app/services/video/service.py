"""Video import orchestration.

extract_recipe_from_url: URL → transcript (captions or STT) → persist
VideoSource + Transcription → Claude extraction → editable draft (NOT saved as a
recipe; quantities are estimates to review).

save_draft: persist a (possibly edited) draft as a recipe + cost it, reusing the
AI module's ``create_recipe_draft`` tool so product-matching and costing behave
exactly like the chat assistant.
"""
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.models import VideoSource, Transcription
from app.services.ai import tools as ai_tools
from .platforms import detect_platform
from .transcript import get_transcript
from .extractor import get_extractor


def extract_recipe_from_url(
    db: Session,
    tenant_id: str,
    url: str,
    stt_provider: Any = None,
    extractor: Any = None,
) -> Dict[str, Any]:
    platform = detect_platform(url)

    source = VideoSource(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        url=url,
        platform=platform,
        fetched_at=datetime.utcnow(),
    )
    db.add(source)
    db.commit()

    text, transcript_source = get_transcript(url, stt_provider=stt_provider)

    db.add(
        Transcription(
            id=str(uuid.uuid4()),
            source_id=str(source.id),
            text=text,
            language=None,
        )
    )
    db.commit()

    extractor = extractor or get_extractor()
    draft = extractor.extract(text)

    excerpt = text[:600] + ("…" if len(text) > 600 else "")
    return {
        "source_id": str(source.id),
        "platform": platform,
        "transcript_source": transcript_source,
        "transcript_excerpt": excerpt,
        "draft": draft,
        "note": (
            "Fiche générée automatiquement : les quantités sont estimées et "
            "doivent être validées avant enregistrement."
        ),
    }


def save_draft(
    db: Session,
    tenant_id: str,
    name: str,
    yield_qty: Optional[float],
    ingredients: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Persist an (edited) draft as a recipe + compute cost (reuses create_recipe_draft)."""
    payload = {
        "name": name,
        "yield_qty": yield_qty or 1,
        "ingredients": ingredients,
    }
    return ai_tools.execute_tool(db, tenant_id, "create_recipe_draft", payload)
