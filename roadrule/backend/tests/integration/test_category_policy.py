import json
import os
from collections import Counter
from datetime import timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.models.exam_bank import BankQuestion, BankRevision, ExamAttempt, ExamItem
from app.models.exam_results import ExamResult
from app.models.pdf_import import PdfImportJob, QuestionDraft
from app.services.exam_generation import can_choose_questions, choose_questions
from app.services.pdf.jobs import process_job
from tests.integration.test_exam_access import HEADERS, REDEEM, client_for, make_promo
from tests.integration.test_exam_bank import fixture_pdf, guest, submit
from tests.integration.test_exam_execution import begin, clock_at
from tests.integration.test_pdf_import import environment as environment

pytestmark = pytest.mark.integration


def category_settings(settings, signs):
    return settings.model_copy(
        update={
            "exam_selection_policy": "CATEGORY_BALANCED",
            "exam_category_road_sign_count": signs,
        }
    )


def test_category_shortage_preserves_healthy_bank(environment):
    _, database, settings = environment
    submit(environment, fixture_pdf(42, sign_interval=2))
    with database.session_factory() as db:
        original = db.scalar(select(BankRevision.id).where(BankRevision.active))
    _, job = submit(environment, fixture_pdf(30, variant="shortage"), process=False)
    assert process_job(category_settings(settings, 10), job)
    with database.session_factory() as db:
        revision = db.scalar(select(BankRevision).where(BankRevision.job_id == job))
        assert revision.status == "INSUFFICIENT_CATEGORIES"
        assert db.scalar(select(BankRevision.id).where(BankRevision.active)) == original


def test_explicit_difficulty_policy_requires_source_classification(environment):
    _, database, settings = environment
    _, job = submit(environment, fixture_pdf(42, sign_interval=2), process=False)
    strict = settings.model_copy(update={"exam_selection_policy": "DIFFICULTY_BALANCED"})
    assert process_job(strict, job)
    with database.session_factory() as db:
        bank = db.scalar(select(BankRevision).where(BankRevision.job_id == job))
        assert bank.status == "INSUFFICIENT_DIFFICULTY" and not bank.active

    _, classified = submit(environment, fixture_pdf(30, quotas=True), process=False)
    assert process_job(strict, classified)
    with database.session_factory() as db:
        bank = db.scalar(select(BankRevision).where(BankRevision.job_id == classified))
        assert bank.status == "READY" and bank.active
        selected = choose_questions(db, bank, uuid4())
        assert Counter(item.difficulty for item in selected) == {"HARD": 7, "MEDIUM": 4, "EASY": 9}


def test_real_category_bank_and_timed_exam(environment, monkeypatch):
    source = os.getenv("PHASE04I_SOURCE_PDF")
    if not source or not Path(source).is_file():
        pytest.skip("Set PHASE04I_SOURCE_PDF to the local road-rules source.")
    admin, database, settings = environment
    _, job = submit(environment, Path(source).read_bytes(), process=False)
    assert process_job(category_settings(settings, 2), job)
    assert not process_job(category_settings(settings, 2), job)
    with database.session_factory() as db:
        bank = db.scalar(select(BankRevision).where(BankRevision.job_id == job))
        import_job = db.get(PdfImportJob, job)
        print(
            json.dumps(
                {"status": bank.status, "counts": bank.counts, "warnings": import_job.diagnostics},
                default=str,
            )
        )
        assert bank.active and bank.status == "READY"
        assert len(import_job.diagnostics) == 10
        assert all(item.get("scope") == "QUESTION_LOCAL" for item in import_job.diagnostics)
        assert bank.counts["category_targets"] == {"ROAD_SIGN": 2, "GENERAL": 18}
        duplicate_rows = db.execute(
            select(QuestionDraft, BankQuestion)
            .join(BankQuestion, BankQuestion.source_order == QuestionDraft.source_order)
            .where(
                QuestionDraft.import_job_id == job,
                QuestionDraft.source_question_number == "227",
                BankQuestion.revision_id == bank.id,
            )
        ).all()
        assert len(duplicate_rows) == 2
        assert {draft.source_page_number for draft, _ in duplicate_rows} == {63}
        assert len({question.id for _, question in duplicate_rows}) == 2
        assert all(question.correct_index is None for _, question in duplicate_rows)
        revision = bank.id
    _, token = guest(database, settings)
    with client_for(settings, token) as student:
        grant = student.post(REDEEM, headers=HEADERS, json={"code": make_promo(admin)["code"]})
        exam = begin(student, grant.json()["id"])
        root = f"/api/v1/exams/{exam['id']}"
        assert exam["total"] == 20
        with database.session_factory() as db:
            attempt = db.get(ExamAttempt, UUID(exam["id"]))
            assert attempt.revision_id == revision and attempt.policy == "CATEGORY_BALANCED"
            guest_id = attempt.guest_session_id
            snapshots = db.scalars(
                select(BankQuestion)
                .join(ExamItem, ExamItem.question_id == BankQuestion.id)
                .where(ExamItem.attempt_id == attempt.id)
                .order_by(ExamItem.position)
            ).all()
            assert len({item.fingerprint for item in snapshots}) == 20
            assert sum(item.category == "ROAD_SIGN" for item in snapshots) == 2
            assert all(
                item.correct_index is not None and item.answer_evidence for item in snapshots
            )
        started, instant = clock_at(monkeypatch, exam)
        instant[0] = started + timedelta(seconds=61)
        assert student.get(root + "/current").json()["exam"]["position"] == 2
        media_count = 0
        for position in range(2, 21):
            current = student.get(root + "/current").json()["exam"]
            question = current["question"]
            assert current["position"] == position
            assert set(question) == {
                "text",
                "options",
                "deadline",
                "selectedOption",
                "answerVersion",
                "images",
            }
            for path in question["images"] + [
                o["image"] for o in question["options"] if "image" in o
            ]:
                media = student.get("/api/v1/" + path)
                assert media.status_code == 200 and media.content.startswith(b"\x89PNG")
                media_count += 1
            answer = student.put(
                root + "/answer",
                headers=HEADERS,
                json={
                    "position": position,
                    "optionId": snapshots[position - 1].correct_index,
                    "answerVersion": 0,
                },
            )
            assert answer.status_code == 200
            assert (
                student.post(
                    root + "/next", headers=HEADERS, json={"position": position}
                ).status_code
                == 200
            )
        grade = student.get(root + "/result").json()
        assert grade["score"] == 19 and grade["status"] == "PASSED"
        with database.session_factory() as db:
            assert db.get(ExamResult, UUID(exam["id"])).correct == 19
        monkeypatch.undo()
        second_grant = student.post(
            REDEEM, headers=HEADERS, json={"code": make_promo(admin)["code"]}
        )
        retake = begin(student, second_grant.json()["id"])
        with database.session_factory() as db:
            second = db.scalars(
                select(BankQuestion)
                .join(ExamItem, ExamItem.question_id == BankQuestion.id)
                .where(ExamItem.attempt_id == UUID(retake["id"]))
            ).all()
            assert len(second) == 20 and sum(item.category == "ROAD_SIGN" for item in second) == 2
            assert not (
                {item.fingerprint for item in snapshots} & {item.fingerprint for item in second}
            )
            assert can_choose_questions(db, db.get(BankRevision, revision), guest_id)
        assert student.get(root + "/result").json() == grade
        print(
            json.dumps(
                {
                    "score": grade["score"],
                    "media_loaded": media_count,
                    "retake": True,
                    "third_pool_feasible": True,
                }
            )
        )
