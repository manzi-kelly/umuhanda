import socket
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.db.session import get_session
from app.main import create_app

pytestmark = pytest.mark.integration


def test_real_postgres_readiness(integration_settings):
    app = create_app(integration_settings)
    with TestClient(app, base_url="http://localhost") as client:
        assert client.get("/api/v1/health").json() == {"status": "ok"}
        response = client.get("/api/v1/health/ready")
        assert response.status_code == 200
        assert response.json() == {"status": "ready"}
        assert app.state.database.engine.pool.checkedout() == 0


def test_real_unavailable_postgres_returns_503_without_breaking_liveness(integration_settings):
    # Reserve but do not listen on a local port: a real refused PostgreSQL connection.
    with socket.socket() as reserved:
        reserved.bind(("127.0.0.1", 0))
        unreachable = integration_settings.connection_url.set(port=reserved.getsockname()[1])
        settings = Settings(
            _env_file=None,
            app_env="testing",
            test_database_url=unreachable.render_as_string(hide_password=False),
        )
        with TestClient(create_app(settings), base_url="http://localhost") as client:
            assert client.get("/api/v1/health").status_code == 200
            response = client.get("/api/v1/health/ready")
            assert response.status_code == 503
            assert response.json() == {
                "error": {
                    "code": "DATABASE_UNAVAILABLE",
                    "message": "Database service is unavailable.",
                }
            }
            assert unreachable.password not in response.text
            assert "Traceback" not in response.text


def test_database_identity_encoding_and_least_privilege(database):
    with database.engine.connect() as connection:
        assert connection.execute(text("SELECT current_database(), current_user")).one() == (
            "roadrules_test",
            "roadrules_test_app",
        )
        assert connection.execute(text("SHOW server_encoding")).scalar_one() == "UTF8"
        assert connection.execute(
            text(
                "SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls "
                "FROM pg_roles WHERE rolname = current_user"
            )
        ).one() == (False, False, False, False, False)
        assert not connection.execute(
            text("SELECT has_database_privilege(current_user, 'roadrules_dev', 'CONNECT')")
        ).scalar_one()
        assert not connection.execute(
            text("SELECT pg_has_role(current_user, 'roadrules_test_owner', 'MEMBER')")
        ).scalar_one()


def test_session_returns_connection_to_pool(database):
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(database=database)))
    dependency = get_session(request)
    session = next(dependency)
    assert session.execute(text("SELECT 1")).scalar_one() == 1
    assert database.engine.pool.checkedout() == 1
    dependency.close()
    assert database.engine.pool.checkedout() == 0


@pytest.mark.parametrize("failure", [False, True])
def test_uncommitted_data_rolls_back_on_success_and_failure(database, failure):
    # Only a connection-local temporary probe is created, never a business table.
    with database.engine.connect() as connection:
        connection.execute(text("CREATE TEMP TABLE rr_rollback_probe (value integer)"))
        connection.commit()
        original_factory = database.session_factory
        database.session_factory = sessionmaker(bind=connection)
        try:
            request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(database=database)))
            dependency = get_session(request)
            session = next(dependency)
            session.execute(text("INSERT INTO rr_rollback_probe VALUES (42)"))
            if failure:
                with pytest.raises(RuntimeError):
                    dependency.throw(RuntimeError("deliberate rollback probe"))
            else:
                dependency.close()
            assert (
                connection.execute(text("SELECT count(*) FROM rr_rollback_probe")).scalar_one() == 0
            )
        finally:
            database.session_factory = original_factory
            connection.rollback()
            connection.execute(text("DROP TABLE pg_temp.rr_rollback_probe"))
            connection.commit()
    assert database.engine.pool.checkedout() == 0
