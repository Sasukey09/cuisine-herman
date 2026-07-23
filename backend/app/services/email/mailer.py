"""Outbound email.

One function the app needs today — the password-reset link — behind a small
abstraction so the endpoint never talks to a provider directly.

Delivery backend, chosen from the environment (first match wins):

* ``RESEND_API_KEY`` set -> Resend HTTP API (recommended).
* ``SMTP_HOST`` set      -> SMTP (STARTTLS by default).
* otherwise              -> "console": the link is written to the structured log
                            rather than dropped. A misconfigured mailer must be
                            *visible*, never a silent black hole that makes
                            account recovery look broken.

Sender address: ``MAIL_FROM`` (fallback ``RESEND_FROM`` / ``SMTP_FROM``). For
Resend, this must be an address on a domain you verified in the Resend dashboard;
``onboarding@resend.dev`` (the default) works out of the box but only delivers to
your own account email — set ``MAIL_FROM`` to your verified domain for real users.

Sending never raises to the caller: whether or not delivery succeeds must not
change the HTTP response (that is what keeps the reset endpoint from leaking
which addresses have an account).
"""
import logging
import os
import smtplib
import ssl
from email.message import EmailMessage

import httpx

from app.core.logging import get_logger, log_event

logger = get_logger("email")

_BRAND = "FoodGad"
_DEFAULT_FROM = f"{_BRAND} <onboarding@resend.dev>"


def _from_address() -> str:
    return (
        os.getenv("MAIL_FROM")
        or os.getenv("RESEND_FROM")
        or os.getenv("SMTP_FROM")
        or _DEFAULT_FROM
    ).strip()


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


# --------------------------------------------------------------------------- #
# The FoodGad-branded reset email (HTML + plain-text fallback).
# Table-based, fully inline styles: that is the only thing email clients render
# reliably. Warm cream background, terracotta CTA — the app's own palette.
# --------------------------------------------------------------------------- #
_SUBJECT = "Réinitialisez votre mot de passe FoodGad"


def _text_body(link: str) -> str:
    return (
        "Bonjour,\n\n"
        "Vous avez demandé à réinitialiser votre mot de passe FoodGad.\n"
        "Ouvrez ce lien pour choisir un nouveau mot de passe "
        "(valable 1 heure, utilisable une seule fois) :\n\n"
        f"{link}\n\n"
        "Si vous n'êtes pas à l'origine de cette demande, ignorez cet e-mail : "
        "votre mot de passe reste inchangé.\n\n"
        "— L'équipe FoodGad\n"
        "FoodGad · le coût matière de votre cuisine, sous contrôle."
    )


