from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_current_tenant_id, require_writer
from app.schemas.schemas import AIChatRequest, AIChatResponse
from app.services.ai.assistant import get_assistant
from app.services.ai.errors import AINotConfiguredError, AIProviderError

router = APIRouter()

_AI_UNAVAILABLE = (
    "Assistant IA indisponible : aucune clé API LLM n'est configurée "
    "(ANTHROPIC_API_KEY)."
)


@router.post("/chat", response_model=AIChatResponse)
def api_ai_chat(
    payload: AIChatRequest,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    _: list = Depends(require_writer),
):
    """Ask the AI assistant a question. It reads the tenant's own data via
    tenant-scoped tools (recipes, costs, products, prices, alerts)."""
    if not payload.message or not payload.message.strip():
        raise HTTPException(status_code=400, detail="Message vide")
    assistant = get_assistant()
    history = [{"role": m.role, "content": m.content} for m in payload.history]
    try:
        return assistant.chat(db, tenant_id, payload.message, history)
    except AINotConfiguredError:
        raise HTTPException(status_code=503, detail=_AI_UNAVAILABLE)
    except AIProviderError as exc:
        raise HTTPException(status_code=502, detail=f"Erreur du fournisseur IA : {exc}")
