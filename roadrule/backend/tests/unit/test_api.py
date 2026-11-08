import logging
from unittest.mock import Mock

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.db.session import get_session
from app.main import create_app


def test_health_is_independent_of_database(client, monkeypatch):
    connect = Mock(side_effect=AssertionError("Liveness must not connect to PostgreSQL"))
    monkeypatch.setattr(client.app.state.database.engine, "connect", connect)
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    connect.assert_not_called()


def test_database_errors_are_safe_and_cors_applies(client):
    session = Mock()
    session.execute.side_effect = OperationalError("secret-dsn", {}, Exception("secret-password"))
    client.app.dependency_overrides[get_session] = lambda: session
    response = client.get("/api/v1/health/ready", headers={"Origin": "http://localhost:3000"})
    assert response.status_code == 503
    assert response.json() == {
        "error": {"code": "DATABASE_UNAVAILABLE", "message": "Database service is unavailable."}
    }
    assert "secret" not in response.text
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_database_failure_logging_is_sanitized(client, caplog):
    session = Mock()
    session.execute.side_effect = OperationalError(
        "postgresql://roadrules_dev_app:unit-only@127.0.0.1:1/roadrules_dev",
        {},
        Exception("secret-password"),
    )
    client.app.dependency_overrides[get_session] = lambda: session
    with caplog.at_level(logging.WARNING, logger="roadrules.api"):
        response = client.get("/api/v1/health/ready")
    assert response.status_code == 503
    assert "database_unavailable" in caplog.text
    assert "target=127.0.0.1:1/roadrules_dev" in caplog.text
    assert "sqlstate=unknown" in caplog.text
    assert "unit-only" not in caplog.text
    assert "secret-password" not in caplog.text


def test_cors_explicit_allowlist(client):
    allowed = client.options(
        "/api/v1/health",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"},
    )
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert allowed.headers["access-control-allow-credentials"] == "true"
    denied = client.options(
        "/api/v1/health",
        headers={"Origin": "https://untrusted.example", "Access-Control-Request-Method": "GET"},
    )
    assert denied.status_code == 400
    assert "access-control-allow-origin" not in denied.headers
    method = client.options(
        "/api/v1/health",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "DELETE"},
    )
    assert method.status_code == 200
    rejected = client.options(
        "/api/v1/health",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "TRACE"},
    )
    assert rejected.status_code == 400


def test_openapi_only_exposes_foundation_endpoints(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert set(response.json()["paths"]) == {
        "/api/v1/health",
        "/api/v1/health/ready",
        "/api/v1/students/sessions",
        "/api/v1/students/sessions/me",
        "/api/v1/students/sessions/revoke",
        "/api/v1/admin/auth/login",
        "/api/v1/admin/auth/me",
        "/api/v1/admin/auth/logout",
        "/api/v1/admin/dashboard/summary",
        "/api/v1/admin/exam-bank/status",
        "/api/v1/payments/mock/initiate",
        "/api/v1/payments/{payment_id}/status",
        "/api/v1/promos/redeem",
        "/api/v1/exam-access/me",
        "/api/v1/exams/start",
        "/api/v1/exams/me",
        "/api/v1/exams/{attempt_id}/current",
        "/api/v1/exams/{attempt_id}/answer",
        "/api/v1/exams/{attempt_id}/next",
        "/api/v1/exams/{attempt_id}/media/{position}/{index}",
        "/api/v1/admin/exam-execution/summary",
        "/api/v1/exams/{attempt_id}/result",
        "/api/v1/students/exams/history",
        "/api/v1/admin/exam-results",
        "/api/v1/admin/exam-results/stats",
        "/api/v1/admin/analytics/overview",
        "/api/v1/admin/system",
        "/api/v1/admin/exam-results/{attempt_id}",
        "/api/v1/admin/promo-codes",
        "/api/v1/admin/promo-codes/{promo_id}",
        "/api/v1/admin/promo-codes/{promo_id}/disable",
        "/api/v1/admin/promo-codes/{promo_id}/enable",
        "/api/v1/admin/promo-codes/{promo_id}/redemptions",
        "/api/v1/admin/mock-payments/summary",
        "/api/v1/admin/pdf-documents",
        "/api/v1/admin/pdf-documents/{document_id}",
        "/api/v1/admin/pdf-documents/{document_id}/jobs",
        "/api/v1/admin/pdf-documents/{document_id}/pages/{page_number}",
        "/api/v1/admin/pdf-import-jobs/{job_id}",
        "/api/v1/admin/pdf-import-jobs/{job_id}/retry",
        "/api/v1/admin/question-drafts",
        "/api/v1/admin/question-drafts/{draft_id}",
        "/api/v1/admin/question-draft-assets/{asset_id}",
    }
    assert "503" in response.json()["paths"]["/api/v1/health/ready"]["get"]["responses"]
    assert client.get("/docs").status_code == 200


def test_validation_and_unexpected_errors_do_not_reflect_inputs(settings):
    app = create_app(settings)

    @app.get("/_test/validate")
    def validate(value: int):
        return {"value": value}

    @app.get("/_test/failure")
    def fail():
        raise RuntimeError("private-database-password")

    with TestClient(app, raise_server_exceptions=False) as client:
        invalid = client.get("/_test/validate?value=private-input")
        assert invalid.status_code == 422
        assert invalid.json()["error"]["code"] == "VALIDATION_ERROR"
        assert "private-input" not in invalid.text
        error = client.get("/_test/failure", headers={"Origin": "http://localhost:3000"})
        assert error.status_code == 500
        assert error.json()["error"]["code"] == "INTERNAL_ERROR"
        assert "private" not in error.text
        assert error.headers["access-control-allow-origin"] == "http://localhost:3000"
        assert client.get("/not-found").status_code == 404


def test_trusted_hosts(client):
    assert client.get("/api/v1/health", headers={"Host": "testserver"}).status_code == 200
    assert client.get("/api/v1/health", headers={"Host": "untrusted.example"}).status_code == 400
    # Deployment/public hosts are only trusted when explicitly configured.
    assert (
        client.get("/api/v1/health", headers={"Host": "umuhanda.vercel.app"}).status_code == 400
    )


def test_unconfigured_deployment_origins_are_not_trusted(client):
    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": "https://umuhanda.vercel.app",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_shutdown_disposes_pool(settings, monkeypatch):
    app = create_app(settings)
    with TestClient(app) as client:
        dispose = Mock(wraps=client.app.state.database.dispose)
        monkeypatch.setattr(client.app.state.database, "dispose", dispose)
    dispose.assert_called_once()
