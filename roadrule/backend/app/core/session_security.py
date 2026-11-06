"""Opaque guest credentials are identity continuity, never exam authorization."""

import hashlib
import re
import secrets
from datetime import datetime

from fastapi import Request, Response

from app.core.config import Settings

COOKIE_PATH = "/api/v1"
SESSION_PATH = "/api/v1/students/sessions"
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_-]{43}", flags=re.ASCII)


class InvalidGuestSession(Exception):
    pass


class SessionCreationLimited(Exception):
    pass


def new_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    if TOKEN_PATTERN.fullmatch(token) is None:
        raise InvalidGuestSession
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def read_token(request: Request, settings: Settings) -> str | None:
    # Reject ambiguous same-name cookies from different paths instead of choosing one.
    count = sum(
        part.strip().split("=", 1)[0].strip() == settings.guest_cookie_name
        for header in request.headers.getlist("cookie")
        for part in header.split(";")
    )
    if count > 1:
        raise InvalidGuestSession
    return request.cookies.get(settings.guest_cookie_name)


def set_guest_cookie(response: Response, token: str, expires: datetime, settings: Settings) -> None:
    response.set_cookie(
        settings.guest_cookie_name,
        token,
        max_age=settings.guest_session_lifetime_seconds,
        expires=expires,
        path=COOKIE_PATH,
        httponly=True,
        secure=settings.guest_cookie_secure,
        samesite=settings.guest_cookie_samesite,
    )


def clear_guest_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        settings.guest_cookie_name,
        path=COOKIE_PATH,
        httponly=True,
        secure=settings.guest_cookie_secure,
        samesite=settings.guest_cookie_samesite,
    )


def session_request_allowed(request: Request, settings: Settings) -> bool:
    if settings.guest_cookie_secure and request.url.scheme != "https":
        return False
    origins = request.headers.getlist("origin")
    if len(origins) > 1 or (origins and origins[0] not in settings.cors_allowed_origins):
        return False
    if request.headers.get("sec-fetch-site") == "cross-site":
        return False
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        return bool(origins) and request.headers.getlist("x-csrf-protection") == ["1"]
    return True
