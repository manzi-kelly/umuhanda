import json
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pymupdf
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from app.core.session_security import InvalidGuestSession
from app.main import create_app
from app.models.exam_bank import (
    BankQuestion,
    BankRevision,
    ExamAttempt,
    ExamItem,
    ExamOperationalEvent,
)
from app.schemas.student_sessions import StudentSessionRequest
from app.services.exam_generation import ExamUnavailable, start_exam
from app.services.pdf.jobs import process_job
from app.services.student_sessions import StudentSessionService
from tests.integration.test_pdf_import import HEADERS, ROOT, job_id, upload
from tests.integration.test_pdf_import import environment as environment

pytestmark = pytest.mark.integration
STATUS = ROOT + "/exam-bank/status"


def fixture_pdf(
    size=40, *, variant="base", defects=False, quotas=False, columns=False, sign_interval=5
):
    pdf = pymupdf.open()
    for start in range(0, size, 6):
        page = pdf.new_page()
        for n in range(start, min(start + 6, size)):
            y = 48 + (n - start) * 125
            sign = n % sign_interval == 0
            prompt = (
                f"Synthetic {variant} road sign item {n}?"
                if sign
                else f"Synthetic {variant} item {n}?"
            )
            if defects and n in (6, 7):
                prompt = "Synthetic duplicate item?"
            x = 350 if columns and n == 1 else 40
            page.insert_text((x, y), f"{n + 1}. {prompt}")
            if quotas:
                group = ("HARD", "MEDIUM", "EASY")[n % 3]
                page.insert_text((40, y + 17), f"Difficulty: {group}")
            page.insert_text((40, y + 32), "A. Synthetic first choice")
            label = "C" if defects and n == 4 else "B"
            page.insert_text((40, y + 50), f"{label}. Synthetic second choice")
            if not (defects and n == 2):
                page.insert_text((40, y + 68), "Answer: A")
            if defects and n == 8:
                page.insert_text((40, y + 85), "Correct answer: A")
            if defects and n == 3:
                page.insert_text((40, y + 85), "Answer: B")
            if sign and not (defects and n == 5):
                page.draw_rect(pymupdf.Rect(360, y + 6, 402, y + 44), color=(1, 0, 0))
    data = pdf.tobytes()
    pdf.close()
    return data


def submit(environment, data, *, policy="UNSTRATIFIED", process=True):
    client, _, settings = environment
    response = upload(client, data)
    assert response.status_code == 202, response.text
    document = response.json()["document"]["id"]
    identifier = job_id(client, document)
    if process:
        assert process_job(
            settings.model_copy(update={"exam_selection_policy": policy}), identifier
        )
    return document, identifier


def guest(database, settings):
    with database.session_factory() as session:
        return StudentSessionService(session, settings).create(
            StudentSessionRequest(fullName="Synthetic Learner", phoneNumber="0781234567")
        )


def generate(database, settings, token, grant, owner):
    def verify(_session, entitlement_id, candidate):
        if entitlement_id != grant or candidate.id != owner:
            raise PermissionError("Invalid test grant")

    with database.session_factory() as session:
        return start_exam(session, settings, token, grant, verify_entitlement=verify)


def test_auto_eligibility_and_evidence(environment):
    client, database, _ = environment
    document, _ = submit(environment, fixture_pdf(defects=True))
    status = client.get(STATUS).json()
    assert status["ready"] and status["activeDocumentId"] == document
    counts = status["documents"][0]["counts"]
    assert counts["ELIGIBLE"] == 33
    assert counts["INELIGIBLE_MISSING_ANSWER"] == 1
    assert counts["INELIGIBLE_AMBIGUOUS_ANSWER"] == 1
    assert counts["INELIGIBLE_INCOMPLETE_OPTIONS"] == 1
    assert counts["INELIGIBLE_IMAGE_ERROR"] == 1
    assert counts["INELIGIBLE_EXTRACTION_ERROR"] == 3
    with database.session_factory() as session:
        sign = session.scalar(select(BankQuestion).where(BankQuestion.source_order == 1))
        assert sign.source_page == 1 and sign.category == "ROAD_SIGN" and sign.assets
        assert sign.answer_evidence["segments"][0]["text"] == "Answer: A"
        assert sign.correct_index == 0 and sign.difficulty is None


