import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core.logging import get_logger, log_event
from app.db.session import get_db
from app.api.deps import (
    daily_quota,
    get_current_tenant_id,
    get_current_user,
    quota,
    require_writer,
)
from app.crud import crud_ai_conversation
from app.models.models import User
from app.schemas.schemas import (
    AIChatRequest,
    AIChatResponse,
    AIConversationDetail,
    AIConversationRead,
    AISuggestions,
)
from app.services.ai import context as ai_context
from app.services.ai.assistant import get_assistant
from app.services.ai.errors import AINotConfiguredError, AIProviderError

router = APIRouter()
logger = get_logger("ai.endpoint")

_AI_UNAVAILABLE = (
    "Assistant IA indisponible : aucune clé API LLM n'est configurée "
    "(ANTHROPIC_API_KEY)."
)
# Shown to the user when the LLM provider call fails. Deliberately generic: the
# raw provider payload (which can contain a 400 body, model ids, internal
# messages) is written to the logs, never returned to the client.
_AI_PROVIDER_ERROR = (
    "L'assistant IA a rencontré un problème et n'a pas pu répondre. "
    "Réessayez dans un instant."
)

# Each call bills Anthropic. Without a ceiling, one scripted account drains the
# budget — and the tokens are not the caller's to spend.
MAX_MESSAGE_CHARS = 4000
# How much of a saved thread is replayed to the model. Old turns cost input
# tokens on every message; the whole thread stays readable in the UI regardless.
CONTEXT_TURNS = 20


@router.get("/suggestions", response_model=AISuggestions)
def api_ai_suggestions(
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Questions worth asking *for this restaurant*.

    The chat used to offer the same three canned prompts to everybody, whether
    or not they meant anything for that tenant's data.
    """
    situation = ai_context.build_situation(db, tenant_id)
    return {"suggestions": ai_context.suggestions(situation)}


@router.get("/conversations", response_model=List[AIConversationRead])
def api_list_conversations(
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
):
    return crud_ai_conversation.list_conversations(db, tenant_id, str(current_user.id))


@router.get("/conversations/{conversation_id}", response_model=AIConversationDetail)
def api_get_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
):
    convo = crud_ai_conversation.get_conversation(
        db, tenant_id, conversation_id, str(current_user.id)
    )
    if convo is None:
        raise HTTPException(status_code=404, detail="Conversation introuvable")
    messages = crud_ai_conversation.list_messages(db, conversation_id)
    return {
        "id": str(convo.id),
        "title": convo.title,
        "updated_at": convo.updated_at,
        "messages": [
            {"role": m.role, "content": m.content, "created_at": m.created_at} for m in messages
        ],
    }


@router.delete("/conversations/{conversation_id}", status_code=204)
def api_delete_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _: list = Depends(require_writer),
):
    if not crud_ai_conversation.delete_conversation(
        db, tenant_id, conversation_id, str(current_user.id)
    ):
        raise HTTPException(status_code=404, detail="Conversation introuvable")


@router.post("/chat", response_model=AIChatResponse)
async def api_ai_chat(
    payload: AIChatRequest,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _: list = Depends(require_writer),
    _q: None = Depends(quota("ai", "AI_CHAT_PER_MIN", 30)),
    _qd: None = Depends(daily_quota("ai", "AI_CHAT_PER_DAY", 300)),
):
    """Ask the assistant. The thread is persisted, so a reload no longer erases it.

    Pass ``conversation_id`` to continue a thread; omit it to start a new one.
    History is read from the database rather than from the request body: the
    client's copy used to be the only source of truth, so a reload lost it — and
    a crafted request could rewrite what the model believed had been said.
    """
    if not payload.message or not payload.message.strip():
        raise HTTPException(status_code=400, detail="Message vide")
    if len(payload.message) > MAX_MESSAGE_CHARS:
        raise HTTPException(
            status_code=413,
            detail=f"Message trop long ({MAX_MESSAGE_CHARS} caractères maximum).",
        )

    message = payload.message.strip()

    def _work():
        if payload.conversation_id:
            convo = crud_ai_conversation.get_conversation(
                db, tenant_id, payload.conversation_id, str(current_user.id)
            )
            if convo is None:
                raise HTTPException(status_code=404, detail="Conversation introuvable")
        else:
            convo = crud_ai_conversation.create_conversation(
                db, tenant_id, str(current_user.id), message
            )

        stored = crud_ai_conversation.list_messages(db, str(convo.id))
        history = [{"role": m.role, "content": m.content} for m in stored][-CONTEXT_TURNS:]

        crud_ai_conversation.add_message(db, str(convo.id), "user", message)

        result = get_assistant().chat(db, tenant_id, message, history)

        reply = result.get("reply") or ""
        if reply:
            crud_ai_conversation.add_message(db, str(convo.id), "assistant", reply)
        crud_ai_conversation.touch(db, convo)

        result["conversation_id"] = str(convo.id)
        return result

    try:
        # The model call is a blocking network round trip of several seconds: from
        # an `async def` it would freeze the worker's event loop for every other
        # tenant (the Phase 4 lesson).
        return await run_in_threadpool(_work)
    except AINotConfiguredError:
        raise HTTPException(status_code=503, detail=_AI_UNAVAILABLE)
    except AIProviderError as exc:
        # Log the full provider detail for diagnosis; return a clean, generic
        # message so the raw API JSON never reaches the interface.
        log_event(
            logger, logging.ERROR, "ai.chat.provider_error",
            tenant=tenant_id, detail=str(exc)[:500],
        )
        raise HTTPException(status_code=502, detail=_AI_PROVIDER_ERROR)
