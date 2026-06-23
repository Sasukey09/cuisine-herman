from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_current_tenant_id, require_writer
from app.schemas.schemas import (
    VideoExtractRequest,
    VideoExtractResult,
    VideoSaveRequest,
)
from app.services.video import service as video_service
from app.services.video.errors import (
    UnsupportedURLError,
    TranscriptUnavailableError,
    STTNotConfiguredError,
    VideoTooLongError,
    AudioDownloadError,
    RecipeExtractionError,
    VideoError,
)

router = APIRouter()


@router.post("/extract", response_model=VideoExtractResult)
def api_video_extract(
    payload: VideoExtractRequest,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    _: list = Depends(require_writer),
):
    """Paste a video URL → transcript → AI-extracted, editable recipe draft.

    The draft is NOT saved; quantities are estimates to review before saving.
    """
    url = (payload.url or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="URL vide")
    try:
        return video_service.extract_recipe_from_url(db, tenant_id, url)
    except UnsupportedURLError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except STTNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except VideoTooLongError as exc:
        raise HTTPException(status_code=413, detail=str(exc))
    except (TranscriptUnavailableError, AudioDownloadError) as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except RecipeExtractionError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except VideoError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/extract-file", response_model=VideoExtractResult)
async def api_video_extract_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    _: list = Depends(require_writer),
):
    """Upload a video/audio file → audio (ffmpeg) → Whisper → editable recipe
    draft. Reliable alternative to URL import (no YouTube IP blocking)."""
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Fichier vide")
    if len(content) > 300 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Fichier trop volumineux (max 300 Mo).")
    try:
        return video_service.extract_recipe_from_file(
            db, tenant_id, content, file.filename, file.content_type
        )
    except STTNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except VideoTooLongError as exc:
        raise HTTPException(status_code=413, detail=str(exc))
    except AudioDownloadError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except RecipeExtractionError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except VideoError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/save")
def api_video_save(
    payload: VideoSaveRequest,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    _: list = Depends(require_writer),
):
    """Persist a (reviewed/edited) draft as a recipe and compute its cost."""
    if not payload.name.strip():
        raise HTTPException(status_code=400, detail="Nom de recette requis")
    ingredients = [i.dict() for i in payload.ingredients]
    return video_service.save_draft(
        db, tenant_id, payload.name.strip(), payload.yield_qty, ingredients,
        instructions=payload.steps,
    )
