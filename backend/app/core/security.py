import os
import re
import sys
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Optional

import jwt  # PyJWT — replaces python-jose (CVE-2024-33663, unmaintained)
from passlib.context import CryptContext

ALGORITHM = "HS256"

# A JWT signed with any of these is forgeable by anyone who reads the source.
_PLACEHOLDER_SECRETS = {
    "",
    "changeme",
    "change_me",
    "change_me_for_prod",
    "change_me_strong_random",
    "changethis",
    "secret",
}

_UNDER_PYTEST = "PYTEST_CURRENT_TEST" in os.environ or "pytest" in sys.modules

# A captured HS256 token lets an attacker brute-force a short signing key
# offline, then forge tokens for any user. Require real entropy in a deployment.
_MIN_SECRET_KEY_LEN = 32


def _resolve_secret_key(secret: str, under_pytest: bool) -> str:
    secret = (secret or "").strip()
    if secret.lower() in _PLACEHOLDER_SECRETS:
        if under_pytest:
            return "pytest-only-secret-never-used-by-a-deployment"
        raise RuntimeError(
            "SECRET_KEY is unset or still a placeholder, so every JWT this "
            "process issued could be forged by anyone. Refusing to start.\n"
            "Generate one with:\n"
            '    python -c "import secrets; print(secrets.token_urlsafe(48))"\n'
            "then set SECRET_KEY in the environment (Render dashboard, .env, or "
            "docker-compose)."
        )
    if not under_pytest and len(secret) < _MIN_SECRET_KEY_LEN:
        raise RuntimeError(
            f"SECRET_KEY is too short (min {_MIN_SECRET_KEY_LEN} chars) to resist "
            "an offline brute-force of the HS256 signing key. Refusing to start.\n"
            "Generate one with:\n"
            '    python -c "import secrets; print(secrets.token_urlsafe(48))"'
        )
    return secret


def _load_secret_key() -> str:
    return _resolve_secret_key(os.getenv("SECRET_KEY", ""), _UNDER_PYTEST)


SECRET_KEY = _load_secret_key()
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
REFRESH_TOKEN_EXPIRE_MINUTES = int(os.getenv("REFRESH_TOKEN_EXPIRE_MINUTES", str(60 * 24 * 14)))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# --- Input hardening (I2) --------------------------------------------------- #
# Applied at registration and admin user-creation (and password reset). Kept as
# plain helpers (no external email-validator dependency) so schemas and endpoints
# share one policy.
PASSWORD_MIN_LENGTH = 8
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_email(email: Optional[str]) -> str:
    return (email or "").strip().lower()


def email_error(email: Optional[str]) -> Optional[str]:
    """Return an error message when the email is not a plausible address, else None."""
    if not _EMAIL_RE.match(normalize_email(email)):
        return "Adresse e-mail invalide."
    return None


def password_error(password: Optional[str]) -> Optional[str]:
    """Return an error message when the password is too weak, else None.

    Policy: at least 8 characters, with at least one letter and one digit. Strong
    enough to stop empty/1-char passwords from undermining every downstream auth
    control, without being draconian.
    """
    pw = password or ""
    if len(pw) < PASSWORD_MIN_LENGTH:
        return f"Le mot de passe doit contenir au moins {PASSWORD_MIN_LENGTH} caractères."
    if not any(c.isalpha() for c in pw) or not any(c.isdigit() for c in pw):
        return "Le mot de passe doit contenir au moins une lettre et un chiffre."
    return None


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: Optional[str]) -> bool:
    if not hashed_password:
        return False
    return pwd_context.verify(plain_password, hashed_password)


@lru_cache(maxsize=1)
def _dummy_hash() -> str:
    return get_password_hash("foodgad-nonexistent-account")


def verify_password_constant_time(plain_password: str, hashed_password: Optional[str]) -> bool:
    """Same as :func:`verify_password`, but always pays the bcrypt cost.

    Without this, "unknown email" answers in ~1 ms while "wrong password" takes
    ~100 ms, which is enough to enumerate who has an account.
    """
    if not hashed_password:
        pwd_context.verify(plain_password, _dummy_hash())
        return False
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=REFRESH_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Decode and verify a JWT. Raises ``jwt.PyJWTError`` on failure.

    ``algorithms`` is pinned, so a token claiming ``alg: none`` or an asymmetric
    algorithm is rejected rather than trusted (algorithm confusion). ``exp`` is
    verified by PyJWT itself.
    """
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
