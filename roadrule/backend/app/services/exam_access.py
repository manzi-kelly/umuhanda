"""Transactional authorization sources. Mock settlement has no HTTP entry point."""

import hashlib
import re
import secrets
from datetime import UTC, timedelta

from sqlalchemy import func, select, text

from app.models import GuestSession
from app.models.exam_access import ExamEntitlement, PaymentTransaction, PromoAttempt, PromoCode
from app.models.exam_bank import BankRevision, ExamOperationalEvent
from app.services.exam_generation import can_choose_questions, start_exam


class AccessError(Exception):
    def __init__(self, code, status=409):
        self.code = code
        self.status = status


def now(session):
    return session.scalar(select(func.clock_timestamp()))


def readiness(session, guest_id, *, audit=True):
    """Return an accurate readiness result without claiming an empty bank is usable."""
    bank = session.scalar(select(BankRevision).where(BankRevision.active))
    if bank and can_choose_questions(session, bank, guest_id):
        return True, None
    reason = "UNUSED_POOL_INSUFFICIENT" if bank else "NO_ACTIVE_BANK"
    if audit:
        session.add(ExamOperationalEvent(code=reason))
    return False, reason


def ready(session, guest_id, *, audit=True):
    return readiness(session, guest_id, audit=audit)[0]


def payment_view(payment):
    return {
        "id": payment.id,
        "reference": payment.reference,
        "provider": payment.provider,
        "mode": payment.mode,
        "amount": int(payment.amount),
        "currency": payment.currency,
        "status": payment.status,
    }


def initiate(session, settings, guest, provider, key):
    if not settings.mock_allowed:
        raise AccessError("MOCK_DISABLED", 403)
    existing = session.scalar(
        select(PaymentTransaction).where(
            PaymentTransaction.guest_session_id == guest.id,
            PaymentTransaction.idempotency_key == key,
        )
    )
    if existing:
        if existing.provider != provider:
            raise AccessError("IDEMPOTENCY_CONFLICT")
        return payment_view(existing)
    if not ready(session, guest.id):
        return AccessError("EXAM_UNAVAILABLE", 503)
    payment = PaymentTransaction(
        student_id=guest.student_id,
        guest_session_id=guest.id,
        provider=provider,
        reference="MOCK-" + secrets.token_hex(16),
        idempotency_key=key,
        amount=settings.mock_exam_amount_rwf,
        created_at=now(session),
    )
    session.add(payment)
    session.flush()
    return payment_view(payment)


