import pytest
from pydantic import ValidationError

from app.core.config import Settings

DEV = "postgresql+psycopg://roadrules_dev_app:unit-only@127.0.0.1:1/roadrules_dev"
TEST = "postgresql+psycopg://roadrules_test_app:unit-only@127.0.0.1:1/roadrules_test"


def test_required_database_configuration(settings):
    with pytest.raises(ValidationError, match="DATABASE_URL is required"):
        Settings(_env_file=None)


@pytest.mark.parametrize(
    "url",
    [
        "sqlite:///test.db",
        "postgresql://user:sentinel@localhost/db",
        "postgresql+psycopg://postgres:sentinel@localhost/roadrules_dev",
        "postgresql+psycopg://roadrules_dev_app@localhost/roadrules_dev",
        "not-a-url-sentinel",
        TEST + "?dbname=roadrules_dev",
        TEST + "?user=roadrules_dev_app",
    ],
)
def test_invalid_database_urls_do_not_expose_inputs(settings, url):
    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None, database_url=url)
    assert "sentinel" not in str(error.value)
    assert url not in str(error.value)


def test_secret_settings_repr_is_redacted(settings):
    assert "unit-only" not in repr(settings)
    assert "postgresql" not in repr(settings)


def test_testing_never_falls_back_to_development(settings):
    with pytest.raises(ValidationError, match="TEST_DATABASE_URL is required"):
        Settings(_env_file=None, app_env="testing", database_url=DEV)
    selected = Settings(_env_file=None, app_env="testing", database_url=DEV, test_database_url=TEST)
    assert selected.connection_url.database == "roadrules_test"
    with pytest.raises(ValidationError, match="TEST_DATABASE_URL must target"):
        Settings(_env_file=None, app_env="testing", test_database_url=DEV)


@pytest.mark.parametrize(
    "origin",
    [
        "*",
        "https://*.example.com",
        "https://user:pass@example.com",
        "https://example.com/path",
        "https://example.com?secret=1",
    ],
)
def test_cors_rejects_wildcards_and_nonorigins(settings, origin):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, database_url=DEV, cors_allowed_origins=[origin])


def test_cors_env_comma_and_json(settings, monkeypatch):
    for value in ['["http://localhost:3000"]', "http://localhost:3000,http://127.0.0.1:3000"]:
        monkeypatch.setenv("CORS_ALLOWED_ORIGINS", value)
        assert (
            Settings(_env_file=None, database_url=DEV).cors_allowed_origins[0]
            == "http://localhost:3000"
        )


def test_production_requires_explicit_safe_configuration(settings):
    production = "postgresql+psycopg://roadrules_runtime:unit-only@db.example.com/roadrules_prod"
    with pytest.raises(ValidationError, match="sslmode"):
        Settings(_env_file=None, app_env="production", database_url=production)
    secure = production + "?sslmode=verify-full"
    with pytest.raises(ValidationError, match="ALLOWED_HOSTS"):
        Settings(_env_file=None, app_env="production", database_url=secure)
    with pytest.raises(ValidationError, match="development hosts"):
        Settings(
            _env_file=None, app_env="production", database_url=secure, allowed_hosts=["localhost"]
        )
    with pytest.raises(ValidationError, match="HTTPS origins"):
        Settings(
            _env_file=None,
            app_env="production",
            database_url=secure,
            allowed_hosts=["api.example.com"],
            cors_allowed_origins=["http://localhost:3000"],
        )
    valid = Settings(
        _env_file=None,
        app_env="production",
        database_url=secure,
        allowed_hosts=["api.example.com"],
        cors_allowed_origins=["https://example.com"],
    )
    assert not valid.docs_enabled


@pytest.mark.parametrize(
    "kwargs",
    [{"db_pool_size": 0}, {"db_connect_timeout": 0}, {"allowed_hosts": ["*"]}, {"app_env": "typo"}],
)
def test_invalid_configuration_fails_closed(settings, kwargs):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, database_url=DEV, **kwargs)
