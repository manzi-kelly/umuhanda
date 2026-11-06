from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy import func, or_, select

from app.api.v1.admin import DatabaseSession, require_admin
from app.api.v1.exam_access import for_guest
from app.api.v1.exam_execution import execute
from app.models.exam_bank import ExamAttempt
from app.models.exam_execution import ExamTiming
from app.models.exam_results import ExamGradingFailure, ExamResult
from app.models.student_sessions import Student
from app.schemas.admin import AdminIdentity
from app.services.exam_access import AccessError
from app.services.exam_results import grade_completed

router = APIRouter(tags=["exam results"])


class ResultView(BaseModel):
    attemptId: UUID
    studentName: str
    startedAt: datetime
    completedAt: datetime
    completionReason: str
    correct: int
    incorrect: int
    unanswered: int
    score: int
    total: int = 20
    percentage: int
    status: str


def result_view(attempt, timing, result):
    return ResultView(
        attemptId=attempt.id,
        studentName=result.student_name,
        startedAt=attempt.started_at,
        completedAt=result.completed_at,
        completionReason=timing.completion_reason,
        correct=result.correct,
        incorrect=result.incorrect,
        unanswered=result.unanswered,
        score=result.correct,
        percentage=result.correct * 5,
        status="PASSED" if result.correct >= 12 else "FAILED",
    )


@router.get("/exams/{attempt_id}/result", response_model=ResultView)
def exam_result(attempt_id: UUID, request: Request, session: DatabaseSession):
    def read(_settings, attempt, timing, _current, _timestamp):
        if attempt.status != "COMPLETED":
            return AccessError("EXAM_NOT_COMPLETED", 409)
        result = grade_completed(session, attempt, timing)
        if result is None:
            return AccessError("EXAM_RESULT_UNAVAILABLE", 503)
        return result_view(attempt, timing, result)

    return execute(request, session, attempt_id, read)


@router.get("/students/exams/history", response_model=list[ResultView])
def history(
    request: Request,
    session: DatabaseSession,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    def read(guest, _settings):
        rows = session.execute(
            select(ExamAttempt, ExamTiming, ExamResult)
            .join(ExamTiming, ExamTiming.attempt_id == ExamAttempt.id)
            .join(ExamResult, ExamResult.attempt_id == ExamAttempt.id)
            .where(
                ExamAttempt.student_id == guest.student_id,
                ExamAttempt.guest_session_id == guest.id,
                ExamAttempt.status == "COMPLETED",
            )
            .order_by(ExamResult.completed_at.desc(), ExamAttempt.id)
            .limit(limit)
            .offset(offset)
        )
        return [result_view(*row) for row in rows]

    return for_guest(request, session, read)


Admin = Annotated[AdminIdentity, Depends(require_admin)]


def reporting_rows():
    return (
        select(ExamAttempt, ExamTiming, ExamResult, Student.full_name, ExamGradingFailure)
        .join(Student, Student.id == ExamAttempt.student_id)
        .outerjoin(ExamTiming, ExamTiming.attempt_id == ExamAttempt.id)
        .outerjoin(ExamResult, ExamResult.attempt_id == ExamAttempt.id)
        .outerjoin(ExamGradingFailure, ExamGradingFailure.attempt_id == ExamAttempt.id)
    )


def admin_view(attempt, timing, result, name, failure):
    return {
        "attemptId": attempt.id,
        "studentName": result.student_name if result else name,
        "startedAt": attempt.started_at,
        "completedAt": attempt.ended_at,
        "status": (("PASSED" if result.correct >= 12 else "FAILED") if result else attempt.status),
        "completionReason": timing.completion_reason if timing else None,
        "gradingIssue": failure is not None,
        "result": result_view(attempt, timing, result) if result else None,
    }


def midnight(day):
    return datetime.combine(day, datetime.min.time(), tzinfo=UTC)


@router.get("/admin/exam-results")
def admin_results(
    _admin: Admin,
    session: DatabaseSession,
    search: str = Query("", max_length=120),
    status: Literal["STARTED", "COMPLETED", "PASSED", "FAILED", "EXPIRED"] | None = None,
    start: date | None = None,
    end: date | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    query = reporting_rows()
    if search:
        query = query.where(
            or_(
                Student.full_name.icontains(search, autoescape=True),
                ExamResult.student_name.icontains(search, autoescape=True),
            )
        )
    filters = {
        "STARTED": ExamAttempt.status == "STARTED",
        "COMPLETED": ExamAttempt.status == "COMPLETED",
        "PASSED": ExamResult.correct >= 12,
        "FAILED": ExamResult.correct < 12,
        "EXPIRED": ExamTiming.completion_reason == "GLOBAL_TIME_EXPIRED",
    }
    if status:
        query = query.where(filters[status])
    if start:
        query = query.where(ExamAttempt.started_at >= midnight(start))
    if end:
        query = query.where(
            ExamAttempt.started_at <= datetime.combine(end, datetime.max.time(), tzinfo=UTC)
        )
    rows = session.execute(
        query.order_by(ExamAttempt.started_at.desc(), ExamAttempt.id)
        .limit(limit + 1)
        .offset(offset)
    ).all()
    return {"items": [admin_view(*row) for row in rows[:limit]], "hasMore": len(rows) > limit}


@router.get("/admin/exam-results/stats")
def admin_stats(
    _admin: Admin,
    session: DatabaseSession,
    period: Literal["all", "daily", "weekly", "monthly", "yearly"] = "all",
):
    today = session.scalar(select(func.current_date()))
    starts = {
        "daily": today,
        "weekly": today - timedelta(days=today.weekday()),
        "monthly": today.replace(day=1),
        "yearly": today.replace(month=1, day=1),
    }
    query = (
        select(
            func.count(),
            func.count().filter(ExamAttempt.status == "COMPLETED"),
            func.count().filter(ExamAttempt.status == "STARTED"),
            func.count().filter(ExamResult.correct >= 12),
            func.count().filter(ExamResult.correct < 12),
            func.count().filter(ExamTiming.completion_reason == "GLOBAL_TIME_EXPIRED"),
            func.avg(ExamResult.correct),
        )
        .select_from(ExamAttempt)
        .outerjoin(ExamTiming, ExamTiming.attempt_id == ExamAttempt.id)
        .outerjoin(ExamResult, ExamResult.attempt_id == ExamAttempt.id)
    )
    if period != "all":
        query = query.where(
            ExamAttempt.started_at >= midnight(starts[period]),
            ExamAttempt.started_at < midnight(today + timedelta(days=1)),
        )
    total, completed, active, passed, failed, expired, average = session.execute(query).one()
    return {
        "total": total,
        "completed": completed,
        "active": active,
        "passed": passed,
        "failed": failed,
        "expired": expired,
        "passPercentage": round(100 * passed / (passed + failed), 2) if passed + failed else None,
        "averageScore": round(float(average), 2) if average is not None else None,
    }


@router.get("/admin/exam-results/{attempt_id}")
def admin_result(attempt_id: UUID, _admin: Admin, session: DatabaseSession):
    row = session.execute(reporting_rows().where(ExamAttempt.id == attempt_id)).first()
    if row is None:
        raise AccessError("EXAM_NOT_FOUND", 404)
    return admin_view(*row)
