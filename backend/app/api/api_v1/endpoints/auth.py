from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from jwt import PyJWTError
from sqlalchemy.orm import Session

import os

from app.core.rate_limit import client_ip, get_login_guard, get_quota_guard
from app.db.session import get_db
from app.schemas.schemas import (
    Token,
    RefreshRequest,
    RegisterRequest,
    CreateUserRequest,
    ResetPasswordRequest,
    UserRead,
    MeRead,
)
from app.core import security
from app.crud import crud_user, crud_rbac
from app.services.rgpd import service as rgpd
from app.api.deps import get_current_user, get_current_roles, require_admin
from app.models.models import User

router = APIRouter()


def _issue_tokens(user: User) -> dict:
    # `tv` pins the token to the user's current token_version: bumping it on
    # logout invalidates every token already issued, including refresh tokens.
    data = {
        "sub": str(user.id),
        "tenant_id": str(user.tenant_id),
        "tv": int(user.token_version or 0),
    }
    return {
        "access_token": security.create_access_token(data),
        "refresh_token": security.create_refresh_token(data),
        "token_type": "bearer",
    }


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    # Rate-limit account/organization creation per IP: signup is public and
    # self-bootstraps a new org+admin, so it is an abuse vector without a cap.
    # Fail-open on a cache outage (the guard returns 0), like the login guard.
    limit = int(os.getenv("REGISTER_PER_HOUR", "5"))
    wait = get_quota_guard().check(f"register:{client_ip(request)}", limit, 3600)
    if wait:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Trop de créations de compte depuis cette adresse "
                f"({limit}/heure maximum). Réessayez dans {wait} seconde(s)."
            ),
            headers={"Retry-After": str(wait)},
        )
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
    # Normaliser comme a l'inscription (strip + lowercase) : l'email est stocke
    # en minuscules au signup, donc un login tape avec une casse/espace differents
    # (frequent sur iOS) ne matcherait jamais -> "identifiants incorrects" alors
    # que l'inscription repond "email deja utilise". Meme normalisation des 2 cotes.
    email = security.normalize_email(form_data.username)

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
    rgpd.record(db, str(user.tenant_id), str(user.id), rgpd.ACTION_LOGIN, {"ip": ip})
    return _issue_tokens(user)


@router.post("/refresh", response_model=Token)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    try:
        claims = security.decode_access_token(payload.refresh_token)
    except PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    if claims.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Not a refresh token")
    user = db.query(User).filter(User.id == claims.get("sub")).first()
    if user is None:
        raise HTTPException(status_code=401, detail="User no longer exists")
    # A refresh token issued before a logout must not mint anything.
    if int(claims.get("tv", 0)) != int(user.token_version or 0):
        raise HTTPException(status_code=401, detail="Session révoquée")
    return _issue_tokens(user)


@router.post("/logout", status_code=204)
def logout(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Revoke every token of the caller — access AND refresh, on every device.

    Logging out used to be a purely client-side `setState(null)`: a refresh
    token captured beforehand kept minting access tokens for 14 days, with no
    way for anyone to cut it off short of rotating SECRET_KEY (which would log
    out every customer).
    """
    current_user.token_version = int(current_user.token_version or 0) + 1
    db.add(current_user)
    db.commit()
    rgpd.record(db, str(current_user.tenant_id), str(current_user.id), rgpd.ACTION_LOGOUT)


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
    rgpd.record(
        db, str(current_user.tenant_id), str(current_user.id), rgpd.ACTION_USER_CREATED,
        {"created_user": payload.email, "role": payload.role},
    )
    return user


@router.post("/users/{user_id}/reset-password", status_code=204)
def reset_user_password(
    user_id: str,
    payload: ResetPasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: list = Depends(require_admin),
):
    """Admin-only: set a new password for a user of the caller's organization.

    There is no email-based reset (no mail provider), and the "mot de passe
    oublié" screen used to *pretend* one had been sent. This makes the honest
    answer — "ask your administrator" — an actual way out instead of a dead end.

    Bumping token_version logs the user out everywhere: whoever knew the old
    password (or held a stolen token) is cut off immediately.
    """
    # Validate the input before touching the database: a weak password is
    # rejected whether or not the user exists (which also avoids confirming that
    # an id exists, and keeps the check free of a query). Same policy as register.
    pw_err = security.password_error(payload.password)
    if pw_err:
        raise HTTPException(status_code=400, detail=pw_err)

    target = (
        db.query(User)
        .filter(User.id == user_id, User.tenant_id == current_user.tenant_id)
        .first()
    )
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")

    target.password_hash = security.get_password_hash(payload.password)
    target.token_version = int(target.token_version or 0) + 1
    db.add(target)
    db.commit()
    rgpd.record(
        db, str(current_user.tenant_id), str(current_user.id), rgpd.ACTION_PASSWORD_RESET,
        {"target_user": target.email},
    )
