import os
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


def _load_secret_key() -> str:
    secret = os.getenv("SECRET_KEY", "").strip()
    if secret.lower() not in _PLACEHOLDER_SECRETS:
        return secret
    if _UNDER_PYTEST:
        return "pytest-only-secret-never-used-by-a-deployment"
    raise RuntimeError(
        "SECRET_KEY is unset or still a placeholder, so every JWT this process "
        "issued could be forged by anyone. Refusing to start.\n"
        "Generate one with:\n"
        '    python -c "import secrets; print(secrets.token_urlsafe(48))"\n'
        "then set SECRET_KEY in the environment (Render dashboard, .env, or "
        "docker-compose)."
    )


SECRET_KEY = _load_secret_key()
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
REFRESH_TOKEN_EXPIRE_MINUTES = int(os.getenv("REFRESH_TOKEN_EXPIRE_MINUTES", str(60 * 24 * 14)))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: Optional[str]) -> bool:
    if not hashed_password:
        return False
    return pwd_context.verify(plain_password, hashed_password)


@lru_cache(maxsize=1)
def _dummy_hash() -> str:
    return get_password_hash("cuisine-herman-nonexistent-account")


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
