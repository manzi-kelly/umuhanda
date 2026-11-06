import hashlib
from datetime import UTC, datetime, timedelta
from http.cookies import SimpleCookie
from unittest.mock import patch

import pytest
from fastapi import Response
from pydantic import ValidationError
from starlette.requests import Request

from app.core.config import Settings
from app.core.session_security import (
    InvalidGuestSession,
    clear_guest_cookie,
    hash_token,
    new_token,
    read_token,
    session_request_allowed,
    set_guest_cookie,
)
from app.schemas.student_sessions import (
    StudentSessionRequest,
    mask_phone,
    normalize_name,
    normalize_phone,
)


@pytest.mark.parametrize("prefix", ["72", "73", "77", "78", "79"])
@pytest.mark.parametrize("format", ["0{}1234567", "+250{}1234567", "250{}1234567", "{}1234567"])
def test_rwanda_mobile_normalization(prefix, format):
    assert normalize_phone(format.format(prefix)) == f"+250{prefix}1234567"


@pytest.mark.parametrize(
    "value",
    [
        "",
        "  ",
        "0701234567",
        "0741234567",
        "0751234567",
        "0761234567",
        "0251234567",
        "+254781234567",
        "078123456",
        "07812345678",
        "++250781234567",
        "+2500781234567",
        "0781234.567",
        "٠٧٨١٢٣٤٥٦٧",
    ],
)
def test_invalid_phone(value):
    with pytest.raises(ValueError):
        normalize_phone(value)


@pytest.mark.parametrize(
    "value",
    ["", "  ", "123", "Jean 123", "<script>", "Jean--Claude", "-Jean", "Jean'", "🙂", "A" * 121],
)
def test_invalid_names(value):
    with pytest.raises(ValueError):
        normalize_name(value)


@pytest.mark.parametrize("value", ["Jean Claude", "Élodie Uwase", "Jean-Luc O’Neil", "李 明"])
def test_unicode_names(value):
    assert normalize_name(value) == value


def test_payload_normalization_and_extra_fields_rejected():
    request = StudentSessionRequest(fullName="  Jean   Claude  ", phoneNumber="+250 (78) 123-4567")
    assert request.fullName == "Jean Claude" and request.phoneNumber == "+250781234567"
    assert mask_phone(request.phoneNumber) == "+25078*****67"
    with pytest.raises(ValidationError):
        StudentSessionRequest(fullName="Jean", phoneNumber="0781234567", studentId="forged")


def test_tokens_have_256_bits_and_only_verifier_is_derived():
    with patch(
        "app.core.session_security.secrets.token_urlsafe", return_value="x" * 43
    ) as generate:
        assert new_token() == "x" * 43
        generate.assert_called_once_with(32)
    tokens = {new_token() for _ in range(100)}
    assert len(tokens) == 100 and all(len(token) == 43 for token in tokens)
    token = new_token()
    assert hash_token(token) == hashlib.sha256(token.encode("ascii")).hexdigest()
    assert len(hash_token(token)) == 64 and token != hash_token(token)


@pytest.mark.parametrize(
    "value",
    [
        "",
        "not-a-token",
        "0" * 64,
        "a" * 42,
        "a" * 44,
        "a" * 42 + "!",
        "a" * 42 + "é",
        "00000000-0000-0000-0000-000000000000",
    ],
)
def test_invalid_token_shapes(value):
    with pytest.raises(InvalidGuestSession):
        hash_token(value)


def production_settings():
    return Settings(
        _env_file=None,
        app_env="production",
        database_url="postgresql+psycopg://runtime:unit-only@db.example.com/app?sslmode=verify-full",
        allowed_hosts=["api.example.com"],
        cors_allowed_origins=["https://app.example.com"],
    )


@pytest.mark.parametrize("production", [False, True])
def test_cookie_attributes_and_matching_deletion(settings, production):
    settings = production_settings() if production else settings
    response = Response()
    set_guest_cookie(response, new_token(), datetime.now(UTC) + timedelta(hours=2), settings)
    cookie = SimpleCookie(response.headers["set-cookie"])[settings.guest_cookie_name]
    assert cookie["httponly"] and bool(cookie["secure"]) == production
    assert cookie["path"] == "/api/v1" and not cookie["domain"]
    assert cookie["samesite"] == "lax" and int(cookie["max-age"]) == 7200 and cookie["expires"]
    clear = Response()
    clear_guest_cookie(clear, settings)
    deleted = SimpleCookie(clear.headers["set-cookie"])[settings.guest_cookie_name]
    assert deleted["max-age"] == "0" and deleted["path"] == cookie["path"]
    assert bool(deleted["secure"]) == production and deleted["httponly"]


def request(method="POST", headers=None, scheme="http"):
    return Request(
        {
            "type": "http",
            "method": method,
            "scheme": scheme,
            "path": "/api/v1/students/sessions",
            "headers": [(key.lower().encode(), value.encode()) for key, value in (headers or [])],
        }
    )


@pytest.mark.parametrize(
    "headers",
    [
        [],
        [("origin", "null")],
        [("origin", "http://evil.example")],
        [("origin", "http://localhost:3000.evil.example"), ("x-csrf-protection", "1")],
        [("origin", "http://localhost:3000")],
        [("origin", "http://localhost:3000"), ("x-csrf-protection", "wrong")],
        [
            ("origin", "http://localhost:3000"),
            ("x-csrf-protection", "1"),
            ("sec-fetch-site", "cross-site"),
        ],
        [
            ("origin", "http://localhost:3000"),
            ("origin", "http://evil.example"),
            ("x-csrf-protection", "1"),
        ],
    ],
)
def test_csrf_rejects_untrusted_or_missing_protection(settings, headers):
    assert not session_request_allowed(request(headers=headers), settings)


def test_origin_csrf_and_production_tls(settings):
    assert session_request_allowed(
        request(headers=[("origin", "http://localhost:3000"), ("x-csrf-protection", "1")]), settings
    )
    assert not session_request_allowed(
        request(
            headers=[
                ("origin", "https://app.example.com"),
                ("x-csrf-protection", "1"),
                ("x-forwarded-proto", "https"),
            ]
        ),
        production_settings(),
    )


def test_duplicate_cookies_rejected(settings):
    with pytest.raises(InvalidGuestSession):
        read_token(request(headers=[("cookie", "roadrules_guest=a; roadrules_guest=b")]), settings)


@pytest.mark.parametrize(
    "options",
    [
        {"guest_session_idle_seconds": 7201},
        {"guest_session_touch_seconds": 1800},
        {"guest_cookie_samesite": "none"},
        {"session_creation_limit": 0},
    ],
)
def test_unsafe_session_settings_rejected(settings, options):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, database_url=settings.database_url, **options)
