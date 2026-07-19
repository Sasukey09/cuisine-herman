"""Saved assistant threads. Scoped to both the tenant AND the owning user:
an assistant thread is a personal working session (it can hold confidential
costing/strategy questions), so one member must not read or delete another
member's threads within the same organization."""
import uuid
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.models import AIConversation, AIMessage

_TITLE_MAX = 60


def _title_from(message: str) -> str:
    text = " ".join((message or "").split())
    return (text[: _TITLE_MAX - 1] + "…") if len(text) > _TITLE_MAX else (text or "Nouvelle conversation")


def create_conversation(
    db: Session, tenant_id: str, user_id: Optional[str], first_message: str
) -> AIConversation:
    convo = AIConversation(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        user_id=user_id,
        title=_title_from(first_message),
    )
    db.add(convo)
    db.commit()
    db.refresh(convo)
    return convo


def get_conversation(
    db: Session, tenant_id: str, conversation_id: str, user_id: str
) -> Optional[AIConversation]:
    return (
        db.query(AIConversation)
        .filter(
            AIConversation.id == conversation_id,
            AIConversation.tenant_id == tenant_id,
            AIConversation.user_id == user_id,
        )
        .first()
    )


def list_conversations(
    db: Session, tenant_id: str, user_id: str, limit: int = 30
) -> List[AIConversation]:
    return (
        db.query(AIConversation)
        .filter(
            AIConversation.tenant_id == tenant_id,
            AIConversation.user_id == user_id,
        )
        .order_by(AIConversation.updated_at.desc())
        .limit(limit)
        .all()
    )


def list_messages(db: Session, conversation_id: str) -> List[AIMessage]:
    return (
        db.query(AIMessage)
        .filter(AIMessage.conversation_id == conversation_id)
        .order_by(AIMessage.created_at.asc())
        .all()
    )


def add_message(db: Session, conversation_id: str, role: str, content: str) -> AIMessage:
    msg = AIMessage(
        id=str(uuid.uuid4()),
        conversation_id=conversation_id,
        role=role,
        content=content,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


def touch(db: Session, convo: AIConversation) -> None:
    """Bump updated_at so the thread rises to the top of the list."""
    from sqlalchemy import func

    convo.updated_at = func.now()
    db.add(convo)
    db.commit()


def delete_conversation(
    db: Session, tenant_id: str, conversation_id: str, user_id: str
) -> bool:
    convo = get_conversation(db, tenant_id, conversation_id, user_id)
    if convo is None:
        return False
    db.delete(convo)  # messages cascade
    db.commit()
    return True
