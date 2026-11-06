"""PostgreSQL-time exam execution. Call under the authenticated guest row lock."""

import hashlib
from datetime import timedelta

from sqlalchemy import func, select

from app.models.exam_bank import BankQuestion, ExamAttempt, ExamItem
from app.models.exam_execution import ExamResponse, ExamTiming
from app.services.exam_access import AccessError, now
from app.services.exam_results import grade_completed
from app.services.pdf.storage import PdfError, PdfStorage

QUESTION_TIME = timedelta(seconds=60)
EXAM_TIME = timedelta(minutes=20)
WARNING_TIME = timedelta(minutes=18)
TOTAL = 20


def open_question(session, timing, timestamp):
    row = ExamResponse(
        attempt_id=timing.attempt_id,
        position=timing.position,
        started_at=timestamp,
        answer_version=0,
        deadline=min(timestamp + QUESTION_TIME, timing.global_deadline),
    )
    session.add(row)
    return row


def close_question(session, attempt, timing, current, timestamp, cause):
    current.finalized_at = timestamp
    current.closed_by = cause
    if timestamp >= timing.global_deadline or timing.position == TOTAL:
        attempt.status, attempt.ended_at = "COMPLETED", timestamp
        timing.completion_reason = (
            "GLOBAL_TIME_EXPIRED"
            if timestamp >= timing.global_deadline
            else "ALL_QUESTIONS_FINISHED"
        )
        grade_completed(session, attempt, timing)
        return None
    timing.position += 1
    return open_question(session, timing, timestamp)


def reconcile(session, attempt, timing, timestamp):
    if attempt.status != "STARTED":
        return None
    current = session.get(ExamResponse, (attempt.id, timing.position))
    while current is not None and timestamp >= current.deadline:
        deadline = current.deadline
        cause = "GLOBAL" if deadline == timing.global_deadline else "DEADLINE"
        current = close_question(session, attempt, timing, current, deadline, cause)
    return current


def find_attempt(session, guest, attempt_id=None):
    query = (
        select(ExamAttempt, ExamTiming)
        .join(ExamTiming, ExamTiming.attempt_id == ExamAttempt.id)
        .where(ExamAttempt.guest_session_id == guest.id, ExamAttempt.student_id == guest.student_id)
    )
    if attempt_id is not None:
        query = query.where(ExamAttempt.id == attempt_id)
    else:
        query = query.order_by(
            (ExamAttempt.status == "STARTED").desc(), ExamAttempt.started_at.desc(), ExamAttempt.id
        ).limit(1)
    return session.execute(query.with_for_update()).first()


def initialize_attempt(session, attempt):
    # A guest can have several grants, but only one active timed exam.
    running = session.execute(
        select(ExamAttempt, ExamTiming)
        .join(ExamTiming, ExamTiming.attempt_id == ExamAttempt.id)
        .where(
            ExamAttempt.guest_session_id == attempt.guest_session_id,
            ExamAttempt.status == "STARTED",
        )
        .with_for_update()
    ).first()
    if running:
        previous, timing = running
        if reconcile(session, previous, timing, now(session)) is not None:
            raise AccessError("EXAM_ALREADY_ACTIVE")
    session.flush()  # The response's composite foreign key targets a snapshot item.
    timing = ExamTiming(
        attempt_id=attempt.id, position=1, global_deadline=attempt.started_at + EXAM_TIME
    )
    session.add(timing)
    open_question(session, timing, attempt.started_at)


def question_for(session, attempt, position):
    item = session.get(ExamItem, (attempt.id, position))
    return session.get(BankQuestion, item.question_id)


def student_view(session, attempt, timing, current, timestamp):
    view = {
        "id": attempt.id,
        "status": attempt.status,
        "position": timing.position,
        "total": TOTAL,
        "startedAt": attempt.started_at,
        "serverNow": timestamp,
        "globalDeadline": timing.global_deadline,
        "warningAt": attempt.started_at + WARNING_TIME,
        "completedAt": attempt.ended_at,
        "completionReason": timing.completion_reason,
        "question": None,
    }
    if current is not None:
        question = question_for(session, attempt, timing.position)
        media = f"exams/{attempt.id}/media/{timing.position}/"
        option_images = {
            asset["option_label"]: media + str(i)
            for i, asset in enumerate(question.assets)
            if "option_label" in asset
        }
        view["question"] = {
            "text": question.question_text,
            "options": [
                {
                    "id": index,
                    "label": option["label"],
                    "text": option["text"],
                    **(
                        {"image": option_images[option["label"]]}
                        if option["label"] in option_images
                        else {}
                    ),
                }
                for index, option in enumerate(question.options)
            ],
            "deadline": current.deadline,
            "selectedOption": current.selected_option,
            "answerVersion": current.answer_version,
            "images": [
                media + str(i)
                for i, asset in enumerate(question.assets)
                if "option_label" not in asset
            ],
        }
    return view


def save_answer(session, attempt, current, option, version, timestamp):
    if option >= len(question_for(session, attempt, current.position).options):
        return AccessError("INVALID_OPTION", 422)
    if current.selected_option == option and version in {
        current.answer_version,
        current.answer_version - 1,
    }:
        return None
    if version != current.answer_version:
        return AccessError("STALE_ANSWER")
    current.selected_option, current.saved_at = option, timestamp
    current.answer_version += 1
    return None


def image_bytes(session, settings, attempt, position, index):
    question = question_for(session, attempt, position)
    if index >= len(question.assets):
        return AccessError("MEDIA_NOT_FOUND", 404)
    asset = question.assets[index]
    try:
        path = PdfStorage(settings).path(asset["storage_key"])
        with path.open("rb") as stream:
            data = stream.read(8 * 1024 * 1024 + 1)
        if (
            len(data) > 8 * 1024 * 1024
            or not data.startswith(b"\x89PNG\r\n\x1a\n")
            or hashlib.sha256(data).hexdigest() != asset["sha256"]
        ):
            raise ValueError("Invalid exam image")
        return data
    except (KeyError, OSError, PdfError, ValueError):
        return AccessError("MEDIA_UNAVAILABLE", 503)


def operational_summary(session):
    from app.models.exam_bank import ExamOperationalEvent

    status = session.execute(
        select(ExamAttempt.status, ExamTiming.completion_reason, func.count())
        .join(ExamTiming, ExamTiming.attempt_id == ExamAttempt.id)
        .group_by(ExamAttempt.status, ExamTiming.completion_reason)
    ).all()
    return {
        "active": sum(count for state, _, count in status if state == "STARTED"),
        "completed": sum(count for state, _, count in status if state == "COMPLETED"),
        "timeExpired": sum(count for _, reason, count in status if reason == "GLOBAL_TIME_EXPIRED"),
        "startFailures": session.scalar(
            select(func.count())
            .select_from(ExamOperationalEvent)
            .where(ExamOperationalEvent.code == "TIMED_START_UNAVAILABLE")
        ),
    }
