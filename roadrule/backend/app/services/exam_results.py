from sqlalchemy import select

from app.models.exam_bank import BankQuestion, ExamItem
from app.models.exam_execution import ExamResponse
from app.models.exam_results import ExamGradingFailure, ExamResult
from app.models.student_sessions import Student
from app.services.exam_access import now


def grade_completed(session, attempt, timing):
    """Persist a grade or an integrity marker under the caller's attempt lock."""
    if attempt.status != "COMPLETED" or attempt.ended_at is None:
        return None
    session.flush()
    existing = session.get(ExamResult, attempt.id)
    if existing is not None:
        return existing
    if session.get(ExamGradingFailure, attempt.id) is not None:
        return None
    rows = session.execute(
        select(ExamItem.position, BankQuestion, ExamResponse)
        .join(BankQuestion, BankQuestion.id == ExamItem.question_id)
        .outerjoin(
            ExamResponse,
            (ExamResponse.attempt_id == ExamItem.attempt_id)
            & (ExamResponse.position == ExamItem.position),
        )
        .where(ExamItem.attempt_id == attempt.id)
        .order_by(ExamItem.position)
    ).all()
    timestamp = now(session)
    if (
        not timing.completion_reason
        or [position for position, _, _ in rows] != list(range(1, 21))
        or any(
            question.revision_id != attempt.revision_id
            or question.eligibility != "ELIGIBLE"
            or not isinstance(question.options, list)
            or not 2 <= len(question.options) <= 4
            or question.correct_index not in range(len(question.options))
            or not question.answer_evidence
            or response is None
            or response.finalized_at is None
            or (
                response.selected_option is not None
                and response.selected_option not in range(len(question.options))
            )
            for _, question, response in rows
        )
    ):
        session.add(ExamGradingFailure(attempt_id=attempt.id, recorded_at=timestamp))
        return None
    correct = incorrect = unanswered = 0
    for _, question, response in rows:
        if response.selected_option is None:
            unanswered += 1
        elif response.selected_option == question.correct_index:
            correct += 1
        else:
            incorrect += 1
    result = ExamResult(
        attempt_id=attempt.id,
        student_name=session.get(Student, attempt.student_id).full_name,
        correct=correct,
        incorrect=incorrect,
        unanswered=unanswered,
        completed_at=attempt.ended_at,
        graded_at=timestamp,
        grading_version=1,
    )
    session.add(result)
    return result
