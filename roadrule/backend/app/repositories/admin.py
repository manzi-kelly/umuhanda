from datetime import timedelta

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.models import AdminAuditEvent, AdminSession, AdminUser


class AdminRepository:
    def __init__(self, session: Session):
        self.session = session

    def now(self):
        return self.session.scalar(select(func.clock_timestamp()))

    def by_email(self, email: str):
        return self.session.scalar(select(AdminUser).where(AdminUser.email == email))

    def lock_session(self, verifier: str):
        return self.session.execute(
            select(AdminSession, AdminUser)
            .join(AdminUser, AdminUser.id == AdminSession.admin_id)
            .where(AdminSession.token_hash == verifier)
            .with_for_update(of=AdminSession)
        ).one_or_none()

    def login_budget(self, window: int, limit: int) -> bool:
        if not self.session.scalar(text("SELECT pg_try_advisory_xact_lock(138112, 4)")):
            return False
        cutoff = self.now() - timedelta(seconds=window)
        return (
            self.session.scalar(
                select(func.count())
                .select_from(AdminAuditEvent)
                .where(
                    AdminAuditEvent.event_type == "ADMIN_LOGIN_ATTEMPT",
                    AdminAuditEvent.created_at >= cutoff,
                )
            )
            < limit
        )

    def bootstrap_available(self) -> bool:
        self.session.execute(text("SELECT pg_advisory_xact_lock(138112, 5)"))
        return not self.session.scalar(
            select(func.count()).select_from(AdminUser)
        ) and not self.session.scalar(
            select(func.count())
            .select_from(AdminAuditEvent)
            .where(AdminAuditEvent.event_type == "ADMIN_BOOTSTRAPPED")
        )
