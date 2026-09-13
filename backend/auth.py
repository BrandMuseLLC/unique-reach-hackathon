from __future__ import annotations

import os
import re
from dataclasses import dataclass
from functools import lru_cache

from fastapi import Request
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

IAP_CERTS_URL = "https://www.gstatic.com/iap/verify/public_key"
IAP_AUDIENCE_RE = re.compile(r"^/projects/\d+/(?:global/backendServices/\d+|locations/[a-z]+-[a-z]+\d+/services/[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?)$")
GOOGLE_ACCOUNT_PREFIX = "accounts.google.com:"


@dataclass(frozen=True)
class AuthenticatedUser:
    email: str
    subject: str


@dataclass(frozen=True)
class AuthSettings:
    mode: str
    invited_emails: frozenset[str]
    iap_audience: str


class AuthError(ValueError):
    pass


@lru_cache(maxsize=1)
def auth_settings() -> AuthSettings:
    mode = os.getenv("AUTH_MODE", "local").lower()
    invited_emails = frozenset(
        normalize_iap_email(email)
        for email in os.getenv("INVITED_EMAILS", "").split(",")
        if email.strip()
    )
    iap_audience = os.getenv("IAP_AUDIENCE", "").strip()
    return AuthSettings(mode=mode, invited_emails=invited_emails, iap_audience=iap_audience)


def validate_auth_configuration(settings: AuthSettings | None = None) -> None:
    current = settings or auth_settings()
    if current.mode == "local":
        return
    if current.mode != "iap":
        raise RuntimeError("AUTH_MODE must be 'local' or 'iap'.")
    if not current.invited_emails:
        raise RuntimeError("INVITED_EMAILS is required when AUTH_MODE=iap.")
    invalid_invites = [email for email in current.invited_emails if "@" not in email or any(char.isspace() for char in email)]
    if invalid_invites:
        raise RuntimeError("INVITED_EMAILS must contain comma-separated Google account emails.")
    if not current.iap_audience:
        raise RuntimeError("IAP_AUDIENCE is required when AUTH_MODE=iap.")
    if not IAP_AUDIENCE_RE.fullmatch(current.iap_audience):
        raise RuntimeError("IAP_AUDIENCE must look like a backend-service audience or /projects/PROJECT_NUMBER/locations/REGION/services/SERVICE_NAME.")


def verify_iap_jwt(assertion: str, audience: str) -> dict[str, object]:
    request = google_requests.Request()
    return id_token.verify_token(assertion, request=request, audience=audience, certs_url=IAP_CERTS_URL)


def normalize_iap_email(email: str) -> str:
    return email.strip().lower().removeprefix(GOOGLE_ACCOUNT_PREFIX).strip()


def user_from_request(request: Request) -> AuthenticatedUser:
    settings = getattr(request.app.state, "auth_settings", auth_settings())
    if settings.mode == "local":
        return AuthenticatedUser(email="local-dev@example.test", subject="local-dev")

    validate_auth_configuration(settings)
    assertion = request.headers.get("x-goog-iap-jwt-assertion")
    if not assertion:
        raise AuthError("Authentication required.")

    verifier = getattr(request.app.state, "iap_verifier", verify_iap_jwt)
    try:
        payload = verifier(assertion, settings.iap_audience)
    except Exception as exc:
        raise AuthError("Invalid identity token.") from exc
    if payload.get("iss") != "https://cloud.google.com/iap":
        raise AuthError("Invalid identity token issuer.")
    email = normalize_iap_email(str(payload.get("email", "")))
    subject = str(payload.get("sub", ""))
    if not email or not subject:
        raise AuthError("Invalid identity token.")
    if email not in settings.invited_emails:
        raise AuthError("This Google account is not invited to this preview.")
    return AuthenticatedUser(email=email, subject=subject)
