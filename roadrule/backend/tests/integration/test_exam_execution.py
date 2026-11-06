import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from app.main import create_app
from app.models.exam_access import ExamEntitlement
from app.models.exam_bank import BankRevision, ExamAttempt, ExamItem
from app.models.exam_execution import ExamResponse
from tests.integration.test_exam_access import HEADERS, REDEEM, client_for, make_promo
from tests.integration.test_exam_bank import fixture_pdf, guest, submit
from tests.integration.test_pdf_import import environment as environment

pytestmark = pytest.mark.integration
BASE = "/api/v1/exams"


def prepared(environment):
    admin, database, settings = environment
    submit(environment, fixture_pdf(45))
    _, token = guest(database, settings)
    code = make_promo(admin)["code"]
    with client_for(settings, token) as client:
        result = client.post(REDEEM, headers=HEADERS, json={"code": code})
        assert result.status_code == 200
    return token, result.json()["id"]


def begin(client, identifier):
    response = client.post(BASE + "/start", headers=HEADERS, json={"entitlementId": identifier})
    assert response.status_code == 200, response.text
    return response.json()["exam"]


def clock_at(monkeypatch, exam):
    started = datetime.fromisoformat(exam["startedAt"])
    instant = [started]
    monkeypatch.setattr("app.api.v1.exam_execution.now", lambda _: instant[0])
    return started, instant


def test_authorized_start_and_concurrent_idempotence(environment):
    _, database, settings = environment
    token, grant = prepared(environment)

    def start(_):
        with client_for(settings, token) as client:
            return begin(client, grant)

    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(start, range(3)))
    assert len({r["id"] for r in results}) == 1
    result = results[0]
    assert result["position"] == 1 and result["total"] == 20
    assert set(result["question"]) == {
        "text",
        "options",
        "deadline",
        "selectedOption",
        "answerVersion",
        "images",
    }
    assert set(result["question"]["options"][0]) == {"id", "label", "text"}
    assert "Answer: A" not in json.dumps(result) and "storage_key" not in json.dumps(result)
    assert datetime.fromisoformat(result["globalDeadline"]) - datetime.fromisoformat(
        result["startedAt"]
    ) == timedelta(minutes=20)
    with database.session_factory() as session:
        items = session.scalars(select(ExamItem).order_by(ExamItem.position)).all()
        assert [item.position for item in items] == list(range(1, 21))
        assert len({item.question_id for item in items}) == 20
        assert session.get(ExamEntitlement, UUID(grant)).status == "CONSUMED"
        assert session.scalar(select(func.count()).select_from(ExamAttempt)) == 1
    with pytest.raises(IntegrityError), database.session_factory.begin() as session:
        session.execute(text("UPDATE exam_attempt_items SET position=position"))


def test_ownership_csrf_and_unavailable_preserve_entitlement(environment):
    admin, database, settings = environment
    token, grant = prepared(environment)
    with TestClient(create_app(settings), base_url="http://localhost") as stranger:
        assert (
            stranger.post(
                BASE + "/start", headers=HEADERS, json={"entitlementId": grant}
            ).status_code
            == 401
        )
    with client_for(settings, token) as client:
        assert client.post(BASE + "/start", json={"entitlementId": grant}).status_code == 403
        assert (
            client.post(
                BASE + "/start", headers=HEADERS, json={"entitlementId": str(uuid4())}
            ).status_code
            == 403
        )
        with database.session_factory.begin() as session:
            active = session.scalar(select(BankRevision).where(BankRevision.active))
            revision = active.id
            active.active = False
        failure = client.post(BASE + "/start", headers=HEADERS, json={"entitlementId": grant})
        assert failure.status_code == 503 and failure.json()["error"]["code"] == "EXAM_UNAVAILABLE"
        assert (
            client.get("/api/v1/exam-access/me").json()["entitlements"][0]["status"] == "AVAILABLE"
        )
        with database.session_factory.begin() as session:
            session.get(BankRevision, revision).active = True
        exam = begin(client, grant)
        _, other = guest(database, settings)
        with client_for(settings, other) as stranger:
            root = BASE + f"/{exam['id']}"
            assert stranger.get(root + "/current").status_code == 404
            assert stranger.get(root + "/media/1/0").status_code == 404
            assert (
                stranger.put(
                    root + "/answer",
                    headers=HEADERS,
                    json={"position": 1, "optionId": 0, "answerVersion": 0},
                ).status_code
                == 404
            )
        stats = admin.get("/api/v1/admin/exam-execution/summary").json()
        assert stats == {"active": 1, "completed": 0, "timeExpired": 0, "startFailures": 1}


