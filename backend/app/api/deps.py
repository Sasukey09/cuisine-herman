from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core import security
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
    except JWTError:
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
