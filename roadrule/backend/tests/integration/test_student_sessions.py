from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, inspect, select, text
from sqlalchemy.exc import IntegrityError

from alembic import command
from app.core.config import Settings
from app.core.session_security import COOKIE_PATH, hash_token, new_token
from app.main import create_app
from app.models import GuestSession, Student, StudentActivityEvent
from app.repositories.student_sessions import StudentSessionRepository

pytestmark = pytest.mark.integration
PATH = "/api/v1/students/sessions"
HEADERS = {"Origin": "http://localhost:3000", "X-CSRF-Protection": "1"}
PAYLOAD = {"fullName": "  Jean   Claude  ", "phoneNumber": "0781234567"}


@pytest.fixture
def session_database(database, migration_config):
    command.upgrade(migration_config, "head")

    def cleanup():
        with database.engine.begin() as connection:
            assert connection.execute(text("SELECT current_database(), current_user")).one() == (
                "roadrules_test",
                "roadrules_test_app",
            )
            assert set(inspect(connection).get_table_names()) == {
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
                "admin_users",
                "admin_sessions",
                "admin_audit_events",
                "students",
                "guest_sessions",
                "student_activity_events",
            }
            # No CASCADE: an unexpected external FK must fail rather than delete unrelated data.
            connection.execute(
                text(
                    "TRUNCATE refund_requests, exam_results, exam_grading_failures, "
                    "exam_responses, exam_timing, exam_entitlements, "
                    "payment_transactions, promo_attempts, "
                    "exam_attempt_items, exam_attempts, "
                    "student_activity_events, guest_sessions, students"
                )
            )

    cleanup()
    try:
        yield database
    finally:
        cleanup()


@pytest.fixture
def session_settings(integration_settings):
    return Settings(
        _env_file=None,
        app_env="testing",
        test_database_url=integration_settings.test_database_url,
        cors_allowed_origins=["http://localhost:3000"],
    )


@pytest.fixture
def session_client(session_database, session_settings):
    with TestClient(
        create_app(session_settings), base_url="http://localhost", raise_server_exceptions=False
    ) as client:
        yield client


def create(client):
    response = client.post(PATH, json=PAYLOAD, headers=HEADERS)
    assert response.status_code == 201, response.text
    return response, client.cookies.get("roadrules_guest")


def counts(database):
    with database.engine.connect() as connection:
        return tuple(
            connection.scalar(select(func.count()).select_from(model))
            for model in (Student, GuestSession, StudentActivityEvent)
        )


def test_persistent_atomic_creation_and_only_hashed_token(session_client, session_database, caplog):
    response, token = create(session_client)
    body = response.json()
    assert set(body) == {
        "studentId",
        "sessionReference",
        "fullName",
        "maskedPhoneNumber",
        "expiresAt",
        "accessGranted",
    }
    assert body["fullName"] == "Jean Claude" and body["maskedPhoneNumber"] == "+25078*****67"
    assert body["accessGranted"] is False and body["expiresAt"].endswith("Z")
    assert token not in response.text and "+250781234567" not in response.text
    assert response.headers["cache-control"] == "no-store"
    with session_database.session_factory() as session:
        student = session.get(Student, UUID(body["studentId"]))
        guest = session.get(GuestSession, UUID(body["sessionReference"]))
        assert student.full_name == "Jean Claude" and student.phone_number == "+250781234567"
        assert guest.token_hash == hash_token(token) and guest.token_hash != token
        assert guest.student_id == student.id and guest.created_at.tzinfo is not None
        assert guest.expires_at > guest.created_at and guest.last_activity_at == guest.created_at
        events = session.scalars(select(StudentActivityEvent)).all()
        assert {row.event_type for row in events} == {"STUDENT_CREATED", "SESSION_CREATED"}
        assert set(StudentActivityEvent.__table__.columns.keys()) == {
            "id",
            "student_id",
            "guest_session_id",
            "event_type",
            "created_at",
        }
    assert token not in caplog.text and "+250781234567" not in caplog.text
    assert counts(session_database) == (1, 1, 2)


def test_same_phone_and_name_create_distinct_students(session_client):
    first, _ = create(session_client)
    second, _ = create(session_client)
    assert first.json()["studentId"] != second.json()["studentId"]
    assert first.json()["sessionReference"] != second.json()["sessionReference"]