def test_answer_version_refresh_and_concurrent_next(environment, monkeypatch):
    _, database, settings = environment
    token, grant = prepared(environment)
    with client_for(settings, token) as client:
        exam = begin(client, grant)
        start, instant = clock_at(monkeypatch, exam)
        root = BASE + f"/{exam['id']}"
        instant[0] = start + timedelta(seconds=10)
        body = {"position": 1, "optionId": 0, "answerVersion": 0}
        assert (
            client.put(root + "/answer", headers=HEADERS, json={**body, "score": 1}).status_code
            == 422
        )
        assert client.put(root + "/answer", json=body).status_code == 403
        assert (
            client.put(root + "/answer", headers=HEADERS, json={**body, "optionId": 3}).status_code
            == 422
        )
        assert (
            client.put(root + "/answer", headers=HEADERS, json={**body, "position": 2}).status_code
            == 409
        )
        saved = client.put(root + "/answer", headers=HEADERS, json=body).json()["exam"]
        assert saved["question"]["selectedOption"] == 0 and saved["question"]["answerVersion"] == 1
        assert client.put(root + "/answer", headers=HEADERS, json=body).json()["exam"] == saved
        assert (
            client.put(root + "/answer", headers=HEADERS, json={**body, "optionId": 1}).status_code
            == 409
        )
        assert client.get(BASE + "/me").json()["exam"] == saved

    def advance(_):
        with client_for(settings, token) as client:
            return client.post(root + "/next", headers=HEADERS, json={"position": 1})

    with ThreadPoolExecutor(max_workers=2) as pool:
        advances = sorted(pool.map(advance, range(2)), key=lambda response: response.status_code)
        assert [response.status_code for response in advances] == [200, 409]
        assert advances[0].json()["exam"]["question"]["answerVersion"] == 0
    with client_for(settings, token) as client:
        second = client.get(root + "/current").json()["exam"]
        assert second["position"] == 2 and second["globalDeadline"] == exam["globalDeadline"]
        assert datetime.fromisoformat(second["question"]["deadline"]) == start + timedelta(
            seconds=70
        )
        assert client.put(root + "/answer", headers=HEADERS, json=body).status_code == 409
    with database.session_factory() as session:
        first = session.get(ExamResponse, (UUID(exam["id"]), 1))
        assert first.selected_option == 0 and first.closed_by == "NEXT"
    with pytest.raises(IntegrityError), database.session_factory.begin() as session:
        session.execute(text("UPDATE exam_responses SET selected_option=NULL WHERE position=1"))


