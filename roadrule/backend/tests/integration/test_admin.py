import secrets
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, inspect, select, text, update

from alembic import command
from app.core.admin_security import ADMIN_PATH, BootstrapRefused, hash_admin_token
from app.core.config import Settings
from app.main import create_app
from app.models import AdminAuditEvent, AdminSession, AdminUser, Student
from app.services.admin_auth import AdminAuthService

pytestmark = pytest.mark.integration
HEADERS = {"Origin": "http://localhost:3000", "X-CSRF-Protection": "1"}
LOGIN = ADMIN_PATH + "/auth/login"
ME = ADMIN_PATH + "/auth/me"
LOGOUT = ADMIN_PATH + "/auth/logout"
SUMMARY = ADMIN_PATH + "/dashboard/summary"
ALL_TABLES = {
    "alembic_version",
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
    "pdf_documents",
    "pdf_import_jobs",
    "question_drafts",
    "question_draft_options",
    "question_draft_answers",
    "question_draft_assets",
    "students",
    "guest_sessions",
    "student_activity_events",
    "admin_users",
    "admin_sessions",
    "admin_audit_events",
}


@pytest.fixture
def admin_database(database, migration_config):
    command.upgrade(migration_config, "head")

    def clear():
        with database.engine.begin() as connection:
            assert connection.execute(text("SELECT current_database(), current_user")).one() == (
                "roadrules_test",
                "roadrules_test_app",
            )
            assert set(inspect(connection).get_table_names()) == ALL_TABLES
            connection.execute(
                text(
                    "TRUNCATE refund_requests, exam_results, exam_grading_failures, "
                    "exam_responses, exam_timing, exam_entitlements, "
                    "payment_transactions, promo_attempts, "
                    "exam_attempt_items, exam_attempts, exam_bank_questions, "
                    "exam_bank_revisions, exam_operational_events, promo_codes, "
                    "question_draft_answers, question_draft_assets, "
                    "question_draft_options, "
                    "question_drafts, pdf_import_jobs, pdf_documents, "
                    "admin_audit_events, admin_sessions, admin_users, "
                    "student_activity_events, guest_sessions, students"
                )
            )

    clear()
    try:
        yield database
    finally:
        clear()


@pytest.fixture
def admin_settings(integration_settings):
    return Settings(
        _env_file=None,
        app_env="testing",
        test_database_url=integration_settings.test_database_url,
        cors_allowed_origins=["http://localhost:3000"],
    )


@pytest.fixture
def account(admin_database, admin_settings):
    password = secrets.token_urlsafe(24)
    with admin_database.session_factory() as session:
        identifier = AdminAuthService(session, admin_settings).bootstrap(
            "Test Administrator", "operator@example.com", password
        )
    return {"id": identifier, "email": "operator@example.com", "password": password}


@pytest.fixture
def admin_client(account, admin_settings):
    with TestClient(
        create_app(admin_settings), base_url="http://localhost", raise_server_exceptions=False
    ) as client:
        yield client


def login(client, account):
    response = client.post(
        LOGIN, headers=HEADERS, json={"email": account["email"], "password": account["password"]}
    )
    assert response.status_code == 200
    return response, client.cookies.get("roadrules_admin")


def test_bootstrap_is_once_and_never_stores_password(account, admin_database, admin_settings):
    with admin_database.session_factory() as session:
        admin = session.get(AdminUser, account["id"])
        assert (
            admin.password_hash.startswith("$argon2id$")
            and account["password"] not in admin.password_hash
        )
        with pytest.raises(BootstrapRefused):
            session.rollback()
            AdminAuthService(session, admin_settings).bootstrap(
                "Another Administrator", "other@example.com", secrets.token_urlsafe(24)
            )
    with admin_database.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(AdminUser)) == 1