@pytest.mark.parametrize(
    "payload",
    [
        {"fullName": " ", "phoneNumber": "0781234567"},
        {"fullName": "Jean123", "phoneNumber": "0781234567"},
        {"fullName": "Jean", "phoneNumber": "0251234567"},
        {**PAYLOAD, "studentId": str(uuid4())},
        {**PAYLOAD, "accessGranted": True},
    ],
)
def test_invalid_creation_never_persists(session_client, session_database, payload):
    response = session_client.post(PATH, json=payload, headers=HEADERS)
    assert response.status_code == 422 and "set-cookie" not in response.headers
    assert counts(session_database) == (0, 0, 0)


def test_failure_after_student_and_session_flush_rolls_everything_back(
    session_client, session_database, monkeypatch
):
    original = StudentSessionRepository.add

    def fail_audit(self, record):
        if isinstance(record, StudentActivityEvent):
            raise RuntimeError("private-internal-detail")
        return original(self, record)

    monkeypatch.setattr(StudentSessionRepository, "add", fail_audit)
    response = session_client.post(PATH, json=PAYLOAD, headers=HEADERS)
    assert response.status_code == 500 and "private" not in response.text
    assert "set-cookie" not in response.headers and counts(session_database) == (0, 0, 0)


def test_cookie_authentication_and_no_uuid_or_bearer_authorization(session_client):
    created, token = create(session_client)
    response = session_client.get(PATH + "/me", headers={"Origin": HEADERS["Origin"]})
    assert response.status_code == 200 and response.json() == created.json()
    session_client.cookies.clear()
    assert session_client.get(PATH + "/me").status_code == 401
    assert (
        session_client.get(PATH + "/me", headers={"Authorization": f"Bearer {token}"}).status_code
        == 401
    )
    for value in (
        created.json()["studentId"],
        created.json()["sessionReference"],
        new_token(),
        "malformed",
    ):
        session_client.cookies.set("roadrules_guest", value, path=COOKIE_PATH)
        assert session_client.get(PATH + "/me").status_code == 401
        session_client.cookies.clear()
    assert (
        session_client.get(PATH + "/me?token=" + created.json()["sessionReference"]).status_code
        == 401
    )
    assert session_client.get("/api/v1/students/" + created.json()["studentId"]).status_code == 404


def test_session_persists_across_fresh_application_instance(session_client):
    created, token = create(session_client)
    with TestClient(
        create_app(session_client.app.state.settings), base_url="http://localhost"
    ) as fresh:
        fresh.cookies.set("roadrules_guest", token, path=COOKIE_PATH)
        response = fresh.get(PATH + "/me")
        assert response.status_code == 200 and response.json() == created.json()


@pytest.mark.parametrize("case", ["plaintext", "duplicate_hash", "orphan"])
def test_database_token_and_foreign_key_constraints(session_client, session_database, case):
    create(session_client)
    with session_database.session_factory() as session:
        existing = session.scalar(select(GuestSession))
    with pytest.raises(IntegrityError), session_database.session_factory.begin() as session:
        session.add(
            GuestSession(
                id=uuid4(),
                student_id=uuid4() if case == "orphan" else existing.student_id,
                # A rejected row can appear in PostgreSQL DETAIL logs. Never use a live
                # credential as an intentionally invalid database value, even in tests.
                token_hash="not-a-credential"
                if case == "plaintext"
                else (existing.token_hash if case == "duplicate_hash" else hash_token(new_token())),
                created_at=existing.created_at,
                expires_at=existing.expires_at,
                last_activity_at=existing.last_activity_at,
            )
        )
    assert counts(session_database) == (1, 1, 2)


@pytest.mark.parametrize("expiration", ["absolute", "inactive"])
def test_server_expiration_and_one_time_audit(session_client, session_database, expiration):
    created, token = create(session_client)
    with session_database.engine.begin() as connection:
        if expiration == "absolute":
            connection.execute(
                text(
                    "UPDATE guest_sessions SET created_at=clock_timestamp()-interval '3 hours', "
                    "last_activity_at=clock_timestamp()-interval '2 minutes', "
                    "expires_at=clock_timestamp()-interval '1 minute'"
                )
            )
        else:
            connection.execute(
                text(
                    "UPDATE guest_sessions SET created_at=clock_timestamp()-interval '2 hours', "
                    "last_activity_at=clock_timestamp()-interval '31 minutes'"
                )
            )
    for _ in range(2):
        session_client.cookies.clear()
        session_client.cookies.set("roadrules_guest", token, path=COOKIE_PATH)
        rejected = session_client.get(PATH + "/me")
        assert rejected.status_code == 401 and token not in rejected.text
    with session_database.session_factory() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(StudentActivityEvent)
                .where(StudentActivityEvent.event_type == "SESSION_EXPIRED")
            )
            == 1
        )


