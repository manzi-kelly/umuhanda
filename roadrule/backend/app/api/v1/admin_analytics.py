from datetime import UTC, date, datetime, time, timedelta
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends
from sqlalchemy import and_, func, select, text

from app.api.v1.admin import DatabaseSession, require_admin
from app.models.exam_access import ExamEntitlement, PaymentTransaction, PromoCode
from app.models.exam_bank import BankRevision, ExamAttempt, ExamOperationalEvent
from app.models.exam_execution import ExamTiming
from app.models.exam_results import ExamGradingFailure, ExamResult
from app.models.pdf_import import PdfDocument, PdfImportJob
from app.models.student_sessions import GuestSession, Student
from app.schemas.admin import AdminIdentity
from app.services.exam_access import AccessError, now

router = APIRouter(prefix="/admin", tags=["admin analytics"])
Admin = Annotated[AdminIdentity, Depends(require_admin)]
Period = Literal["daily", "weekly", "monthly", "yearly"]
KIGALI = ZoneInfo("Africa/Kigali")


def reporting_bounds(timestamp, period, start=None, end=None):
    today = timestamp.astimezone(KIGALI).date()
    if (start is None) != (end is None) or (
        start is not None
        and (start == date.min or end < start or end > today or (end - start).days >= 366)
    ):
        raise AccessError("INVALID_REPORTING_RANGE", 422)
    if start is None:
        start = {
            "daily": today,
            "weekly": today - timedelta(days=today.weekday()),
            "monthly": today.replace(day=1),
            "yearly": today.replace(month=1, day=1),
        }[period]
        end = today
    return (
        datetime.combine(start, time.min, KIGALI).astimezone(UTC),
        datetime.combine(end + timedelta(days=1), time.min, KIGALI).astimezone(UTC),
    )


@router.get("/analytics/overview")
def overview(
    _admin: Admin,
    session: DatabaseSession,
    period: Period = "weekly",
    start: date | None = None,
    end: date | None = None,
):
    session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
    timestamp = now(session)
    lower, upper = reporting_bounds(timestamp, period, start, end)

    def within(column):
        return and_(column >= lower, column < upper)

    students, unique_students, registered = session.execute(
        select(
            func.count(Student.id),
            func.count(func.distinct(Student.id)),
            func.count().filter(within(Student.created_at)),
        )
    ).one()
    active_students = session.scalar(
        select(func.count(func.distinct(GuestSession.student_id))).where(
            within(GuestSession.last_activity_at)
        )
    )
    attempts, active, completed, expired, passed, failed, average, unanswered = session.execute(
        select(
            func.count(),
            func.count().filter(ExamAttempt.status == "STARTED"),
            func.count().filter(ExamAttempt.status == "COMPLETED"),
            func.count().filter(ExamTiming.completion_reason == "GLOBAL_TIME_EXPIRED"),
            func.count().filter(ExamResult.correct >= 12),
            func.count().filter(ExamResult.correct < 12),
            func.avg(ExamResult.correct),
            func.sum(ExamResult.unanswered),
        )
        .select_from(ExamAttempt)
        .outerjoin(ExamTiming, ExamTiming.attempt_id == ExamAttempt.id)
        .outerjoin(ExamResult, ExamResult.attempt_id == ExamAttempt.id)
        .where(within(ExamAttempt.started_at))
    ).one()
    uses = (
        select(ExamEntitlement.promo_id, func.count().label("used"))
        .where(ExamEntitlement.promo_id.is_not(None))
        .group_by(ExamEntitlement.promo_id)
        .subquery()
    )
    used = func.coalesce(uses.c.used, 0)
    enabled = PromoCode.disabled_at.is_(None)
    live = and_(enabled, PromoCode.expires_at > timestamp)
    available = and_(live, used < PromoCode.usage_limit)
    generated, current, disabled, expired_codes, exhausted, capacity = session.execute(
        select(
            func.count().filter(within(PromoCode.created_at)),
            func.count().filter(available),
            func.count().filter(~enabled),
            func.count().filter(enabled, PromoCode.expires_at <= timestamp),
            func.count().filter(live, used >= PromoCode.usage_limit),
            func.coalesce(func.sum(PromoCode.usage_limit - used).filter(available), 0),
        )
        .select_from(PromoCode)
        .outerjoin(uses, uses.c.promo_id == PromoCode.id)
        .where(PromoCode.deleted_at.is_(None))
    ).one()
    redeemed = session.scalar(
        select(func.count())
        .select_from(ExamEntitlement)
        .where(ExamEntitlement.promo_id.is_not(None), within(ExamEntitlement.created_at))
    )
    initiated, pending, successful, rejected, cancelled, simulated = session.execute(
        select(
            func.count(),
            func.count().filter(PaymentTransaction.status == "PENDING"),
            func.count().filter(PaymentTransaction.status == "SUCCESSFUL"),
            func.count().filter(PaymentTransaction.status == "FAILED"),
            func.count().filter(PaymentTransaction.status == "CANCELLED"),
            func.coalesce(
                func.sum(PaymentTransaction.amount).filter(
                    PaymentTransaction.status == "SUCCESSFUL"
                ),
                0,
            ),
        ).where(PaymentTransaction.mode == "MOCK", within(PaymentTransaction.created_at))
    ).one()
    return {
        "asOf": timestamp,
        "window": {"start": lower, "endExclusive": upper, "timezone": "Africa/Kigali"},
        "students": {
            "records": students,
            "uniqueIds": unique_students,
            "registered": registered,
            "recentlyActiveIds": active_students,
        },
        "examinations": {
            "attempts": attempts,
            "active": active,
            "completed": completed,
            "expired": expired,
            "passed": passed,
            "failed": failed,
            "averageScore": average,
            "passRate": round(100 * passed / (passed + failed), 2) if passed + failed else None,
            "unanswered": unanswered,
        },
        "promos": {
            "generated": generated,
            "active": current,
            "disabled": disabled,
            "expired": expired_codes,
            "exhausted": exhausted,
            "remainingCapacity": capacity,
            "redeemed": redeemed,
            "entitlementsIssued": redeemed,
        },
        "payments": {
            "mode": "MOCK",
            "initiated": initiated,
            "pending": pending,
            "successful": successful,
            "failed": rejected,
            "cancelled": cancelled,
            "simulatedSuccessfulRwf": simulated,
            "realVerifiedRevenue": None,
        },
    }


