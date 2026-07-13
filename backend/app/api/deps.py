import os

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt import PyJWTError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core import security
from app.core.rate_limit import get_quota_guard
from app.crud import crud_rbac
from app.models.models import User

# tokenUrl must match the login route so Swagger "Authorize" works
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")

_credentials_exc = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    try:
        payload = security.decode_access_token(token)
    except PyJWTError:
        raise _credentials_exc

    # Refresh tokens must not be usable as access tokens.
    if payload.get("type") == "refresh":
        raise _credentials_exc

    user_id = payload.get("sub")
    if not user_id:
        raise _credentials_exc

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise _credentials_exc

    # Tokens minted before the last logout are dead. Absent claim == 0, so the
    # tokens already in the wild when this shipped keep working.
    if int(payload.get("tv", 0)) != int(user.token_version or 0):
        raise _credentials_exc

    return user


def get_current_tenant_id(current_user: User = Depends(get_current_user)) -> str:
    """Tenant scoping: every request is bound to the caller's organization."""
    if current_user.tenant_id is None:
        raise HTTPException(status_code=403, detail="User has no organization")
    return str(current_user.tenant_id)


def get_current_roles(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list:
    return crud_rbac.get_user_role_names(db, str(current_user.id), str(current_user.tenant_id))


def require_roles(*allowed: str):
    """Dependency factory: 403 unless the caller holds one of ``allowed`` roles."""
    allowed_set = set(allowed)

    def checker(roles: list = Depends(get_current_roles)) -> list:
        if not allowed_set.intersection(roles):
            raise HTTPException(
                status_code=403,
                detail=f"Requires one of roles: {sorted(allowed_set)}",
            )
        return roles

    return checker


# Convenience guard for mutating endpoints.
require_writer = require_roles("admin", "manager")
require_admin = require_roles("admin")


# --------------------------------------------------------------------------- #
# Per-tenant quotas on the endpoints that cost money or CPU
# --------------------------------------------------------------------------- #
def _quota_limit(env_name: str, default: int) -> int:
    try:
        return int(os.getenv(env_name, str(default)))
    except ValueError:
        return default


def quota(bucket: str, env_name: str, default_per_minute: int):
    """Dependency factory: at most N calls per minute, per tenant.

    Applied to the routes that bill a third party (Anthropic, Mistral, OpenAI)
    or burn a worker's CPU. Without it, one scripted account drains the budget
    for everyone — Gunicorn workers are shared across tenants.
    """
    limit = _quota_limit(env_name, default_per_minute)

    def dependency(tenant_id: str = Depends(get_current_tenant_id)) -> None:
        wait = get_quota_guard().check(f"{bucket}:{tenant_id}", limit, 60)
        if wait:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Trop de requêtes ({limit}/min maximum sur cette opération). "
                    f"Réessayez dans {wait} seconde(s)."
                ),
                headers={"Retry-After": str(wait)},
            )

    return dependency


def daily_quota(bucket: str, env_name: str, default_per_day: int):
    """Dependency factory: at most N calls per DAY, per tenant.

    A per-minute ceiling bounds a burst, not a bill. At 30 AI calls/min a single
    tenant could still make 43 200 calls a day — roughly $970 of Anthropic usage,
    for one customer, in one day. The daily cap is what actually bounds the spend
    (and it is the only thing standing between a stolen token and the budget).
    """
    limit = _quota_limit(env_name, default_per_day)

    def dependency(tenant_id: str = Depends(get_current_tenant_id)) -> None:
        wait = get_quota_guard().check(f"{bucket}:daily:{tenant_id}", limit, 86400)
        if wait:
            hours = max(1, wait // 3600)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Quota quotidien atteint ({limit}/jour sur cette opération). "
                    f"Réessayez dans environ {hours} heure(s)."
                ),
                headers={"Retry-After": str(wait)},
            )

    return dependency
