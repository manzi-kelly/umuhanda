"""Read-only database audit and real HTTP smoke check; outputs no connection secrets."""

import importlib.metadata
import json
import platform
import socket
import threading
import time
from pathlib import Path

import httpx
import uvicorn
from sqlalchemy import inspect, text

from app.core.config import Settings
from app.db.session import Database
from app.main import create_app

ROOT = Path(__file__).resolve().parents[1]


def live_check(settings: Settings, expected_ready: int) -> dict:
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    server = uvicorn.Server(
        uvicorn.Config(
            create_app(settings),
            host="127.0.0.1",
            port=port,
            log_level="warning",
            access_log=False,
        )
    )
    thread = threading.Thread(target=lambda: server.run(sockets=[listener]), daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 15
        while not server.started and time.monotonic() < deadline and thread.is_alive():
            time.sleep(0.05)
        if not server.started:
            raise RuntimeError("Live API did not start.")
        with httpx.Client(
            base_url=f"http://127.0.0.1:{port}", timeout=10, trust_env=False
        ) as client:
            health = client.get("/api/v1/health")
            ready = client.get("/api/v1/health/ready")
            assert health.status_code == 200 and health.json() == {"status": "ok"}
            assert ready.status_code == expected_ready
            expected_body = (
                {"status": "ready"}
                if expected_ready == 200
                else {
                    "error": {
                        "code": "DATABASE_UNAVAILABLE",
                        "message": "Database service is unavailable.",
                    }
                }
            )
            assert ready.json() == expected_body
            assert client.get("/docs").status_code == 200
            assert set(client.get("/openapi.json").json()["paths"]) == {
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
                "/api/v1/health",
                "/api/v1/health/ready",
                "/api/v1/students/sessions",
                "/api/v1/students/sessions/me",
                "/api/v1/students/sessions/revoke",
            }
            return {
                "health": health.status_code,
                "health_body": health.json(),
                "ready": ready.status_code,
                "ready_body": ready.json(),
                "docs": 200,
                "openapi": 200,
            }
    finally:
        server.should_exit = True
        thread.join(timeout=15)
        listener.close()
        if thread.is_alive():
            raise RuntimeError("Live API did not shut down cleanly.")


def main() -> None:
    evidence = {"python": platform.python_version(), "dependencies": {}, "databases": {}}
    for dependency in (
        "fastapi",
        "uvicorn",
        "sqlalchemy",
        "psycopg",
        "psycopg-binary",
        "alembic",
        "pydantic",
        "pydantic-settings",
        "pytest",
        "httpx",
        "ruff",
    ):
        evidence["dependencies"][dependency] = importlib.metadata.version(dependency)
    for environment in ("development", "testing"):
        database = Database(Settings(app_env=environment))
        try:
            with database.engine.connect() as connection:
                identity = connection.execute(text("SELECT current_database(), current_user")).one()
                flags = connection.execute(
                    text(
                        "SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls "
                        "FROM pg_roles WHERE rolname = current_user"
                    )
                ).one()
                other = "roadrules_dev" if environment == "testing" else "roadrules_test"
                access = connection.execute(
                    text("SELECT has_database_privilege(current_user, :other, 'CONNECT')"),
                    {"other": other},
                ).scalar_one()
                tables = inspect(connection).get_table_names()
                revision = connection.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar_one()
                assert (
                    not any(flags)
                    and not access
                    and set(tables)
                    == {
                        "alembic_version",
                        "students",
                        "guest_sessions",
                        "student_activity_events",
                        "admin_users",
                        "admin_sessions",
                        "admin_audit_events",
                        "pdf_documents",
                        "exam_bank_revisions",
                        "exam_bank_questions",
                        "exam_attempts",
                        "exam_attempt_items",
                        "exam_operational_events",
                        "exam_timing",
                        "refund_requests",
                        "exam_results",
                        "exam_grading_failures",
                        "exam_responses",
                        "exam_entitlements",
                        "payment_transactions",
                        "promo_codes",
                        "promo_attempts",
                        "pdf_import_jobs",
                        "question_drafts",
                        "question_draft_options",
                        "question_draft_answers",
                        "question_draft_assets",
                    }
                )
                assert revision == "20261106_0010"
                evidence["databases"][environment] = {
                    "database": identity[0],
                    "role": identity[1],
                    "encoding": connection.execute(text("SHOW server_encoding")).scalar_one(),
                    "server_version": connection.execute(text("SHOW server_version")).scalar_one(),
                    "privileged_role_flags": list(flags),
                    "can_connect_other_database": access,
                    "tables": tables,
                    "revision": revision,
                }
        finally:
            database.dispose()
    settings = Settings(app_env="testing")
    evidence["live_available"] = live_check(settings, 200)
    with socket.socket() as reserved:
        reserved.bind(("127.0.0.1", 0))
        unreachable = settings.connection_url.set(port=reserved.getsockname()[1])
        offline = Settings(
            _env_file=None,
            app_env="testing",
            test_database_url=unreachable.render_as_string(hide_password=False),
        )
        evidence["live_unavailable"] = live_check(offline, 503)
    evidence["clean_shutdown"] = True
    output = ROOT.parent / "docs/evidence/phase04i/foundation-verification.json"
    output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print("Live API and read-only database audit passed; sanitized evidence saved.")


if __name__ == "__main__":
    main()
