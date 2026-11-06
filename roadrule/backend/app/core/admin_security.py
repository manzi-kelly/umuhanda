"""Administrator-only credentials; deliberately independent of guest identity."""

import hashlib
import secrets
from datetime import datetime

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Request, Response

from app.core.config import Settings
from app.core.session_security import TOKEN_PATTERN

ADMIN_PATH = "/api/v1/admin"
PASSWORD_HASHER = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2, type=Type.ID)
# Not an account/default credential: equal-cost verification for unknown email attempts.
DUMMY_HASH = PASSWORD_HASHER.hash(secrets.token_urlsafe(32))


class AdminUnauthorized(Exception):
    pass


class AdminLoginLimited(Exception):
    pass


class BootstrapRefused(Exception):
    pass


def hash_password(password: str) -> str:
    if not 15 <= len(password) <= 256 or not password.strip():
        raise ValueError("Use a nonblank administrator passphrase of 15–256 characters.")
    return PASSWORD_HASHER.hash(password)


def verify_password(verifier: str, password: str) -> bool:
    if not verifier.startswith("$argon2id$"):
        return False
    try:
        return PASSWORD_HASHER.verify(verifier, password)
    except (VerificationError, InvalidHashError):
        return False


def new_admin_token() -> str:
    return secrets.token_urlsafe(32)


def hash_admin_token(token: str) -> str:
    if TOKEN_PATTERN.fullmatch(token) is None:
        raise AdminUnauthorized
    return hashlib.sha256(("admin:" + token).encode("ascii")).hexdigest()


def admin_token(request: Request, settings: Settings) -> str | None:
    names = [
        part.strip().split("=", 1)[0].strip()
        for header in request.headers.getlist("cookie")
        for part in header.split(";")
    ]
    if names.count(settings.admin_cookie_name) > 1:
        raise AdminUnauthorized
    return request.cookies.get(settings.admin_cookie_name)


def set_admin_cookie(response: Response, token: str, expires: datetime, settings: Settings) -> None:
    response.set_cookie(
        settings.admin_cookie_name,
        token,
        path=ADMIN_PATH,
        max_age=settings.admin_session_lifetime_seconds,
        expires=expires,
        httponly=True,
        secure=settings.guest_cookie_secure,
        samesite="strict",
    )


def clear_admin_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        settings.admin_cookie_name,
        path=ADMIN_PATH,
        httponly=True,
        secure=settings.guest_cookie_secure,
        samesite="strict",
    )
