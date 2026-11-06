from datetime import datetime, timedelta

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.models import GuestSession, Student, StudentActivityEvent


class StudentSessionRepository:
    def __init__(self, session: Session):
        self.session = session

    def database_now(self) -> datetime:
        return self.session.scalar(select(func.clock_timestamp()))

    def lock_creation_budget(self) -> bool:
        # Shared across workers/processes using this dedicated PostgreSQL database.
        return self.session.scalar(text("SELECT pg_try_advisory_xact_lock(138112, 3)"))

    def recent_creations(self, now: datetime, window_seconds: int) -> int:
        return self.session.scalar(
            select(func.count())
            .select_from(StudentActivityEvent)
            .where(
                StudentActivityEvent.event_type == "SESSION_CREATED",
                StudentActivityEvent.created_at >= now - timedelta(seconds=window_seconds),
            )
        )

    def add(self, record: Student | GuestSession | StudentActivityEvent) -> None:
        self.session.add(record)

    def lock_by_hash(self, verifier: str) -> tuple[GuestSession, Student] | None:
        return self.session.execute(
            select(GuestSession, Student)
            .join(Student, Student.id == GuestSession.student_id)
            .where(GuestSession.token_hash == verifier)
            .with_for_update(of=GuestSession)
        ).one_or_none()

    def has_event(self, guest: GuestSession, event_type: str) -> bool:
        return (
            self.session.scalar(
                select(StudentActivityEvent.id).where(
                    StudentActivityEvent.guest_session_id == guest.id,
                    StudentActivityEvent.event_type == event_type,
                )
            )
            is not None
        )