def test_exact_deadlines_offline_reconciliation_and_idempotent_finish(environment, monkeypatch):
    _, database, settings = environment
    token, grant = prepared(environment)
    with client_for(settings, token) as client:
        exam = begin(client, grant)
        start, instant = clock_at(monkeypatch, exam)
        root = BASE + f"/{exam['id']}"
        instant[0] = start + timedelta(seconds=59)
        assert (
            client.put(
                root + "/answer",
                headers=HEADERS,
                json={"position": 1, "optionId": 1, "answerVersion": 0},
            ).status_code
            == 200
        )
        instant[0] = start + timedelta(seconds=60)
        assert (
            client.put(
                root + "/answer",
                headers=HEADERS,
                json={"position": 1, "optionId": 0, "answerVersion": 1},
            ).status_code
            == 409
        )
        instant[0] = start + timedelta(minutes=18)
        warning = client.get(root + "/current").json()["exam"]
        assert warning["position"] == 19 and warning["serverNow"] == warning["warningAt"]
        instant[0] = start + timedelta(minutes=20, seconds=5)
        finished = client.get(root + "/current").json()["exam"]
        assert finished["status"] == "COMPLETED" and finished["question"] is None
        assert finished["completionReason"] == "GLOBAL_TIME_EXPIRED"
        assert finished["completedAt"] == finished["globalDeadline"]
        assert (
            client.post(root + "/next", headers=HEADERS, json={"position": 20}).json()["exam"]
            == finished
        )
        assert (
            client.put(
                root + "/answer",
                headers=HEADERS,
                json={"position": 20, "optionId": 0, "answerVersion": 0},
            ).status_code
            == 409
        )
    with database.session_factory() as session:
        responses = session.scalars(select(ExamResponse).order_by(ExamResponse.position)).all()
        grade = session.execute(
            text("SELECT correct, incorrect, unanswered FROM exam_results")
        ).one()
        assert tuple(grade) == (0, 1, 19)
        assert len(responses) == 20 and responses[0].selected_option == 1
        assert all(row.finalized_at is not None for row in responses)
        assert responses[-1].closed_by == "GLOBAL"


def test_twentieth_next_finishes_and_media_is_current_only(environment, monkeypatch):
    _, _, settings = environment
    token, grant = prepared(environment)
    with client_for(settings, token) as client:
        exam = begin(client, grant)
        start, instant = clock_at(monkeypatch, exam)
        root = BASE + f"/{exam['id']}"
        assert client.get(root + "/media/2/0").status_code == 404
        seen_image = False
        for position in range(1, 21):
            assert exam["position"] == position
            if exam["question"]["images"]:
                path = "/api/v1/" + exam["question"]["images"][0]
                asset = client.get(path)
                assert asset.status_code == 200 and asset.headers["content-type"] == "image/png"
                seen_image = True
            else:
                path = None
            instant[0] = start + timedelta(seconds=position)
            exam = client.post(root + "/next", headers=HEADERS, json={"position": position}).json()[
                "exam"
            ]
            if path:
                assert client.get(path).status_code == 404
        assert seen_image and exam["completionReason"] == "ALL_QUESTIONS_FINISHED"
        assert exam["question"] is None


@pytest.mark.parametrize("correct", [0, 11, 12, 20])
def test_result_thresholds_and_scope(environment, monkeypatch, correct):
    admin, database, settings = environment
    token, grant = prepared(environment)
    with client_for(settings, token) as client:
        exam = begin(client, grant)
        start, instant = clock_at(monkeypatch, exam)
        root = BASE + f"/{exam['id']}"
        history = "/api/v1/students/exams/history"
        assert client.get(root + "/result").status_code == 409
        assert client.get(history).json() == []
        assert client.get("/api/v1/admin/exam-results/stats").status_code == 401
        for position in range(1, 21):
            instant[0] = start + timedelta(seconds=position)
            if position <= correct:
                saved = client.put(
                    root + "/answer",
                    headers=HEADERS,
                    json={"position": position, "optionId": 0, "answerVersion": 0},
                )
                assert saved.status_code == 200
            assert (
                client.post(
                    root + "/next", headers=HEADERS, json={"position": position}
                ).status_code
                == 200
            )
        result = client.get(root + "/result").json()
        assert result["score"] == result["correct"] == correct
        assert result["unanswered"] == 20 - correct and result["incorrect"] == 0
        assert result["percentage"] == correct * 5
        assert result["status"] == ("PASSED" if correct >= 12 else "FAILED")
        assert result["attemptId"] == exam["id"]
        assert client.get(history).json() == [result]
        assert client.get(history + "?offset=1").json() == []
        assert begin(client, grant)["id"] == exam["id"]
        assert client.get(root + "/result").json() == result
    _, other = guest(database, settings)
    with client_for(settings, other) as stranger:
        assert stranger.get(root + "/result").status_code == 404
        assert stranger.get(history).json() == []
    stats = admin.get("/api/v1/admin/exam-results/stats?period=yearly").json()
    assert stats["completed"] == 1 and stats["averageScore"] == correct
    assert stats["passPercentage"] == (100 if correct >= 12 else 0)
    listing = admin.get(
        "/api/v1/admin/exam-results",
        params={"search": result["studentName"], "status": result["status"]},
    ).json()
    assert listing["items"][0]["result"] == result and not listing["hasMore"]
    assert admin.get(f"/api/v1/admin/exam-results/{exam['id']}").json()["result"] == result
    with pytest.raises(IntegrityError), database.session_factory.begin() as session:
        session.execute(text("UPDATE exam_results SET correct = correct"))
    with pytest.raises(IntegrityError), database.session_factory.begin() as session:
        session.execute(text("INSERT INTO exam_results SELECT * FROM exam_results"))