def test_activity_update_is_throttled_and_never_extends_absolute_expiry(
    session_client, session_database
):
    created, _ = create(session_client)

    def read():
        with session_database.engine.connect() as connection:
            return connection.execute(
                text("SELECT last_activity_at, expires_at FROM guest_sessions")
            ).one()

    initial = read()
    assert session_client.get(PATH + "/me").status_code == 200
    assert read() == initial
    with session_database.engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE guest_sessions SET created_at=clock_timestamp()-interval '3 minutes', "
                "last_activity_at=clock_timestamp()-interval '2 minutes'"
            )
        )
    older = read()
    assert session_client.get(PATH + "/me").status_code == 200
    touched = read()
    assert touched[0] > older[0] and touched[1] == initial[1]
    assert session_client.get(PATH + "/me").status_code == 200 and read() == touched


def test_revocation_is_persistent_idempotent_and_old_credential_cannot_replay(
    session_client, session_database
):
    _, token = create(session_client)
    response = session_client.post(PATH + "/revoke", headers=HEADERS)
    assert response.status_code == 204 and response.content == b""
    assert (
        "Max-Age=0" in response.headers["set-cookie"]
        and "Path=/api/v1" in response.headers["set-cookie"]
    )
    assert session_client.post(PATH + "/revoke", headers=HEADERS).status_code == 204
    session_client.cookies.set("roadrules_guest", token, path=COOKIE_PATH)
    assert session_client.post(PATH + "/revoke", headers=HEADERS).status_code == 204
    session_client.cookies.set("roadrules_guest", token, path=COOKIE_PATH)
    assert session_client.get(PATH + "/me").status_code == 401
    with session_database.session_factory() as session:
        assert session.scalar(select(GuestSession.revoked_at)) is not None
        assert (
            session.scalar(
                select(func.count())
                .select_from(StudentActivityEvent)
                .where(StudentActivityEvent.event_type == "SESSION_REVOKED")
            )
            == 1
        )


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Origin": "null", "X-CSRF-Protection": "1"},
        {"Origin": "http://evil.example", "X-CSRF-Protection": "1"},
        {"Origin": "http://localhost:3000"},
        {**HEADERS, "Sec-Fetch-Site": "cross-site"},
    ],
)
def test_csrf_blocks_creation_before_any_database_write(session_client, session_database, headers):
    assert session_client.post(PATH, json=PAYLOAD, headers=headers).status_code == 403
    assert counts(session_database) == (0, 0, 0)


def test_csrf_blocks_revoke_and_wrong_origin_read(session_client, session_database):
    create(session_client)
    assert session_client.post(PATH + "/revoke").status_code == 403
    assert (
        session_client.get(PATH + "/me", headers={"Origin": "https://evil.example"}).status_code
        == 403
    )
    assert session_client.get(PATH + "/me").status_code == 200
    response = session_client.options(
        PATH,
        headers={
            "Origin": HEADERS["Origin"],
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,x-csrf-protection",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-credentials"] == "true"
    assert response.headers["access-control-allow-origin"] == HEADERS["Origin"]


def test_shared_durable_rate_limit_ignores_spoofed_ip_headers(session_database, session_settings):
    options = session_settings.model_dump()
    options["session_creation_limit"] = 1
    settings = Settings(_env_file=None, **options)
    with TestClient(create_app(settings), base_url="http://localhost") as first:
        with TestClient(create_app(settings), base_url="http://localhost") as second:
            assert first.post(PATH, json=PAYLOAD, headers=HEADERS).status_code == 201
            limited = second.post(
                PATH,
                json=PAYLOAD,
                headers={**HEADERS, "X-Forwarded-For": "203.0.113.1", "X-Real-IP": "203.0.113.2"},
            )
            assert limited.status_code == 429 and limited.headers["retry-after"] == "60"
    assert counts(session_database) == (1, 1, 2)


def test_concurrent_creations_share_one_budget(session_database, session_settings):
    options = session_settings.model_dump()
    options["session_creation_limit"] = 1
    settings = Settings(_env_file=None, **options)
    with TestClient(create_app(settings), base_url="http://localhost") as first:
        with TestClient(create_app(settings), base_url="http://localhost") as second:
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(
                    pool.map(
                        lambda client: client.post(PATH, json=PAYLOAD, headers=HEADERS).status_code,
                        [first, second],
                    )
                )
    assert sorted(results) == [201, 429] and counts(session_database) == (1, 1, 2)


def test_creation_budget_recovers_using_database_window(session_database, session_settings):
    options = session_settings.model_dump()
    options["session_creation_limit"] = 1
    with TestClient(
        create_app(Settings(_env_file=None, **options)), base_url="http://localhost"
    ) as client:
        create(client)
        assert client.post(PATH, json=PAYLOAD, headers=HEADERS).status_code == 429
        with session_database.engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE student_activity_events "
                    "SET created_at=clock_timestamp()-interval '2 minutes' "
                    "WHERE event_type='SESSION_CREATED'"
                )
            )
        assert client.post(PATH, json=PAYLOAD, headers=HEADERS).status_code == 201


