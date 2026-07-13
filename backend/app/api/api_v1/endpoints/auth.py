from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.rate_limit import client_ip, get_login_guard
from app.db.session import get_db
from app.schemas.schemas import (
    Token,
    RefreshRequest,
    RegisterRequest,
    CreateUserRequest,
    UserRead,
    MeRead,
)
from app.core import security
from app.crud import crud_user, crud_rbac
from app.api.deps import get_current_user, get_current_roles, require_admin
from app.models.models import User

router = APIRouter()


def _issue_tokens(user: User) -> dict:
    data = {"sub": str(user.id), "tenant_id": str(user.tenant_id)}
    return {
        "access_token": security.create_access_token(data),
        "refresh_token": security.create_refresh_token(data),
        "token_type": "bearer",
    }


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    if crud_user.get_user_by_email(db, payload.email):
        raise HTTPException(status_code=409, detail="Email already registered")
    # First user of a new org bootstraps the organization and becomes admin.
    org = crud_user.create_organization(db, name=payload.org_name)
    roles = crud_rbac.ensure_default_roles(db, str(org.id))
    user = crud_user.create_user(
        db,
        tenant_id=str(org.id),
        email=payload.email,
        password=payload.password,
        name=payload.name,
    )
    crud_rbac.assign_role(db, str(user.id), str(roles["admin"].id))
    return user


@router.post("/token", response_model=Token)
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    guard = get_login_guard()
    ip = client_ip(request)
    email = form_data.username

    wait = guard.retry_after(email, ip)
    if wait > 0:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "Trop de tentatives de connexion échouées. "
                f"Réessayez dans {wait} seconde(s)."
            ),
            headers={"Retry-After": str(wait)},
        )

    user = crud_user.get_user_by_email(db, email)
    # Constant-time: an unknown email must not answer faster than a wrong password.
    password_ok = security.verify_password_constant_time(
        form_data.password, user.password_hash if user else None
    )
    if not user or not password_ok:
        guard.record_failure(email, ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    guard.record_success(email, ip)
    return _issue_tokens(user)


@router.post("/refresh", response_model=Token)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    try:
        claims = security.decode_access_token(payload.refresh_token)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    if claims.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Not a refresh token")
    user = db.query(User).filter(User.id == claims.get("sub")).first()
    if user is None:
        raise HTTPException(status_code=401, detail="User no longer exists")
    return _issue_tokens(user)


@router.get("/me", response_model=MeRead)
def me(
    current_user: User = Depends(get_current_user),
    roles: list = Depends(get_current_roles),
):
    return MeRead(
        id=str(current_user.id),
        email=current_user.email,
        name=current_user.name,
        tenant_id=str(current_user.tenant_id),
        roles=roles,
    )


@router.get("/users", response_model=List[MeRead])
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: list = Depends(require_admin),
):
    """Admin-only: list the organization's users with their roles."""
    tenant_id = str(current_user.tenant_id)
    users = crud_user.list_users(db, tenant_id)
    return [
        MeRead(
            id=str(u.id),
            email=u.email,
            name=u.name,
            tenant_id=tenant_id,
            roles=crud_rbac.get_user_role_names(db, str(u.id), tenant_id),
        )
        for u in users
    ]


@router.get("/roles", response_model=List[str])
def list_roles(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: list = Depends(require_admin),
):
    """Admin-only: available role names for the organization."""
    roles = crud_rbac.ensure_default_roles(db, str(current_user.tenant_id))
    return sorted(roles.keys())


@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: CreateUserRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: list = Depends(require_admin),
):
    """Admin-only: add a user to the caller's organization with a role."""
    if crud_user.get_user_by_email(db, payload.email):
        raise HTTPException(status_code=409, detail="Email already registered")
    roles = crud_rbac.ensure_default_roles(db, str(current_user.tenant_id))
    if payload.role not in roles:
        raise HTTPException(status_code=400, detail=f"Unknown role '{payload.role}'")
    user = crud_user.create_user(
        db,
        tenant_id=str(current_user.tenant_id),
        email=payload.email,
        password=payload.password,
        name=payload.name,
    )
    crud_rbac.assign_role(db, str(user.id), str(roles[payload.role].id))
    return user
