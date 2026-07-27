"""Video import orchestration.

extract_recipe_from_url/_from_transcript/_from_file: video/transcript → persist
VideoSource + Transcription → Claude extraction → a LIST of editable recipe
candidates + the video's provenance (source). NOT saved as recipes yet;
quantities are estimates to review.

save_candidates: persist the (possibly edited) selected candidates as full
recipes, reusing the PDF-import path's shared builder (``save_import``) so
product-matching and costing behave exactly the same way, while recording
each recipe's provenance and rich fields (description, timings, tips...).
"""
import os
import tempfile
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.url_guard import assert_safe_fetch_url
from app.models.models import VideoSource, Transcription
from . import provenance
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

    candidates = (extractor or get_extractor()).extract(text, hints={"title": filename})
    src = {
        "platform": "upload", "url": None, "video_id": None,
        "title": filename, "creator": None, "thumbnail": None,
    }
    excerpt = text[:600] + ("…" if len(text) > 600 else "")
    return {
        "source_id": str(source.id),
        "platform": "upload",
        "transcript_source": "audio_upload",
        "transcript_excerpt": excerpt,
        "candidates": candidates,
        "source": src,
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

    oembed = provenance.fetch_oembed(url)
    source = provenance.build_source(url, platform, oembed)

    source_row = VideoSource(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        url=url,
        platform=platform,
        fetched_at=datetime.utcnow(),
        meta=source,
    )
    db.add(source_row)
    db.commit()

    text, transcript_source = get_transcript(url, stt_provider=stt_provider)

    db.add(
        Transcription(
            id=str(uuid.uuid4()),
            source_id=str(source_row.id),
            text=text,
            language=None,
        )
    )
    db.commit()

    extractor = extractor or get_extractor()
    candidates = extractor.extract(text, hints={"title": source.get("title")})

    excerpt = text[:600] + ("…" if len(text) > 600 else "")
    return {
        "source_id": str(source_row.id),
        "platform": platform,
        "transcript_source": transcript_source,
        "transcript_excerpt": excerpt,
        "candidates": candidates,
        "source": source,
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

    source = provenance.build_source(
        url or "", "youtube_client", provenance.fetch_oembed(url) if url else {}
    )

    source_row = VideoSource(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        url=(url or "client-transcript")[:2000],
        platform="youtube_client",
        fetched_at=datetime.utcnow(),
    )
    db.add(source_row)
    db.commit()
    db.add(Transcription(id=str(uuid.uuid4()), source_id=str(source_row.id), text=text, language=None))
    db.commit()

    candidates = (extractor or get_extractor()).extract(
        text, hints={"title": title or source.get("title")}
    )
    excerpt = text[:600] + ("…" if len(text) > 600 else "")
    return {
        "source_id": str(source_row.id),
        "platform": "youtube_client",
        "transcript_source": "client_captions",
        "transcript_excerpt": excerpt,
        "candidates": candidates,
        "source": source,
        "note": (
            "Fiche générée depuis les sous-titres de la vidéo : les quantités sont "
            "estimées et doivent être validées avant enregistrement."
        ),
    }


def save_candidates(db, tenant_id, recipes, source):
    """Enregistre chaque recette sélectionnée via le save_import mutualisé,
    en persistant provenance (Recipe.meta['source']) et champs riches
    (RecipeVersion.meta)."""
    from app.services.recipe_import import service as recipe_import_service

    src = source or {}
    vid = src.get("video_id")
    results = []
    for rec in recipes:
        start = rec.get("start_sec")
        deeplink = (
            f"https://youtu.be/{vid}?t={int(start)}" if vid and start is not None
            else (f"https://youtu.be/{vid}" if vid else src.get("url"))
        )
        recipe_meta = {"source": {
            "platform": src.get("platform"), "url": src.get("url"), "video_id": vid,
            "thumbnail": src.get("thumbnail"), "creator": src.get("creator"),
            "start_sec": start, "end_sec": rec.get("end_sec"), "deeplink": deeplink,
        }}
        version_meta_extra = {
            "description": rec.get("description"),
            "prep_time_min": rec.get("prep_time_min"),
            "cook_time_min": rec.get("cook_time_min"),
            "tips": rec.get("tips") or [],
            "variants": rec.get("variants") or [],
            "allergens": rec.get("allergens") or [],
        }
        mapped = [{"name": i.get("name"), "quantity": i.get("qty"),
                   "unit": i.get("unit"), "product_id": i.get("product_id")}
                  for i in (rec.get("ingredients") or [])]
        results.append(recipe_import_service.save_import(
            db, tenant_id, name=(rec.get("name") or "").strip() or "Recette",
            servings=rec.get("yield_qty"), instructions=rec.get("steps") or [],
            ingredients=mapped, imported_from="video",
            recipe_meta=recipe_meta, version_meta_extra=version_meta_extra,
        ))
    return results