def test_bootstrap_marker_survives_admin_deletion(account, admin_database, admin_settings):
    with admin_database.engine.begin() as connection:
        connection.execute(delete(AdminUser).where(AdminUser.id == account["id"]))
    with admin_database.session_factory() as session, pytest.raises(BootstrapRefused):
        AdminAuthService(session, admin_settings).bootstrap(
            "Another Administrator", "other@example.com", secrets.token_urlsafe(24)
        )


def test_bootstrap_concurrency_allows_only_one(admin_database, admin_settings):
    def bootstrap(number):
        with admin_database.session_factory() as session:
            try:
                AdminAuthService(session, admin_settings).bootstrap(
                    "Concurrent Administrator",
                    f"operator{number}@example.com",
                    secrets.token_urlsafe(24),
                )
                return "created"
            except BootstrapRefused:
                return "refused"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(bootstrap, [1, 2])) == ["created", "refused"]


def test_admin_login_and_only_hashed_session(admin_client, account, admin_database, caplog):
    response, token = login(admin_client, account)
    body = response.json()
    assert set(body) == {"id", "fullName", "email", "role", "expiresAt"}
    assert body["role"] == "ADMIN" and UUID(body["id"]) == account["id"]
    assert token not in response.text and account["password"] not in response.text
    assert response.headers["cache-control"] == "no-store"
    with admin_database.session_factory() as session:
        stored = session.scalar(select(AdminSession))
        assert stored.token_hash == hash_admin_token(token) and stored.token_hash != token
        events = session.scalars(select(AdminAuditEvent)).all()
        assert all(set(event.sanitized_metadata) <= {"result", "reason"} for event in events)
    assert token not in caplog.text and account["password"] not in caplog.text
    assert admin_client.get(ME).json() == body


@pytest.mark.parametrize("case", ["wrong", "unknown", "inactive"])
def test_generic_login_failure(admin_client, account, admin_database, case):
    payload = {"email": account["email"], "password": account["password"]}
    if case == "wrong":
        payload["password"] = "incorrect"
    if case == "unknown":
        payload["email"] = "missing@example.com"
    if case == "inactive":
        with admin_database.engine.begin() as connection:
            connection.execute(update(AdminUser).values(is_active=False))
    response = admin_client.post(LOGIN, json=payload, headers=HEADERS)
    assert response.status_code == 401
    assert response.json() == {
        "error": {"code": "ADMIN_AUTH_REQUIRED", "message": "Administrator authentication failed."}
    }
    assert "operator@example.com" not in response.text
    with admin_database.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(AdminSession)) == 0
        assert (
            session.scalar(
                select(func.count())
                .select_from(AdminAuditEvent)
                .where(AdminAuditEvent.event_type == "ADMIN_LOGIN_ATTEMPT")
            )
            == 1
        )


def test_unauthorized_student_and_uuid_cannot_access_admin(admin_client, account):
    for endpoint in [ME, SUMMARY]:
        assert admin_client.get(endpoint).status_code == 401
    guest = admin_client.post(
        "/api/v1/students/sessions",
        json={"fullName": "Student Guest", "phoneNumber": "0781234567"},
        headers=HEADERS,
    )
    assert guest.status_code == 201
    guest_token = admin_client.cookies.get("roadrules_guest")
    assert admin_client.get(SUMMARY).status_code == 401
    for value in [guest_token, str(account["id"]), str(uuid4())]:
        admin_client.cookies.set("roadrules_admin", value, path=ADMIN_PATH)
        assert admin_client.get(SUMMARY, headers={"X-Admin-Role": "ADMIN"}).status_code == 401
        admin_client.cookies.clear()


def test_dashboard_uses_real_count_and_null_unimplemented_metrics(
    admin_client, account, admin_database
):
    login(admin_client, account)
    with admin_database.session_factory.begin() as session:
        session.add(
            Student(id=uuid4(), full_name="Count Verification", phone_number="+250781234567")
        )
    response = admin_client.get(SUMMARY)
    assert response.status_code == 200
    assert response.json() == {
        "totalStudents": 1,
        "totalExamAttempts": None,
        "passedExams": None,
        "failedExams": None,
        "totalVerifiedRevenue": None,
        "activePromoCodes": None,
    }
    assert "phone" not in response.text and "Verification" not in response.text


