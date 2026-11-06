import uuid
from datetime import timedelta

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core.admin_security import (
    DUMMY_HASH,
    PASSWORD_HASHER,
    AdminLoginLimited,
    AdminUnauthorized,
    BootstrapRefused,
    hash_admin_token,
    hash_password,
    new_admin_token,
    verify_password,
)
from app.core.config import Settings
from app.models import AdminAuditEvent, AdminSession, AdminUser
from app.repositories.admin import AdminRepository
from app.schemas.admin import AdminIdentity, AdminLoginRequest
from app.schemas.student_sessions import normalize_name


class AdminAuthService:
    def __init__(self, session: Session, settings: Settings):
        self.session = session
        self.settings = settings
        self.repository = AdminRepository(session)

    def event(self, event_type, admin_id=None, *, result="success", reason=None):
        metadata = {"result": result}
        if reason is not None:
            metadata["reason"] = reason
        self.session.add(
            AdminAuditEvent(
                id=uuid.uuid4(),
                actor_admin_id=admin_id,
                event_type=event_type,
                created_at=self.repository.now(),
                sanitized_metadata=metadata,
            )
        )

    @staticmethod
    def identity(admin, guest):
        return AdminIdentity(
            id=admin.id,
            fullName=admin.full_name,
            email=admin.email,
            role=admin.role,
            expiresAt=guest.expires_at,
        )

    def bootstrap(self, full_name: str, email: str, password: str):
        # Validate before any insert; password never enters SQL or an audit payload.
        validated = AdminLoginRequest(email=email, password=password)
        name = normalize_name(full_name)
        verifier = hash_password(validated.password.get_secret_value())
        with self.session.begin():
            if not self.repository.bootstrap_available():
                raise BootstrapRefused
            admin = AdminUser(
                id=uuid.uuid4(),
                full_name=name,
                email=str(validated.email),
                password_hash=verifier,
                role="ADMIN",
                is_active=True,
            )
            self.session.add(admin)
            self.session.flush()
            self.event("ADMIN_BOOTSTRAPPED", admin.id)
        return admin.id

    def login(self, credentials: AdminLoginRequest, previous_token: str | None = None):
        denied = False
        token = None
        result = None
        with self.session.begin():
            if not self.repository.login_budget(
                self.settings.admin_login_window_seconds, self.settings.admin_login_limit
            ):
                raise AdminLoginLimited
            self.event("ADMIN_LOGIN_ATTEMPT")
            admin = self.repository.by_email(str(credentials.email))
            verified = verify_password(
                admin.password_hash if admin else DUMMY_HASH,
                credentials.password.get_secret_value(),
            )
            if not verified or admin is None or not admin.is_active or admin.role != "ADMIN":
                self.event("ADMIN_LOGIN_FAILED", result="denied", reason="credentials")
                denied = True
            else:
                now = self.repository.now()
                if PASSWORD_HASHER.check_needs_rehash(admin.password_hash):
                    admin.password_hash = hash_password(credentials.password.get_secret_value())
                if previous_token:
                    try:
                        previous_hash = hash_admin_token(previous_token)
                    except AdminUnauthorized:
                        previous_hash = None
                    if previous_hash:
                        self.session.execute(
                            update(AdminSession)
                            .where(
                                AdminSession.token_hash == previous_hash,
                                AdminSession.admin_id == admin.id,
                                AdminSession.revoked_at.is_(None),
                            )
                            .values(revoked_at=now)
                        )
                token = new_admin_token()
                guest = AdminSession(
                    id=uuid.uuid4(),
                    admin_id=admin.id,
                    token_hash=hash_admin_token(token),
                    created_at=now,
                    last_activity_at=now,
                    expires_at=now
                    + timedelta(seconds=self.settings.admin_session_lifetime_seconds),
                )
                self.session.add(guest)
                self.event("ADMIN_LOGIN_SUCCEEDED", admin.id)
                result = self.identity(admin, guest)
        if denied:
            raise AdminUnauthorized
        return result, token

    def authenticate(self, token: str | None, *, logout=False):
        if not token:
            if logout:
                return None
            raise AdminUnauthorized
        verifier = hash_admin_token(token)
        denied = False
        result = None
        with self.session.begin():
            record = self.repository.lock_session(verifier)
            if record is None:
                raise AdminUnauthorized
            guest, admin = record
            now = self.repository.now()
            if guest.revoked_at is not None:
                if not logout:
                    raise AdminUnauthorized
            elif not admin.is_active or admin.role != "ADMIN":
                guest.revoked_at = now
                self.event("ADMIN_SESSION_REVOKED", admin.id, result="revoked", reason="disabled")
                denied = True
            elif now >= guest.expires_at or now - guest.last_activity_at >= timedelta(
                seconds=self.settings.admin_session_idle_seconds
            ):
                guest.revoked_at = now
                self.event(
                    "ADMIN_SESSION_EXPIRED",
                    admin.id,
                    result="expired",
                    reason="lifetime" if now >= guest.expires_at else "inactivity",
                )
                denied = True
            elif logout:
                guest.revoked_at = now
                self.event("ADMIN_LOGOUT", admin.id, result="revoked")
            else:
                if now - guest.last_activity_at >= timedelta(
                    seconds=self.settings.admin_session_touch_seconds
                ):
                    guest.last_activity_at = now
                result = self.identity(admin, guest)
        if denied:
            raise AdminUnauthorized
        return result
