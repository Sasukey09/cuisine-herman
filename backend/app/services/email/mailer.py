"""Outbound email.

One function the app actually needs today — the password-reset link — behind a
tiny abstraction so the endpoint never talks to SMTP directly.

Delivery backend is chosen from the environment:

* ``SMTP_HOST`` set  -> send over SMTP (STARTTLS by default).
* otherwise          -> "console" backend: the link is written to the structured
                        log instead of dropped. A misconfigured mailer must be
                        *visible*, never a silent black hole that makes recovery
                        look broken.

Sending never raises to the caller: whether or not delivery succeeds must not
change the HTTP response (that is what stops the reset endpoint from leaking
which addresses have an account).
"""
import logging
import os
import smtplib
import ssl
from email.message import EmailMessage
from typing import Optional

from app.core.logging import get_logger, log_event

logger = get_logger("email")


def _frontend_url() -> str:
    # Where the reset link points. Falls back to the first CORS origin, then to
    # localhost, so a link is always well-formed even before FRONTEND_URL is set.
    url = os.getenv("FRONTEND_URL", "").strip()
    if url:
        return url.rstrip("/")
    cors = os.getenv("CORS_ORIGINS", "").split(",")[0].strip()
    return (cors or "http://localhost:3000").rstrip("/")


def build_reset_link(token: str) -> str:
    return f"{_frontend_url()}/reset-password?token={token}"


def _render(to_email: str, link: str) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = "Réinitialisation de votre mot de passe FoodGad"
    msg["From"] = os.getenv("SMTP_FROM", "no-reply@foodgad.app")
    msg["To"] = to_email
    msg.set_content(
        "Bonjour,\n\n"
        "Vous avez demandé à réinitialiser votre mot de passe FoodGad.\n"
        "Cliquez sur le lien ci-dessous (valable 1 heure, utilisable une seule fois) :\n\n"
        f"{link}\n\n"
        "Si vous n'êtes pas à l'origine de cette demande, ignorez cet e-mail : "
        "votre mot de passe reste inchangé.\n\n"
        "— L'équipe FoodGad"
    )
    return msg


def _send_smtp(msg: EmailMessage) -> None:
    host = os.getenv("SMTP_HOST", "").strip()
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER", "").strip()
    password = os.getenv("SMTP_PASSWORD", "")
    use_tls = os.getenv("SMTP_TLS", "true").lower() != "false"

    with smtplib.SMTP(host, port, timeout=15) as server:
        if use_tls:
            server.starttls(context=ssl.create_default_context())
        if user:
            server.login(user, password)
        server.send_message(msg)


def send_password_reset_email(to_email: str, token: str) -> None:
    """Deliver (or log) the reset link. Never raises."""
    link = build_reset_link(token)
    if not os.getenv("SMTP_HOST", "").strip():
        # No mailer configured: make the link visible in the logs rather than
        # silently lost, so recovery is usable in dev/staging and a prod
        # misconfiguration is obvious in the log stream.
        log_event(
            logger, logging.WARNING, "email.reset_link_not_sent_no_smtp",
            to=to_email, link=link,
        )
        return
    try:
        _send_smtp(_render(to_email, link))
        log_event(logger, logging.INFO, "email.reset_link_sent", to=to_email)
    except Exception as exc:  # delivery failure must not change the HTTP answer
        log_event(logger, logging.ERROR, "email.reset_link_send_failed", to=to_email, error=str(exc))
