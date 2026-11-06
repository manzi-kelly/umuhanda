"""Validated configuration; connection secrets are never included in model repr."""

import ipaddress
import json
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from sqlalchemy.engine import URL, make_url

BACKEND_ROOT = Path(__file__).resolve().parents[2]
StringList = Annotated[list[str], NoDecode]


def parse_database_url(secret: SecretStr) -> URL:
    try:
        url = make_url(secret.get_secret_value())
        if (
            url.drivername != "postgresql+psycopg"
            or not url.host
            or not url.database
            or not url.username
            or not url.password
            or url.username.lower() in {"postgres", "root"}
            or set(url.query) - {"sslmode", "sslrootcert", "sslcert", "sslkey", "sslcrl"}
        ):
            raise ValueError
        return url
    except Exception:
        raise ValueError(
            "Use a PostgreSQL Psycopg URL with a dedicated role and credentials."
        ) from None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="forbid",
        hide_input_in_errors=True,
        frozen=True,
    )

    app_env: Literal["development", "testing", "production"] = "development"
    app_name: str = Field(default="Road Rules API", min_length=1, max_length=100)
    database_url: SecretStr | None = Field(default=None, repr=False)
    test_database_url: SecretStr | None = Field(default=None, repr=False)
    cors_allowed_origins: StringList = Field(default_factory=list)
    allowed_hosts: StringList = Field(default_factory=lambda: ["localhost", "127.0.0.1"])
    enable_docs: bool | None = None
    db_pool_size: int = Field(default=5, ge=1, le=20)
    db_max_overflow: int = Field(default=5, ge=0, le=20)
    db_pool_timeout: int = Field(default=5, ge=1, le=30)
    db_connect_timeout: int = Field(default=3, ge=1, le=30)
    db_statement_timeout_ms: int = Field(default=5000, ge=100, le=30000)
    guest_session_lifetime_seconds: int = Field(default=7200, ge=60, le=86400)
    guest_session_idle_seconds: int = Field(default=1800, ge=30, le=86400)
    guest_session_touch_seconds: int = Field(default=60, ge=1, le=300)
    guest_cookie_samesite: Literal["lax", "strict"] = "lax"
    session_creation_limit: int = Field(default=30, ge=1, le=10000)
    session_creation_window_seconds: int = Field(default=60, ge=1, le=3600)
    admin_session_lifetime_seconds: int = Field(default=28800, ge=60, le=86400)
    admin_session_idle_seconds: int = Field(default=1800, ge=30, le=86400)
    admin_session_touch_seconds: int = Field(default=60, ge=1, le=300)
    admin_login_limit: int = Field(default=20, ge=1, le=1000)
    admin_login_window_seconds: int = Field(default=60, ge=1, le=3600)

    mock_payments_enabled: bool = False
    mock_exam_amount_rwf: int = Field(default=500, ge=1, le=1000000)

    @property
    def mock_allowed(self) -> bool:
        return self.mock_payments_enabled and self.app_env in {"development", "testing"}

    exam_selection_policy: Literal[
        "DIFFICULTY_BALANCED", "CATEGORY_BALANCED", "DIFFICULTY_QUOTAS", "UNSTRATIFIED"
    ] = "DIFFICULTY_BALANCED"
    exam_category_road_sign_count: int = Field(default=1, ge=1, le=19)
    pdf_storage_root: Path = BACKEND_ROOT / ".local/pdf-storage"
    pdf_max_file_bytes: int = Field(default=26214400, ge=1024, le=104857600)
    pdf_worker_memory_mb: int = Field(default=512, ge=256, le=2048)
    pdf_ocr_tessdata: Path | None = None
    pdf_ocr_language: str = Field(default="kin", pattern=r"^[a-zA-Z0-9_+]{1,32}$")
    pdf_max_pages: int = Field(default=600, ge=1, le=1000)
    pdf_max_page_points: int = Field(default=2000, ge=100, le=4000)
    pdf_max_page_chars: int = Field(default=50000, ge=1000, le=200000)
    pdf_max_questions: int = Field(default=2000, ge=1, le=5000)
    pdf_upload_limit: int = Field(default=10, ge=1, le=100)
    pdf_upload_window_seconds: int = Field(default=3600, ge=60, le=86400)
    pdf_job_timeout_seconds: int = Field(default=300, ge=10, le=1800)
    pdf_question_pattern: str = r"^\s*(\d{1,4})[.)]\s+(.+)$"
    pdf_option_pattern: str = r"^\s*([A-Da-d])[.)]\s+(.+)$"

    @field_validator("cors_allowed_origins", "allowed_hosts", mode="before")
    @classmethod
    def parse_lists(cls, value: object) -> object:
        if isinstance(value, str):
            return (
                json.loads(value)
                if value.strip().startswith("[")
                else [entry.strip() for entry in value.split(",") if entry.strip()]
            )
        return value

    @field_validator("cors_allowed_origins")
    @classmethod
    def validate_origins(cls, origins: list[str]) -> list[str]:
        normalized = []
        for origin in origins:
            parsed = urlsplit(origin)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.path not in {"", "/"}
                or parsed.query
                or parsed.fragment
                or "*" in origin
            ):
                raise ValueError("CORS origins must be explicit HTTP(S) origins without paths.")
            _ = parsed.port  # Reject malformed ports during settings validation.
            normalized.append(origin.rstrip("/"))
        return list(dict.fromkeys(normalized))

    @field_validator("allowed_hosts")
    @classmethod
    def validate_hosts(cls, hosts: list[str]) -> list[str]:
        if not hosts or any(not host or any(c in host for c in "*/:@ ") for host in hosts):
            raise ValueError(
                "ALLOWED_HOSTS requires explicit host names without ports or wildcards."
            )
        return hosts

    @model_validator(mode="after")
    def validate_environment(self) -> "Settings":
        if (
            not self.admin_session_touch_seconds
            < self.admin_session_idle_seconds
            <= self.admin_session_lifetime_seconds
        ):
            raise ValueError("Admin timeouts require touch < inactivity <= absolute lifetime.")
        if (
            not self.guest_session_touch_seconds
            < self.guest_session_idle_seconds
            <= self.guest_session_lifetime_seconds
        ):
            raise ValueError("Session timeouts require touch < inactivity <= absolute lifetime.")
        if self.test_database_url:
            test_url = parse_database_url(self.test_database_url)
            if test_url.database != "roadrules_test" or test_url.username != "roadrules_test_app":
                raise ValueError(
                    "TEST_DATABASE_URL must target roadrules_test as roadrules_test_app."
                )
        url = self.connection_url
        if self.app_env == "testing":
            if url.database != "roadrules_test" or url.username != "roadrules_test_app":
                raise ValueError("Testing requires the isolated test database and test role.")
        elif self.app_env == "development":
            if url.database != "roadrules_dev" or url.username != "roadrules_dev_app":
                raise ValueError("Development requires roadrules_dev as roadrules_dev_app.")
        else:
            if url.database in {"roadrules_dev", "roadrules_test"}:
                raise ValueError("Production cannot use development or test databases.")
            if url.query.get("sslmode") != "verify-full":
                raise ValueError("Production requires PostgreSQL sslmode=verify-full.")
            if "allowed_hosts" not in self.model_fields_set:
                raise ValueError("Production requires explicit ALLOWED_HOSTS.")
            if any(host in {"localhost", "127.0.0.1", "testserver"} for host in self.allowed_hosts):
                raise ValueError("Production ALLOWED_HOSTS cannot inherit local development hosts.")
            for origin in self.cors_allowed_origins:
                host = urlsplit(origin).hostname
                try:
                    is_loopback = ipaddress.ip_address(host or "").is_loopback
                except ValueError:
                    is_loopback = host == "localhost"
                if not origin.startswith("https://") or is_loopback:
                    raise ValueError("Production CORS requires explicit non-local HTTPS origins.")
        return self

    @property
    def connection_url(self) -> URL:
        secret = self.test_database_url if self.app_env == "testing" else self.database_url
        if secret is None:
            name = "TEST_DATABASE_URL" if self.app_env == "testing" else "DATABASE_URL"
            raise ValueError(f"{name} is required for this environment.")
        return parse_database_url(secret)

    @property
    def docs_enabled(self) -> bool:
        return self.enable_docs if self.enable_docs is not None else self.app_env != "production"

    @property
    def guest_cookie_secure(self) -> bool:
        return self.app_env == "production"

    @property
    def guest_cookie_name(self) -> str:
        return "__Secure-roadrules_guest" if self.guest_cookie_secure else "roadrules_guest"

    @property
    def admin_cookie_name(self) -> str:
        return "__Secure-roadrules_admin" if self.guest_cookie_secure else "roadrules_admin"


def get_settings() -> Settings:
    return Settings()