def _html_body(link: str) -> str:
    return f"""\
<!doctype html>
<html lang="fr">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_SUBJECT}</title></head>
<body style="margin:0;padding:0;background:#f4efe6;">
  <span style="display:none;max-height:0;overflow:hidden;opacity:0;">Lien de réinitialisation — valable 1 heure, à usage unique.</span>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4efe6;padding:32px 12px;">
    <tr><td align="center">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:520px;background:#fffdf9;border:1px solid #e7ded0;border-radius:16px;overflow:hidden;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;">
        <!-- Logo -->
        <tr><td style="padding:28px 32px 8px 32px;">
          <table role="presentation" cellpadding="0" cellspacing="0"><tr>
            <td style="width:40px;height:40px;background:#c1663f;border-radius:10px;text-align:center;vertical-align:middle;color:#ffffff;font-weight:700;font-size:20px;font-family:Georgia,'Times New Roman',serif;">F</td>
            <td style="padding-left:12px;font-size:19px;font-weight:700;color:#2b2622;font-family:Georgia,'Times New Roman',serif;">FoodGad</td>
          </tr></table>
        </td></tr>
        <!-- Heading + body -->
        <tr><td style="padding:12px 32px 4px 32px;">
          <h1 style="margin:0 0 12px 0;font-size:22px;line-height:1.3;color:#2b2622;font-family:Georgia,'Times New Roman',serif;font-weight:700;">Réinitialisez votre mot de passe</h1>
          <p style="margin:0 0 8px 0;font-size:15px;line-height:1.6;color:#4a443e;">Bonjour,</p>
          <p style="margin:0 0 20px 0;font-size:15px;line-height:1.6;color:#4a443e;">Vous avez demandé à réinitialiser votre mot de passe FoodGad. Cliquez sur le bouton ci-dessous pour en choisir un nouveau.</p>
        </td></tr>
        <!-- CTA -->
        <tr><td align="center" style="padding:4px 32px 8px 32px;">
          <table role="presentation" cellpadding="0" cellspacing="0"><tr>
            <td style="border-radius:12px;background:#c1663f;">
              <a href="{link}" style="display:inline-block;padding:14px 30px;font-size:15px;font-weight:600;color:#ffffff;text-decoration:none;border-radius:12px;">Réinitialiser mon mot de passe</a>
            </td>
          </tr></table>
        </td></tr>
        <tr><td style="padding:16px 32px 4px 32px;">
          <p style="margin:0 0 6px 0;font-size:12.5px;line-height:1.5;color:#8a817a;">Le bouton ne fonctionne pas ? Copiez ce lien dans votre navigateur :</p>
          <p style="margin:0 0 18px 0;font-size:12.5px;line-height:1.5;word-break:break-all;"><a href="{link}" style="color:#c1663f;">{link}</a></p>
          <p style="margin:0 0 4px 0;font-size:13px;line-height:1.5;color:#8a817a;">🔒 Ce lien est valable <b>1 heure</b> et utilisable <b>une seule fois</b>.</p>
          <p style="margin:0 0 20px 0;font-size:13px;line-height:1.5;color:#8a817a;">Si vous n'êtes pas à l'origine de cette demande, ignorez cet e-mail : votre mot de passe reste inchangé.</p>
        </td></tr>
        <!-- Footer -->
        <tr><td style="padding:18px 32px 26px 32px;border-top:1px solid #efe7d9;">
          <p style="margin:0;font-size:12px;line-height:1.5;color:#a79e93;">FoodGad · le coût matière de votre cuisine, sous contrôle.</p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body></html>"""


def _send_resend(to_email: str, subject: str, text: str, html: str) -> None:
    api_key = os.getenv("RESEND_API_KEY", "").strip()
    resp = httpx.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "from": _from_address(),
            "to": [to_email],
            "subject": subject,
            "html": html,
            "text": text,
        },
        timeout=15,
    )
    resp.raise_for_status()


def _send_smtp(to_email: str, subject: str, text: str, html: str) -> None:
    host = os.getenv("SMTP_HOST", "").strip()
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER", "").strip()
    password = os.getenv("SMTP_PASSWORD", "")
    use_tls = os.getenv("SMTP_TLS", "true").lower() != "false"

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = _from_address()
    msg["To"] = to_email
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")

    with smtplib.SMTP(host, port, timeout=15) as server:
        if use_tls:
            server.starttls(context=ssl.create_default_context())
        if user:
            server.login(user, password)
        server.send_message(msg)


def send_password_reset_email(to_email: str, token: str) -> None:
    """Deliver (or log) the branded reset email. Never raises."""
    link = build_reset_link(token)
    text = _text_body(link)
    html = _html_body(link)

    provider = None
    if os.getenv("RESEND_API_KEY", "").strip():
        provider = "resend"
    elif os.getenv("SMTP_HOST", "").strip():
        provider = "smtp"

    if provider is None:
        # No mailer configured: surface the link in the logs rather than losing
        # it silently, so recovery is usable in dev and a prod misconfiguration
        # is obvious in the log stream.
        log_event(
            logger, logging.WARNING, "email.reset_link_not_sent_no_provider",
            to=to_email, link=link,
        )
        return

    try:
        if provider == "resend":
            _send_resend(to_email, _SUBJECT, text, html)
        else:
            _send_smtp(to_email, _SUBJECT, text, html)
        log_event(logger, logging.INFO, "email.reset_link_sent", to=to_email, provider=provider)
    except Exception as exc:  # delivery failure must not change the HTTP answer
        log_event(
            logger, logging.ERROR, "email.reset_link_send_failed",
            to=to_email, provider=provider, error=str(exc),
        )