def test_simultaneous_completion_and_grading_rollback(environment, monkeypatch):
    from sqlalchemy.exc import OperationalError

    from app.services import exam_execution

    _, database, settings = environment
    token, grant = prepared(environment)
    original = exam_execution.grade_completed

    def fail(session, attempt, timing):
        original(session, attempt, timing)
        session.flush()
        raise OperationalError(None, None, Exception("simulated grading write failure"))

    with client_for(settings, token) as client:
        exam = begin(client, grant)
        started, instant = clock_at(monkeypatch, exam)
        root = BASE + f"/{exam['id']}"
        instant[0] = started + timedelta(minutes=21)
        monkeypatch.setattr(exam_execution, "grade_completed", fail)
        assert client.get(root + "/result").status_code == 503
    with database.session_factory() as session:
        assert session.get(ExamAttempt, UUID(exam["id"])).status == "STARTED"
        assert session.scalar(text("SELECT count(*) FROM exam_results")) == 0
        assert session.scalar(text("SELECT count(*) FROM exam_responses")) == 1
    monkeypatch.setattr(exam_execution, "grade_completed", original)

    def read(_):
        with client_for(settings, token) as client:
            response = client.get(root + "/result")
            assert response.status_code == 200
            return response.json()

    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(read, range(3)))
    assert results[0] == results[1] == results[2]
    assert results[0]["score"] == 0 and results[0]["unanswered"] == 20
    with database.session_factory() as session:
        assert session.scalar(text("SELECT count(*) FROM exam_results")) == 1


def test_corrupt_snapshot_preserves_completion(environment, monkeypatch):
    from sqlalchemy import event
    from sqlalchemy.orm.attributes import set_committed_value

    from app.models.exam_bank import BankQuestion

    admin, database, settings = environment
    token, grant = prepared(environment)
    with client_for(settings, token) as client:
        exam = begin(client, grant)
        started, instant = clock_at(monkeypatch, exam)
        instant[0] = started + timedelta(minutes=21)
        root = BASE + f"/{exam['id']}"

        def corrupt(question, _context):
            set_committed_value(question, "correct_index", None)

        event.listen(BankQuestion, "load", corrupt)
        try:
            response = client.get(root + "/result")
        finally:
            event.remove(BankQuestion, "load", corrupt)
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "EXAM_RESULT_UNAVAILABLE"
        assert client.get(root + "/current").json()["exam"]["status"] == "COMPLETED"
        assert client.get(root + "/result").status_code == 503
    with database.session_factory() as session:
        assert session.scalar(text("SELECT count(*) FROM exam_results")) == 0
        assert session.scalar(text("SELECT count(*) FROM exam_grading_failures")) == 1
    detail = admin.get(f"/api/v1/admin/exam-results/{exam['id']}").json()
    assert detail["gradingIssue"] and detail["result"] is None