def settle_mock(session, settings, payment_id, outcome):
    if not settings.mock_allowed:
        raise AccessError("MOCK_DISABLED", 403)
    if outcome not in {"SUCCESSFUL", "FAILED", "CANCELLED"}:
        raise AccessError("INVALID_PAYMENT_STATE", 422)
    with session.begin():
        candidate = session.get(PaymentTransaction, payment_id)
        if candidate is None:
            raise AccessError("PAYMENT_NOT_FOUND", 404)
        guest = session.scalar(
            select(GuestSession)
            .where(GuestSession.id == candidate.guest_session_id)
            .with_for_update()
        )
        payment = session.scalar(
            select(PaymentTransaction)
            .where(PaymentTransaction.id == payment_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if payment.status == outcome:
            return payment_view(payment)
        if payment.status != "PENDING":
            raise AccessError("INVALID_PAYMENT_STATE")
        timestamp = now(session)
        if outcome == "SUCCESSFUL":
            if (
                guest.revoked_at
                or timestamp >= guest.expires_at
                or timestamp - guest.last_activity_at
                >= timedelta(seconds=settings.guest_session_idle_seconds)
            ):
                raise AccessError("GUEST_SESSION_REQUIRED", 401)
            if not ready(session, guest.id):
                return AccessError("EXAM_UNAVAILABLE", 503)
            payment.status, payment.completed_at = outcome, timestamp
            session.flush()
            session.add(
                ExamEntitlement(
                    student_id=guest.student_id,
                    guest_session_id=guest.id,
                    payment_id=payment.id,
                    created_at=timestamp,
                )
            )
        payment.status, payment.completed_at = outcome, timestamp
        return payment_view(payment)


PROMO_CODE_PATTERN = re.compile(r"[A-Z0-9][A-Z0-9._-]{0,79}", flags=re.ASCII)


def normalize_promo_code(code):
    """Normalize an administrator-entered code; return None when it is not usable."""
    if not isinstance(code, str):
        return None
    normalized = code.strip().upper()
    if normalized and PROMO_CODE_PATTERN.fullmatch(normalized) is not None:
        return normalized
    return None


def verifier(code):
    return hashlib.sha256(("promo:" + code).encode("ascii")).hexdigest()


def promo_used(session, promo_id):
    return session.scalar(
        select(func.count())
        .select_from(ExamEntitlement)
        .where(ExamEntitlement.promo_id == promo_id)
    )


def duplicate_promo(session, digest, *, exclude=None):
    query = select(PromoCode.id).where(
        PromoCode.verifier == digest, PromoCode.deleted_at.is_(None)
    )
    if exclude is not None:
        query = query.where(PromoCode.id != exclude)
    return session.scalar(query) is not None


def new_promo(session, admin_id, code, limit, expires_in_hours=24):
    normalized = normalize_promo_code(code)
    if normalized is None:
        raise AccessError("PROMO_CODE_INVALID", 422)
    digest = verifier(normalized)
    if duplicate_promo(session, digest):
        raise AccessError("PROMO_DUPLICATE", 409)
    timestamp = now(session)
    row = PromoCode(
        code=normalized,
        verifier=digest,
        created_by=admin_id,
        usage_limit=limit,
        created_at=timestamp,
        expires_at=timestamp + timedelta(hours=expires_in_hours),
        published_at=timestamp,
        updated_at=timestamp,
    )
    session.add(row)
    session.flush()
    return promo_view(row, 0, timestamp)


def promo_row(session, promo_id, *, lock=False):
    query = select(PromoCode).where(
        PromoCode.id == promo_id, PromoCode.deleted_at.is_(None)
    )
    if lock:
        query = query.with_for_update()
    row = session.scalar(query)
    if row is None:
        raise AccessError("PROMO_NOT_FOUND", 404)
    return row


UNSET = object()


def update_promo(
    session,
    promo_id,
    *,
    code=UNSET,
    usage_limit=UNSET,
    expires_at=UNSET,
):
    row = promo_row(session, promo_id, lock=True)
    if code is UNSET and usage_limit is UNSET and expires_at is UNSET:
        raise AccessError("PROMO_UPDATE_EMPTY", 422)
    if code is not UNSET:
        normalized = normalize_promo_code(code)
        if normalized is None:
            raise AccessError("PROMO_CODE_INVALID", 422)
        digest = verifier(normalized)
        if duplicate_promo(session, digest, exclude=row.id):
            raise AccessError("PROMO_DUPLICATE", 409)
        row.code, row.verifier = normalized, digest
    if usage_limit is not UNSET:
        row.usage_limit = usage_limit
    if expires_at is not UNSET:
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at <= row.created_at:
            raise AccessError("PROMO_EXPIRY_INVALID", 422)
        row.expires_at = expires_at
    row.updated_at = now(session)
    session.flush()
    return promo_view(row, promo_used(session, row.id), row.updated_at)


def disable_promo(session, promo_id):
    row = promo_row(session, promo_id, lock=True)
    timestamp = now(session)
    if row.disabled_at is None:
        row.disabled_at = timestamp
    row.updated_at = timestamp
    session.flush()
    return promo_view(row, promo_used(session, row.id), timestamp)


def enable_promo(session, promo_id):
    row = promo_row(session, promo_id, lock=True)
    timestamp = now(session)
    row.disabled_at = None
    row.updated_at = timestamp
    session.flush()
    return promo_view(row, promo_used(session, row.id), timestamp)


def delete_promo(session, promo_id):
    row = promo_row(session, promo_id, lock=True)
    timestamp = now(session)
    row.deleted_at = timestamp
    row.updated_at = timestamp
    session.flush()
    return {"id": row.id, "status": "DELETED"}


def promo_view(row, used, timestamp):
    status = (
        "DELETED"
        if row.deleted_at
        else "DISABLED"
        if row.disabled_at
        else "DRAFT"
        if row.published_at is None
        else "EXPIRED"
        if timestamp >= row.expires_at
        else "EXHAUSTED"
        if used >= row.usage_limit
        else "ACTIVE"
    )
    return {
        "id": row.id,
        "code": row.code,
        "createdAt": row.created_at,
        "publishedAt": row.published_at,
        "updatedAt": row.updated_at,
        "expiresAt": row.expires_at,
        "usageLimit": row.usage_limit,
        "used": used,
        "status": status,
        "disabledAt": row.disabled_at,
        "deletedAt": row.deleted_at,
    }


def redeem(session, guest, code):
    # Durable shared budget limits new guest sessions as well as repeat guesses.
    session.execute(text("SELECT pg_advisory_xact_lock(138112, 10)"))
    timestamp = now(session)
    recent = (
        select(func.count())
        .select_from(PromoAttempt)
        .where(PromoAttempt.created_at >= timestamp - timedelta(minutes=5))
    )
    if (
        session.scalar(recent) >= 100
        or session.scalar(recent.where(PromoAttempt.guest_session_id == guest.id)) >= 8
    ):
        return AccessError("PROMO_RATE_LIMITED", 429)
    session.add(PromoAttempt(guest_session_id=guest.id, created_at=timestamp))
    normalized = normalize_promo_code(code)
    if normalized is None:
        return AccessError("PROMO_INVALID", 422)
    promo = session.scalar(
        select(PromoCode)
        .where(
            PromoCode.verifier == verifier(normalized),
            PromoCode.deleted_at.is_(None),
        )
        .with_for_update()
    )
    if promo is None:
        return AccessError("PROMO_INVALID", 422)
    existing = session.scalar(
        select(ExamEntitlement).where(
            ExamEntitlement.promo_id == promo.id, ExamEntitlement.guest_session_id == guest.id
        )
    )
    if existing:
        return grant_view(existing)
    used = promo_used(session, promo.id)
    timestamp = now(session)
    if promo.published_at is None:
        return AccessError("PROMO_NOT_PUBLISHED", 422)
    if promo.disabled_at is not None:
        return AccessError("PROMO_DISABLED", 422)
    if timestamp >= promo.expires_at:
        return AccessError("PROMO_EXPIRED", 422)
    if used >= promo.usage_limit:
        return AccessError("PROMO_EXHAUSTED", 422)
    if not ready(session, guest.id):
        return AccessError("EXAM_UNAVAILABLE", 503)
    row = ExamEntitlement(
        student_id=guest.student_id,
        guest_session_id=guest.id,
        promo_id=promo.id,
        created_at=timestamp,
    )
    session.add(row)
    session.flush()
    return grant_view(row)


def grant_view(row):
    return {
        "id": row.id,
        "status": row.status,
        "accessStatus": "ACTIVE" if row.status == "AVAILABLE" else "INACTIVE",
        "source": "PROMO" if row.promo_id else "MOCK_PAYMENT",
    }


def start_with_entitlement(session, settings, token, identifier, *, initialize=None):
    def verify(db, key, guest):
        grant = db.scalar(
            select(ExamEntitlement).where(ExamEntitlement.id == key).with_for_update()
        )
        if (
            grant is None
            or grant.guest_session_id != guest.id
            or grant.student_id != guest.student_id
            or grant.status == "REVOKED"
            or (grant.payment_id and not settings.mock_allowed)
        ):
            raise AccessError("ENTITLEMENT_REQUIRED", 403)

    def consume(db, attempt):
        grant = db.get(ExamEntitlement, identifier)
        if grant.status != "AVAILABLE":
            raise AccessError("ENTITLEMENT_REQUIRED", 403)
        if initialize is not None:
            initialize(db, attempt)
        grant.status, grant.attempt_id, grant.consumed_at = "CONSUMED", attempt.id, now(db)

    return start_exam(
        session, settings, token, identifier, verify_entitlement=verify, consume_entitlement=consume
    )
