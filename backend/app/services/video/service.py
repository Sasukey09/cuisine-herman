"""Video import orchestration.

extract_recipe_from_url: URL → transcript (captions or STT) → persist
VideoSource + Transcription → Claude extraction → editable draft (NOT saved as a
recipe; quantities are estimates to review).

save_draft: persist a (possibly edited) draft as a recipe + cost it, reusing the
AI module's ``create_recipe_draft`` tool so product-matching and costing behave
exactly like the chat assistant.
"""
import os
import tempfile
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.url_guard import assert_safe_fetch_url
from app.models.models import VideoSource, Transcription
from .platforms import detect_platform
from .transcript import get_transcript
from .extractor import get_extractor
from .config import get_video_config
from .errors import STTNotConfiguredError, VideoTooLongError, TranscriptUnavailableError

# Whisper rejects audio files larger than 25MB; our transcode stays well below.
_MAX_AUDIO_BYTES = 24 * 1024 * 1024


def extract_recipe_from_file(
    db: Session,
    tenant_id: str,
    file_bytes: bytes,
    filename: Optional[str],
    content_type: Optional[str] = None,
    stt_provider: Any = None,
    extractor: Any = None,
) -> Dict[str, Any]:
    """Upload a video/audio FILE → ffmpeg audio → Whisper STT → editable draft.

    Bypasses YouTube entirely (no datacenter-IP blocking). Needs OPENAI_API_KEY.
    """
    from .audio import transcode_to_mp3
    from .stt.openai_stt import OpenAISTTProvider

    provider = stt_provider or OpenAISTTProvider()
    if not provider.is_configured():
        raise STTNotConfiguredError(
            "La transcription audio n'est pas configurée (OPENAI_API_KEY manquante)."
        )

    source = VideoSource(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        url=filename or "upload",
        platform="upload",
        fetched_at=datetime.utcnow(),
    )
    db.add(source)
    db.commit()

    suffix = os.path.splitext(filename or "")[1] or ".bin"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    audio_path = None
    try:
        tmp.write(file_bytes)
        tmp.close()
        audio_path = transcode_to_mp3(tmp.name)
        if os.path.getsize(audio_path) > _MAX_AUDIO_BYTES:
            raise VideoTooLongError(
                "Vidéo trop longue pour la transcription (~50 min max). Découpez-la."
            )
        text = provider.transcribe(audio_path)
    finally:
        for p in (tmp.name, audio_path):
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass

    db.add(Transcription(id=str(uuid.uuid4()), source_id=str(source.id), text=text, language=None))
    db.commit()

    draft = (extractor or get_extractor()).extract(text, hint_title=filename)
    excerpt = text[:600] + ("…" if len(text) > 600 else "")
    return {
        "source_id": str(source.id),
        "platform": "upload",
        "transcript_source": "audio_upload",
        "transcript_excerpt": excerpt,
        "draft": draft,
        "note": (
            "Fiche générée depuis le fichier vidéo : vérifiez les quantités et la "
            "procédure avant d'enregistrer."
        ),
    }


def extract_recipe_from_url(
    db: Session,
    tenant_id: str,
    url: str,
    stt_provider: Any = None,
    extractor: Any = None,
) -> Dict[str, Any]:
    # SSRF: everything below hands this URL to yt-dlp / an HTTP fetch. Refuse
    # anything that is not a supported public video host BEFORE touching the
    # network — otherwise a caller can make the server read cloud metadata or
    # an internal service and hand the body back.
    assert_safe_fetch_url(url)

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


def extract_recipe_from_transcript(
    db: Session,
    tenant_id: str,
    transcript: str,
    url: Optional[str] = None,
    title: Optional[str] = None,
    extractor: Any = None,
) -> Dict[str, Any]:
    """Extract a recipe from a transcript the CLIENT already fetched.

    The mobile app pulls the YouTube captions from the phone's residential IP —
    which YouTube does not bot-block like Render's datacenter IP — and posts the
    text here. We never fetch YouTube server-side on this path, so there is no
    SSRF surface and no datacenter-IP block: only the AI extraction runs.
    """
    text = (transcript or "").strip()
    if not text:
        raise TranscriptUnavailableError("Transcript vide.")
    limit = get_video_config().transcript_char_limit
    if len(text) > limit:
        text = text[:limit]

    source = VideoSource(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        url=(url or "client-transcript")[:2000],
        platform="youtube_client",
        fetched_at=datetime.utcnow(),
    )
    db.add(source)
    db.commit()
    db.add(Transcription(id=str(uuid.uuid4()), source_id=str(source.id), text=text, language=None))
    db.commit()

    draft = (extractor or get_extractor()).extract(text, hint_title=title)
    excerpt = text[:600] + ("…" if len(text) > 600 else "")
    return {
        "source_id": str(source.id),
        "platform": "youtube_client",
        "transcript_source": "client_captions",
        "transcript_excerpt": excerpt,
        "draft": draft,
        "note": (
            "Fiche générée depuis les sous-titres de la vidéo : les quantités sont "
            "estimées et doivent être validées avant enregistrement."
        ),
    }


def save_draft(
    db: Session,
    tenant_id: str,
    name: str,
    yield_qty: Optional[float],
    ingredients: List[Dict[str, Any]],
    instructions: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Persist an (edited) draft as a FULL recipe (ingredients + procedure + cost).

    Routes through the shared recipe-import builder so a video recipe is saved
    exactly like a manual / PDF one — nothing extracted by the AI is dropped.
    """
    from app.services.recipe_import import service as recipe_import_service

    mapped = [
        {
            "name": ing.get("name"),
            "quantity": ing.get("qty"),
            "unit": ing.get("unit"),
            "product_id": ing.get("product_id"),
        }
        for ing in (ingredients or [])
    ]
    return recipe_import_service.save_import(
        db,
        tenant_id,
        name=name,
        servings=yield_qty,
        instructions=instructions or [],
        ingredients=mapped,
    )