def test_replacement_and_snapshot_history(environment):
    client, database, settings = environment
    first, _ = submit(environment, fixture_pdf())
    old = client.get(STATUS).json()["activeRevisionId"]
    identity, token = guest(database, settings)
    grant = uuid4()
    snapshot = generate(database, settings, token, grant, identity.sessionReference)
    assert len(snapshot["questions"]) == 20
    assert len({q["id"] for q in snapshot["questions"]}) == 20
    assert 0 < sum(q["imageCount"] > 0 for q in snapshot["questions"]) < 20
    assert set(snapshot["questions"][0]) == {"id", "text", "position", "options", "imageCount"}
    assert "Answer: A" not in json.dumps(snapshot) and "storage_key" not in json.dumps(snapshot)
    pending, _ = submit(environment, fixture_pdf(2, variant="small"), process=False)
    assert client.get(STATUS).json()["activeDocumentId"] == first
    assert process_job(settings, job_id(client, pending))
    assert client.get(STATUS).json()["activeRevisionId"] == old
    submit(environment, fixture_pdf(40, variant="columns", columns=True))
    status = client.get(STATUS).json()
    assert status["activeRevisionId"] == old
    assert status["documents"][0]["bankStatus"] == "EXTRACTION_IMPROVEMENTS_REQUIRED"
    replacement, _ = submit(environment, fixture_pdf(41))
    assert client.get(STATUS).json()["activeDocumentId"] == replacement
    assert generate(database, settings, token, grant, identity.sessionReference) == snapshot
    second = generate(database, settings, token, uuid4(), identity.sessionReference)
    assert second["revisionId"] != old
    assert {q["text"] for q in second["questions"]}.isdisjoint(
        q["text"] for q in snapshot["questions"]
    )
    assert isinstance(
        generate(database, settings, token, uuid4(), identity.sessionReference), ExamUnavailable
    )
    with pytest.raises(IntegrityError), database.session_factory.begin() as session:
        session.execute(text("UPDATE exam_bank_questions SET question_text = 'changed'"))
    with pytest.raises(IntegrityError), database.session_factory.begin() as session:
        session.execute(text("DELETE FROM exam_attempt_items"))


def test_no_bank_no_eligible_and_authorization_boundary(environment):
    client, database, settings = environment
    identity, token = guest(database, settings)
    grant = uuid4()
    assert generate(database, settings, token, grant, identity.sessionReference) == ExamUnavailable(
        "NO_ACTIVE_BANK"
    )
    with pytest.raises(InvalidGuestSession):
        generate(database, settings, None, grant, identity.sessionReference)
    with pytest.raises(PermissionError):
        generate(database, settings, token, grant, uuid4())
    submit(environment, fixture_pdf(1, defects=True, variant="strict"), policy="DIFFICULTY_QUOTAS")
    assert not client.get(STATUS).json()["ready"]
    with database.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(ExamAttempt)) == 0
        assert session.scalar(select(func.count()).select_from(ExamOperationalEvent)) == 1
    with TestClient(create_app(settings), base_url="http://localhost") as public:
        assert public.get(STATUS).status_code == 401
        assert (
            public.post(
                "/api/v1/exams/start",
                headers={"Origin": "http://localhost:3000", "X-CSRF-Protection": "1"},
                json={"entitlementId": str(grant)},
            ).status_code
            == 401
        )


def test_concurrent_same_grant_is_idempotent_and_difficulty_quotas(environment):
    _, database, settings = environment
    submit(environment, fixture_pdf(30, quotas=True), policy="DIFFICULTY_QUOTAS")
    identity, token = guest(database, settings)
    grant = uuid4()
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(
            pool.map(
                lambda _: generate(database, settings, token, grant, identity.sessionReference),
                range(4),
            )
        )
    assert all(result == results[0] for result in results)
    assert results[0]["policy"] == "DIFFICULTY_QUOTAS"
    with database.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(ExamAttempt)) == 1
        rows = session.execute(
            select(BankQuestion.difficulty, func.count())
            .join(ExamItem, ExamItem.question_id == BankQuestion.id)
            .group_by(BankQuestion.difficulty)
        )
        assert dict(rows.all()) == {"HARD": 7, "MEDIUM": 4, "EASY": 9}
        assert (
            session.scalar(
                select(func.count()).select_from(BankRevision).where(BankRevision.active)
            )
            == 1
        )
    other, other_token = guest(database, settings)
    with pytest.raises(PermissionError):
        generate(database, settings, other_token, grant, other.sessionReference)


def test_strict_policy_and_zero_eligible(environment):
    client, _, _ = environment
    submit(environment, fixture_pdf(), policy="DIFFICULTY_QUOTAS")
    status = client.get(STATUS).json()
    assert not status["ready"] and status["documents"][0]["counts"]["ELIGIBLE"] == 40
    source = pymupdf.open()
    page = source.new_page()
    page.insert_text((40, 50), "1. Synthetic item without an answer?")
    page.insert_text((40, 80), "A. First")
    page.insert_text((40, 110), "B. Second")
    submit(environment, source.tobytes())
    source.close()
    status = client.get(STATUS).json()
    assert not status["ready"]
    assert status["documents"][0]["counts"] == {
        "extracted": 1,
        "road_sign": 0,
        "INELIGIBLE_MISSING_ANSWER": 1,
        "difficulty": {"HARD": 0, "MEDIUM": 0, "EASY": 0},
    }


def test_reprocess_existing_source_after_explicit_policy_change(environment):
    client, _, settings = environment
    document, job = submit(environment, fixture_pdf(), policy="DIFFICULTY_QUOTAS")
    assert not client.get(STATUS).json()["ready"]
    retry = client.post(ROOT + f"/pdf-import-jobs/{job}/retry", headers=HEADERS)
    assert retry.status_code == 202
    assert process_job(settings.model_copy(update={"exam_selection_policy": "UNSTRATIFIED"}), job)
    status = client.get(STATUS).json()
    assert status["activeDocumentId"] == document and status["policy"] == "UNSTRATIFIED"
