"""Social login find-or-create logic, against a real PostgreSQL (JSONB query +
org/user creation + RBAC). Skips when no DATABASE_URL is set."""
import uuid

import pytest
from fastapi import HTTPException

from app.api.api_v1.endpoints.auth import _social_login_or_create
from app.services.social_auth import SocialIdentity
from app.crud import crud_user, crud_rbac
from app.models.models import Organization, User


def _delete_org_of(db, user_id):
    u = db.query(User).filter(User.id == user_id).first()
    if u:
        org = db.query(Organization).filter(Organization.id == u.tenant_id).first()
        if org:
            db.delete(org)
            db.commit()


def test_google_creates_passwordless_account_then_logs_in_by_subject(db):
    sub = f"gsub-{uuid.uuid4()}"
    email = f"soc-{uuid.uuid4().hex[:8]}@ex.test"
    ident = SocialIdentity("google", sub, email, True, "Soc One")
    u1 = _social_login_or_create(db, ident, org_name="Resto Social")
    try:
        assert u1.password_hash is None, "a social account must have no password"
        assert (u1.meta or {}).get("providers", {}).get("google") == sub
        # A returning Apple-style token (no email) must resolve by subject, not
        # create a duplicate.
        u2 = _social_login_or_create(db, SocialIdentity("google", sub, None, False, None), None)
        assert u2.id == u1.id
    finally:
        _delete_org_of(db, u1.id)


def test_social_links_to_an_existing_email_account(db):
    org = crud_user.create_organization(db, name="Existing Resto")
    crud_rbac.ensure_default_roles(db, str(org.id))
    email = f"link-{uuid.uuid4().hex[:8]}@ex.test"
    existing = crud_user.create_user(
        db, tenant_id=str(org.id), email=email, password="motdepasse1", name="Existing"
    )
    try:
        ident = SocialIdentity("google", f"gsub-{uuid.uuid4()}", email, True, "Existing")
        u = _social_login_or_create(db, ident, None)
        assert u.id == existing.id, "must link, not create a second account"
        assert u.password_hash is not None, "existing password must be preserved"
        assert (u.meta or {}).get("providers", {}).get("google") == ident.subject
    finally:
        db.delete(db.query(Organization).filter(Organization.id == org.id).first())
        db.commit()


def test_social_rejects_missing_or_unverified_email(db):
    # No email at all, no prior link -> cannot create.
    with pytest.raises(HTTPException):
        _social_login_or_create(db, SocialIdentity("apple", "sub-x", None, False, None), None)
    # Email present but NOT verified -> refuse (prevents account takeover).
    with pytest.raises(HTTPException):
        _social_login_or_create(db, SocialIdentity("apple", "sub-y", "u@x.test", False, None), None)
