"""Internal exam snapshots. There is no HTTP start route or entitlement issuer."""

import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.session_security import InvalidGuestSession, hash_token
from app.models import GuestSession
from app.models.exam_bank import (
    BankQuestion,
    BankRevision,
    ExamAttempt,
    ExamItem,
    ExamOperationalEvent,
)
from app.services.exam_bank import DIFFICULTY_POLICIES, QUOTAS, category_targets


@dataclass(frozen=True)
class ExamUnavailable:
    reason: str
    code: str = "EXAM_UNAVAILABLE"


EntitlementVerifier = Callable[[Session, UUID, GuestSession], None]


def unused_questions(bank, guest_id):
    used = (
        select(BankQuestion.fingerprint)
        .join(ExamItem, ExamItem.question_id == BankQuestion.id)
        .join(ExamAttempt, ExamAttempt.id == ExamItem.attempt_id)
        .where(ExamAttempt.guest_session_id == guest_id)
    )
    return select(BankQuestion).where(
        BankQuestion.revision_id == bank.id,
        BankQuestion.eligibility == "ELIGIBLE",
        BankQuestion.fingerprint.not_in(used),
    )


def can_choose_questions(session, bank, guest_id):
    pool = unused_questions(bank, guest_id)
    if bank.policy in DIFFICULTY_POLICIES:
        pool = pool.where(BankQuestion.difficulty.in_(tuple(QUOTAS)))
    counts = session.execute(
        pool.with_only_columns(
            BankQuestion.category, BankQuestion.difficulty, func.count()
        ).group_by(BankQuestion.category, BankQuestion.difficulty)
    ).all()
    if bank.policy == "CATEGORY_BALANCED":
        targets = revision_category_targets(bank)
        return bool(targets) and all(
            sum(count for kind, _, count in counts if kind == category) >= required
            for category, required in targets.items()
        )
    if {category for category, _, _ in counts} != {"ROAD_SIGN", "GENERAL"}:
        return False
    if bank.policy not in DIFFICULTY_POLICIES:
        return sum(count for _, _, count in counts) >= 20
    return all(
        sum(count for _, difficulty, count in counts if difficulty == key) >= quota
        for key, quota in QUOTAS.items()
    )


def revision_category_targets(bank):
    stored = bank.counts.get("category_targets", {})
    if not isinstance(stored, dict):
        return {}
    expected = category_targets(stored.get("ROAD_SIGN"))
    return expected if stored == expected else {}


def choose_questions(session, bank, guest_id):
    pool = unused_questions(bank, guest_id)
    # Secret ordering nonce avoids predictable selection and keeps the pool in SQL.
    ordering = func.md5(BankQuestion.fingerprint + secrets.token_hex(32))
    if bank.policy == "CATEGORY_BALANCED":
        targets = revision_category_targets(bank)
        if not targets:
            return []
        selected = []
        for category, count in targets.items():
            group = session.scalars(
                pool.where(BankQuestion.category == category).order_by(ordering).limit(count)
            ).all()
            if len(group) != count:
                return []
            selected.extend(group)
        secrets.SystemRandom().shuffle(selected)
        return selected
    groups = QUOTAS if bank.policy in DIFFICULTY_POLICIES else {None: 20}
    selected = []
    for difficulty, size in groups.items():
        query = pool if difficulty is None else pool.where(BankQuestion.difficulty == difficulty)
        group = session.scalars(query.order_by(ordering).limit(size)).all()
        if len(group) != size:
            return []
        selected.extend(group)
    if len({q.category for q in selected}) == 1:
        opposite = "GENERAL" if selected[0].category == "ROAD_SIGN" else "ROAD_SIGN"
        query = pool.where(BankQuestion.category == opposite)
        if bank.policy in DIFFICULTY_POLICIES:
            query = query.where(BankQuestion.difficulty.in_(list(QUOTAS)))
        candidate = session.scalar(query.order_by(ordering).limit(1))
        if candidate is None:
            return []
        replace = next(
            i
            for i, q in enumerate(selected)
            if bank.policy == "UNSTRATIFIED" or q.difficulty == candidate.difficulty
        )
        selected[replace] = candidate
    secrets.SystemRandom().shuffle(selected)
    return selected


def safe_snapshot(attempt, questions):
    return {
        "id": str(attempt.id),
        "revisionId": str(attempt.revision_id),
        "policy": attempt.policy,
        "questions": [
            {
                "id": str(q.id),
                "position": i,
                "text": q.question_text,
                "options": [{"label": o["label"], "text": o["text"]} for o in q.options],
                "imageCount": len(q.assets),
            }
            for i, q in enumerate(questions, 1)
        ],
    }


def authenticated_guest(session, settings, token):
    if token is None:
        raise InvalidGuestSession
    guest = session.scalar(
        select(GuestSession).where(GuestSession.token_hash == hash_token(token)).with_for_update()
    )
    now = session.scalar(select(func.clock_timestamp()))
    if (
        guest is None
        or guest.revoked_at is not None
        or now >= guest.expires_at
        or now - guest.last_activity_at >= timedelta(seconds=settings.guest_session_idle_seconds)
    ):
        raise InvalidGuestSession
    if now - guest.last_activity_at >= timedelta(seconds=settings.guest_session_touch_seconds):
        guest.last_activity_at = now
    return guest


def start_exam(
    session: Session,
    settings,
    token: str | None,
    entitlement_id: UUID,
    *,
    verify_entitlement: EntitlementVerifier,
    consume_entitlement: Callable[[Session, ExamAttempt], None] | None = None,
):
    """Future trusted caller supplies a verifier that locks and checks an actual grant.

    The verifier must check ownership and validity, including idempotent access to a
    committed attempt. It must not consume a grant.
    A committed attempt keyed by entitlement_id is the consumption record.
    """
    with session.begin():
        guest = authenticated_guest(session, settings, token)
        # Serialize a grant even if maliciously reused from a different guest.
        session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 410))"),
            {"key": f"exam:{entitlement_id}"},
        )
        verify_entitlement(session, entitlement_id, guest)
        existing = session.scalar(
            select(ExamAttempt).where(ExamAttempt.entitlement_id == entitlement_id)
        )
        if existing:
            if existing.guest_session_id != guest.id:
                raise PermissionError("Exam entitlement does not belong to this session.")
            questions = session.scalars(
                select(BankQuestion)
                .join(ExamItem, ExamItem.question_id == BankQuestion.id)
                .where(ExamItem.attempt_id == existing.id)
                .order_by(ExamItem.position)
            ).all()
            return safe_snapshot(existing, questions)
        bank = session.scalar(select(BankRevision).where(BankRevision.active))
        questions = choose_questions(session, bank, guest.id) if bank else []
        if len(questions) != 20:
            reason = "UNUSED_POOL_INSUFFICIENT" if bank else "NO_ACTIVE_BANK"
            session.add(ExamOperationalEvent(code=reason))
            return ExamUnavailable(reason)
        attempt = ExamAttempt(
            student_id=guest.student_id,
            guest_session_id=guest.id,
            entitlement_id=entitlement_id,
            revision_id=bank.id,
            policy=bank.policy,
            started_at=session.scalar(select(func.clock_timestamp())),
        )
        session.add(attempt)
        session.flush()
        session.add_all(
            ExamItem(attempt_id=attempt.id, position=i, question_id=q.id)
            for i, q in enumerate(questions, 1)
        )
        if consume_entitlement is not None:
            consume_entitlement(session, attempt)
        return safe_snapshot(attempt, questions)