@router.get("/system")
def system(_admin: Admin, session: DatabaseSession):
    session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
    timestamp = now(session)
    since = timestamp - timedelta(hours=24)
    jobs = dict(
        session.execute(
            select(PdfImportJob.status, func.count()).group_by(PdfImportJob.status)
        ).all()
    )
    activity, last_success, errors, stuck = session.execute(
        select(
            func.max(func.coalesce(PdfImportJob.completed_at, PdfImportJob.started_at)),
            func.max(PdfImportJob.completed_at).filter(
                PdfImportJob.status.in_(("COMPLETED", "COMPLETED_WITH_WARNINGS"))
            ),
            func.coalesce(func.sum(PdfImportJob.failed_item_count), 0),
            func.count().filter(
                PdfImportJob.status == "PROCESSING",
                PdfImportJob.started_at < timestamp - timedelta(minutes=30),
            ),
        )
    ).one()
    failures = session.scalar(
        select(func.count())
        .select_from(ExamOperationalEvent)
        .where(ExamOperationalEvent.created_at >= since)
    )
    integrity = session.scalar(
        select(func.count())
        .select_from(ExamGradingFailure)
        .where(ExamGradingFailure.recorded_at >= since)
    )
    bank = session.scalar(select(BankRevision).where(BankRevision.active))
    failed_jobs = jobs.get("FAILED", 0)
    warnings = []
    if failed_jobs or stuck:
        warnings.append("PDF_IMPORT_ISSUES")
    if not bank:
        warnings.append("EXAM_BANK_UNAVAILABLE")
    if failures:
        warnings.append("EXAM_START_FAILURES")
    if integrity:
        warnings.append("GRADING_INTEGRITY")
    return {
        "asOf": timestamp,
        "status": "DEGRADED" if warnings else "HEALTHY",
        "backend": "HEALTHY",
        "database": "HEALTHY",
        "pdfWorker": {
            "status": "DEGRADED" if stuck else "UNKNOWN",
            "lastObservedActivity": activity,
            "staleProcessing": stuck,
        },
        "pdf": {
            "documents": session.scalar(select(func.count()).select_from(PdfDocument)),
            "jobs": jobs,
            "lastSuccessfulImport": last_success,
            "extractionErrors": errors,
        },
        "bank": {"id": bank.id, "policy": bank.policy, "counts": bank.counts} if bank else None,
        "recentExamStartFailures": failures,
        "recentGradingIntegrityIssues": integrity,
        "warnings": warnings,
    }
