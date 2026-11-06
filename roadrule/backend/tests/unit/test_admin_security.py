import secrets
from datetime import UTC, datetime, timedelta
from http.cookies import SimpleCookie

import pytest
from fastapi import Response
from pydantic import ValidationError

from app.core.admin_security import (
    AdminUnauthorized,
    clear_admin_cookie,
    hash_admin_token,
    hash_password,
    new_admin_token,
    set_admin_cookie,
    verify_password,
)
from app.core.config import Settings
from app.core.session_security import hash_token
from app.schemas.admin import AdminLoginRequest


def test_argon2id_password_hashing_and_random_salts():
    password = secrets.token_urlsafe(24)
    first, second = hash_password(password), hash_password(password)
    assert first.startswith("$argon2id$") and first != second and password not in first
    assert verify_password(first, password) and not verify_password(first, "incorrect")
    assert not verify_password("malformed-verifier", password)


@pytest.mark.parametrize("password", ["short", " " * 20, "x" * 257])
def test_bootstrap_rejects_weak_or_oversized_passwords(password):
    with pytest.raises(ValueError):
        hash_password(password)


def test_admin_tokens_are_separate_from_guest_credentials():
    tokens = {new_admin_token() for _ in range(50)}
    assert len(tokens) == 50 and all(len(token) == 43 for token in tokens)
    token = new_admin_token()
    assert hash_admin_token(token) != hash_token(token)
    assert len(hash_admin_token(token)) == 64
    with pytest.raises(AdminUnauthorized):
        hash_admin_token("00000000-0000-0000-0000-000000000000")


@pytest.mark.parametrize("email", [None, "invalid", "somebody@", "name@exam ple.com"])
def test_invalid_email_is_rejected_without_echo(email):
    with pytest.raises(ValidationError):
        AdminLoginRequest(email=email, password="not-a-real-credential")


def test_normalized_email_and_secret_schema():
    payload = AdminLoginRequest(email="  OPERATOR@EXAMPLE.COM ", password="not-a-real-credential")
    assert str(payload.email) == "operator@example.com"
    assert "not-a-real-credential" not in repr(payload)
    with pytest.raises(ValidationError):
        AdminLoginRequest(email="operator@example.com", password="x", role="ADMIN")


@pytest.mark.parametrize("production", [False, True])
def test_admin_cookie_policy(settings, production):
    if production:
        settings = Settings(
            _env_file=None,
            app_env="production",
            database_url="postgresql+psycopg://runtime:unit-only@db.example.com/app?sslmode=verify-full",
            allowed_hosts=["api.example.com"],
        )
    response = Response()
    set_admin_cookie(response, new_admin_token(), datetime.now(UTC) + timedelta(hours=8), settings)
    cookie = SimpleCookie(response.headers["set-cookie"])[settings.admin_cookie_name]
    assert (
        cookie["httponly"] and cookie["samesite"] == "strict" and cookie["path"] == "/api/v1/admin"
    )
    assert bool(cookie["secure"]) == production and not cookie["domain"]
    cleared = Response()
    clear_admin_cookie(cleared, settings)
    deleted = SimpleCookie(cleared.headers["set-cookie"])[settings.admin_cookie_name]
    assert deleted["max-age"] == "0" and deleted["path"] == cookie["path"]


def test_cli_rejects_noninteractive_password_input(monkeypatch, capsys):
    from scripts import bootstrap_admin

    monkeypatch.setattr("sys.argv", ["bootstrap_admin.py", "--confirm-first-admin"])
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    assert bootstrap_admin.main() == 1
    assert "interactive" in capsys.readouterr().out