@pytest.mark.parametrize("kind", ["absolute", "inactivity", "disabled"])
def test_admin_session_server_enforced_lifecycle(admin_client, account, admin_database, kind):
    _, token = login(admin_client, account)
    with admin_database.engine.begin() as connection:
        if kind == "absolute":
            connection.execute(
                text(
                    "UPDATE admin_sessions SET created_at=clock_timestamp()-interval '10 hours', "
                    "expires_at=clock_timestamp()-interval '1 minute', "
                    "last_activity_at=clock_timestamp()-interval '2 minutes'"
                )
            )
        elif kind == "inactivity":
            connection.execute(
                text(
                    "UPDATE admin_sessions SET created_at=clock_timestamp()-interval '2 hours', "
                    "last_activity_at=clock_timestamp()-interval '31 minutes'"
                )
            )
        else:
            connection.execute(update(AdminUser).values(is_active=False))
    assert admin_client.get(SUMMARY).status_code == 401
    admin_client.cookies.clear()
    admin_client.cookies.set("roadrules_admin", token, path=ADMIN_PATH)
    assert admin_client.get(ME).status_code == 401
    with admin_database.session_factory() as session:
        assert session.scalar(select(AdminSession.revoked_at)) is not None


def test_logout_revocation_and_login_rotation(admin_client, account, admin_database):
    _, old = login(admin_client, account)
    _, current = login(admin_client, account)
    assert current != old
    with admin_database.session_factory() as session:
        assert (
            session.scalar(
                select(AdminSession.revoked_at).where(
                    AdminSession.token_hash == hash_admin_token(old)
                )
            )
            is not None
        )
    response = admin_client.post(LOGOUT, headers=HEADERS)
    assert (
        response.status_code == 204
        and response.content == b""
        and "Max-Age=0" in response.headers["set-cookie"]
    )
    assert admin_client.post(LOGOUT, headers=HEADERS).status_code == 204
    admin_client.cookies.clear()
    admin_client.cookies.set("roadrules_admin", current, path=ADMIN_PATH)
    assert admin_client.get(ME).status_code == 401


def test_login_limits_persist_across_instances(admin_database, admin_settings, account):
    options = admin_settings.model_dump()
    options["admin_login_limit"] = 1
    settings = Settings(_env_file=None, **options)
    with TestClient(create_app(settings), base_url="http://localhost") as first:
        assert (
            first.post(
                LOGIN, headers=HEADERS, json={"email": account["email"], "password": "wrong"}
            ).status_code
            == 401
        )
    with TestClient(create_app(settings), base_url="http://localhost") as second:
        response = second.post(
            LOGIN,
            headers={**HEADERS, "X-Forwarded-For": "203.0.113.10"},
            json={"email": account["email"], "password": account["password"]},
        )
        assert response.status_code == 429 and response.headers["retry-after"] == "60"


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Origin": "http://localhost:3000"},
        {"Origin": "https://evil.example", "X-CSRF-Protection": "1"},
    ],
)
def test_csrf_guards_admin_login_and_logout(admin_client, account, headers):
    assert (
        admin_client.post(
            LOGIN,
            json={"email": account["email"], "password": account["password"]},
            headers=headers,
        ).status_code
        == 403
    )
    login(admin_client, account)
    assert admin_client.post(LOGOUT, headers=headers).status_code == 403
    assert admin_client.get(ME).status_code == 200


def test_no_public_signup_or_upload_endpoint(admin_client):
    for endpoint in ["/api/v1/admin/signup", "/api/v1/admin/users", "/api/v1/admin/pdf-uploads"]:
        assert admin_client.post(endpoint, json={}, headers=HEADERS).status_code == 404
