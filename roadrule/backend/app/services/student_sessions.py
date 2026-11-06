import uuid
from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.session_security import (
    InvalidGuestSession,
    SessionCreationLimited,
    hash_token,
    new_token,
)
from app.models import GuestSession, Student, StudentActivityEvent
from app.repositories.student_sessions import StudentSessionRepository
from app.schemas.student_sessions import StudentSessionRequest, StudentSessionResponse, mask_phone


class StudentSessionService:
    def __init__(self, session: Session, settings: Settings):
        self.session = session
        self.settings = settings
        self.repository = StudentSessionRepository(session)

    @staticmethod
    def response(student: Student, guest: GuestSession) -> StudentSessionResponse:
        return StudentSessionResponse(
            studentId=student.id,
            sessionReference=guest.id,
            fullName=student.full_name,
            maskedPhoneNumber=mask_phone(student.phone_number),
            expiresAt=guest.expires_at,
        )

    def create(self, payload: StudentSessionRequest) -> tuple[StudentSessionResponse, str]:
        token = new_token()
        with self.session.begin():
            if not self.repository.lock_creation_budget():
                raise SessionCreationLimited
            now = self.repository.database_now()
            if (
                self.repository.recent_creations(now, self.settings.session_creation_window_seconds)
                >= self.settings.session_creation_limit
            ):
                raise SessionCreationLimited
            student = Student(
                id=uuid.uuid4(),
                full_name=payload.fullName,
                phone_number=payload.phoneNumber,
                created_at=now,
                updated_at=now,
            )
            self.repository.add(student)
            self.session.flush()
            guest = GuestSession(
                id=uuid.uuid4(),
                student_id=student.id,
                token_hash=hash_token(token),
                created_at=now,
                last_activity_at=now,
                expires_at=now + timedelta(seconds=self.settings.guest_session_lifetime_seconds),
            )
            self.repository.add(guest)
            self.session.flush()
            for event_type, reference in (("STUDENT_CREATED", None), ("SESSION_CREATED", guest.id)):
                self.repository.add(
                    StudentActivityEvent(
                        id=uuid.uuid4(),
                        student_id=student.id,
                        guest_session_id=reference,
                        event_type=event_type,
                        created_at=now,
                    )
                )
            result = self.response(student, guest)
        # Cookie is issued only after the atomic transaction commits successfully.
        return result, token

    def authenticate(
        self, token: str | None, *, revoke: bool = False
    ) -> StudentSessionResponse | None:
        if token is None:
            if revoke:
                return None  # Repeat logout after cookie deletion is a safe no-op.
            raise InvalidGuestSession
        verifier = hash_token(token)
        expired = False
        result = None
        with self.session.begin():
            record = self.repository.lock_by_hash(verifier)
            if record is None:
                raise InvalidGuestSession
            guest, student = record
            if guest.revoked_at is not None:
                if not revoke:
                    raise InvalidGuestSession
            else:
                # Sample database time after obtaining the row lock, never browser/app time.
                now = self.repository.database_now()
                expired = now >= guest.expires_at or now - guest.last_activity_at >= timedelta(
                    seconds=self.settings.guest_session_idle_seconds
                )
                if expired:
                    if not self.repository.has_event(guest, "SESSION_EXPIRED"):
                        self.repository.add(
                            StudentActivityEvent(
                                id=uuid.uuid4(),
                                student_id=student.id,
                                guest_session_id=guest.id,
                                event_type="SESSION_EXPIRED",
                                created_at=now,
                            )
                        )
                elif revoke:
                    guest.revoked_at = now
                    self.repository.add(
                        StudentActivityEvent(
                            id=uuid.uuid4(),
                            student_id=student.id,
                            guest_session_id=guest.id,
                            event_type="SESSION_REVOKED",
                            created_at=now,
                        )
                    )
                else:
                    if now - guest.last_activity_at >= timedelta(
                        seconds=self.settings.guest_session_touch_seconds
                    ):
                        guest.last_activity_at = now
                    result = self.response(student, guest)
        # Preserve the one-time expiration audit even though authentication is rejected.
        if expired:
            raise InvalidGuestSession
        return result
