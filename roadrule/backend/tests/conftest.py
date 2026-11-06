from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.config import Settings
from app.db.session import Database
from app.main import create_app


@pytest.fixture
def settings(monkeypatch):
    for name in Settings.model_fields:
        monkeypatch.delenv(name.upper(), raising=False)
    return Settings(
        _env_file=None,
        database_url="postgresql+psycopg://roadrules_dev_app:unit-only@127.0.0.1:1/roadrules_dev",
        cors_allowed_origins=["http://localhost:3000"],
        allowed_hosts=["testserver", "localhost", "127.0.0.1"],
    )


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings), raise_server_exceptions=False) as client:
        yield client


@pytest.fixture(scope="session")
def integration_settings():
    # Fails rather than skips if real PostgreSQL integration prerequisites are missing.
    try:
        settings = Settings(app_env="testing")
    except ValueError:
        pytest.fail("Integration requires a valid TEST_DATABASE_URL for roadrules_test.")
    assert settings.connection_url.database == "roadrules_test"
    assert settings.connection_url.username == "roadrules_test_app"
    database = Database(settings)
    try:
        with database.engine.connect() as connection:
            assert connection.execute(text("SELECT current_database(), current_user")).one() == (
                "roadrules_test",
                "roadrules_test_app",
            )
    finally:
        database.dispose()
    return settings


@pytest.fixture
def database(integration_settings):
    database = Database(integration_settings)
    try:
        yield database
    finally:
        database.dispose()


@pytest.fixture
def migration_config(integration_settings, monkeypatch):
    from alembic.config import Config

    monkeypatch.setenv("APP_ENV", "testing")
    monkeypatch.setenv(
        "TEST_DATABASE_URL", integration_settings.test_database_url.get_secret_value()
    )
    return Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
