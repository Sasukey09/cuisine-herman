"""Password-reset tokens — creation, validation, single-use consumption.

Security choices (OWASP "Forgot Password"):
* Token = 256 bits of ``secrets.token_urlsafe`` — unguessable, URL-safe.
* Only ``sha256(token)`` is persisted; the plaintext exists solely in the email.
  A dump of ``password_reset_tokens`` therefore yields no usable link.
* Short TTL (default 60 min) and single use (``used_at`` set on redemption).
* Requesting a new link invalidates the user's older unused ones.
"""
import hashlib
import os
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.models.models import PasswordResetToken


def _ttl_minutes() -> int:
    return int(os.getenv("PASSWORD_RESET_TTL_MINUTES", "60"))


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_for_user(db: Session, user_id: str) -> str:
    """Invalidate the user's outstanding links, mint a new one, return its
    PLAINTEXT token (to be emailed — never stored, never logged in prod)."""
    # One live link per user: a new request supersedes older unused tokens.
    now = datetime.utcnow()
    (
        db.query(PasswordResetToken)
        .filter(
            PasswordResetToken.user_id == user_id,
            PasswordResetToken.used_at.is_(None),
        )
        .update({PasswordResetToken.used_at: now}, synchronize_session=False)
    )

    token = secrets.token_urlsafe(32)
    row = PasswordResetToken(
        id=str(uuid.uuid4()),
        user_id=user_id,
        token_hash=hash_token(token),
        expires_at=now + timedelta(minutes=_ttl_minutes()),
    )
    db.add(row)
    db.commit()
    return token


def get_valid(db: Session, token: str) -> Optional[PasswordResetToken]:
    """Return the row for a token that is unused and unexpired, else None."""
    row = (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.token_hash == hash_token(token))
        .first()
    )
    if row is None or row.used_at is not None:
        return None
    if row.expires_at is None or row.expires_at < datetime.utcnow():
        return None
    return row


def mark_used(db: Session, row: PasswordResetToken) -> None:
    row.used_at = datetime.utcnow()
    db.add(row)
    db.commit()
