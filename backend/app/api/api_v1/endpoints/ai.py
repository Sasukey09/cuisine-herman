from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_current_tenant_id, require_writer, quota, daily_quota
from app.schemas.schemas import AIChatRequest, AIChatResponse
from app.services.ai.assistant import get_assistant
from app.services.ai.errors import AINotConfiguredError, AIProviderError

router = APIRouter()

_AI_UNAVAILABLE = (
    "Assistant IA indisponible : aucune clé API LLM n'est configurée "
    "(ANTHROPIC_API_KEY)."
)


# Each call bills Anthropic. Without a ceiling, one scripted account drains the
# budget — and the tokens are not the caller's to spend.
MAX_MESSAGE_CHARS = 4000
MAX_HISTORY_TURNS = 40


@router.post("/chat", response_model=AIChatResponse)
def api_ai_chat(
    payload: AIChatRequest,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    _: list = Depends(require_writer),
    _q: None = Depends(quota("ai", "AI_CHAT_PER_MIN", 30)),
    _qd: None = Depends(daily_quota("ai", "AI_CHAT_PER_DAY", 300)),
):
    """Ask the AI assistant a question. It reads the tenant's own data via
    tenant-scoped tools (recipes, costs, products, prices, alerts)."""
    if not payload.message or not payload.message.strip():
        raise HTTPException(status_code=400, detail="Message vide")
    if len(payload.message) > MAX_MESSAGE_CHARS:
        raise HTTPException(
            status_code=413,
            detail=f"Message trop long ({MAX_MESSAGE_CHARS} caractères maximum).",
        )
    if len(payload.history) > MAX_HISTORY_TURNS:
        raise HTTPException(
            status_code=413,
            detail=f"Conversation trop longue ({MAX_HISTORY_TURNS} messages maximum).",
        )
    assistant = get_assistant()
    history = [{"role": m.role, "content": m.content} for m in payload.history]
    try:
        return assistant.chat(db, tenant_id, payload.message, history)
    except AINotConfiguredError:
        raise HTTPException(status_code=503, detail=_AI_UNAVAILABLE)
    except AIProviderError as exc:
        raise HTTPException(status_code=502, detail=f"Erreur du fournisseur IA : {exc}")