@pytest.mark.parametrize(
    "values",
    [
        {"full_name": " ", "phone_number": "+250781234567"},
        {"full_name": "Jean", "phone_number": "0781234567"},
        {"full_name": "Jean123", "phone_number": "+250781234567"},
    ],
)
def test_database_constraints_reject_bypassing_request_schema(session_database, values):
    with pytest.raises(IntegrityError), session_database.session_factory.begin() as session:
        session.add(Student(id=uuid4(), **values))


def test_guest_session_cannot_authorize_payment_or_exam(session_client):
    response, _ = create(session_client)
    assert response.json()["accessGranted"] is False
    assert (
        session_client.get(PATH + "/me?accessGranted=true&status=SUCCESS").json()["accessGranted"]
        is False
    )
    for endpoint in ("/api/v1/exam", "/api/v1/payments/initiate"):
        assert session_client.post(endpoint, headers=HEADERS).status_code == 404
    promo = "/api/v1/promos/redeem"
    assert session_client.post(promo, json={"code": "invalid"}).status_code == 403
    assert session_client.post(promo, headers=HEADERS, json={"code": "invalid"}).status_code == 422
    assert session_client.get("/api/v1/exam-access/me").json()["entitlements"] == []


def test_failed_revocation_does_not_claim_success(session_client, session_database, monkeypatch):
    create(session_client)
    original = StudentSessionRepository.add

    def fail_event(self, record):
        if isinstance(record, StudentActivityEvent) and record.event_type == "SESSION_REVOKED":
            raise RuntimeError("redacted internal failure")
        return original(self, record)

    monkeypatch.setattr(StudentSessionRepository, "add", fail_event)
    response = session_client.post(PATH + "/revoke", headers=HEADERS)
    assert response.status_code == 500 and "set-cookie" not in response.headers
    with session_database.session_factory() as session:
        assert session.scalar(select(GuestSession.revoked_at)) is None
    assert session_client.get(PATH + "/me").status_code == 200


def test_expiration_audit_is_unique_under_concurrent_replay(session_client, session_database):
    from fastapi.testclient import TestClient

    from app.main import create_app

    _, token = create(session_client)
    with session_database.engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE guest_sessions SET created_at=clock_timestamp()-interval '2 hours', "
                "last_activity_at=clock_timestamp()-interval '31 minutes'"
            )
        )
    with TestClient(
        create_app(session_client.app.state.settings), base_url="http://localhost"
    ) as other:
        other.cookies.set("roadrules_guest", token, path=COOKIE_PATH)
        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(
                pool.map(
                    lambda client: client.get(PATH + "/me").status_code, [session_client, other]
                )
            )
    assert statuses == [401, 401]
    with session_database.session_factory() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(StudentActivityEvent)
                .where(StudentActivityEvent.event_type == "SESSION_EXPIRED")
            )
            == 1
        )


def test_audit_survives_identity_deletion_without_pii(session_client, session_database):
    response, _ = create(session_client)
    with session_database.session_factory.begin() as session:
        session.delete(session.get(Student, UUID(response.json()["studentId"])))
    with session_database.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(GuestSession)) == 0
        events = session.scalars(select(StudentActivityEvent)).all()
        assert len(events) == 2 and all(
            event.student_id is None and event.guest_session_id is None for event in events
        )
