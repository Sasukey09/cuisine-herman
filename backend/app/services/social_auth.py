"""Verify Google / Apple identity tokens WITHOUT Firebase.

The mobile/web client performs the native Sign-in flow and obtains a signed
identity token (a JWT). It sends that token here; we verify it against the
provider's published public keys (JWKS), check issuer/audience/expiry, and read
the trusted email + subject. The backend then issues its OWN JWT (see auth.py),
so the existing multi-tenant / RBAC model is untouched.

No client secret is needed to VERIFY an identity token — only the provider's
public keys and the expected audience (our OAuth client id / bundle id).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Optional

import jwt
from jwt import PyJWKClient

from app.core.security import normalize_email

GOOGLE_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}
GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
APPLE_ISSUER = "https://appleid.apple.com"
APPLE_JWKS_URL = "https://appleid.apple.com/auth/keys"


class SocialAuthError(Exception):
    """Token could not be verified (bad signature/issuer/audience/expiry)."""


class SocialAuthNotConfigured(Exception):
    """No accepted audience configured for this provider (feature off)."""


@dataclass
class SocialIdentity:
    provider: str          # "google" | "apple"
    subject: str           # stable per-user id from the provider (sub)
    email: Optional[str]   # normalized; may be a private-relay address for Apple
    email_verified: bool
    name: Optional[str]


def _audiences(env_var: str) -> List[str]:
    raw = os.getenv(env_var, "")
    auds = [a.strip() for a in raw.split(",") if a.strip()]
    return auds


# PyJWKClient caches keys per URL, so we keep one client per provider process-wide.
_jwk_clients: dict[str, PyJWKClient] = {}


def _jwk_client(url: str) -> PyJWKClient:
    client = _jwk_clients.get(url)
    if client is None:
        client = PyJWKClient(url, cache_keys=True)
        _jwk_clients[url] = client
    return client


def _verify(token: str, jwks_url: str, issuers: set[str], audiences: List[str]) -> dict:
    if not audiences:
        raise SocialAuthNotConfigured()
    try:
        signing_key = _jwk_client(jwks_url).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=audiences,
            options={"require": ["exp", "iat", "sub"]},
        )
    except SocialAuthNotConfigured:
        raise
    except Exception as exc:  # signature, expiry, audience, malformed…
        raise SocialAuthError(str(exc)) from exc
    if claims.get("iss") not in issuers:
        raise SocialAuthError(f"issuer inattendu: {claims.get('iss')}")
    return claims


def verify_google(id_token: str) -> SocialIdentity:
    claims = _verify(id_token, GOOGLE_JWKS_URL, GOOGLE_ISSUERS, _audiences("GOOGLE_CLIENT_IDS"))
    return SocialIdentity(
        provider="google",
        subject=str(claims["sub"]),
        email=normalize_email(claims.get("email")) or None,
        email_verified=bool(claims.get("email_verified")),
        name=claims.get("name"),
    )


def verify_apple(identity_token: str) -> SocialIdentity:
    claims = _verify(identity_token, APPLE_JWKS_URL, {APPLE_ISSUER}, _audiences("APPLE_CLIENT_IDS"))
    verified = claims.get("email_verified")
    return SocialIdentity(
        provider="apple",
        subject=str(claims["sub"]),
        email=normalize_email(claims.get("email")) or None,
        # Apple sends this as the string "true"/"false" or a bool.
        email_verified=str(verified).lower() == "true",
        name=None,  # Apple only returns the name out-of-band on first consent
    )
