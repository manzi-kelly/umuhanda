from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select

from app.api.v1.admin import DatabaseSession, require_admin
from app.core.session_security import read_token
from app.models.exam_access import ExamEntitlement, PaymentTransaction, PromoCode
from app.schemas.admin import AdminIdentity
from app.services.exam_access import (
    AccessError,
    delete_promo,
    disable_promo,
    enable_promo,
    grant_view,
    initiate,
    new_promo,
    now,
    payment_view,
    promo_view,
    readiness,
    redeem,
    update_promo,
)
from app.services.exam_generation import authenticated_guest

router = APIRouter()
Admin = Annotated[AdminIdentity, Depends(require_admin)]


class PaymentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: Literal["MTN", "AIRTEL"]
    idempotencyKey: UUID


class PromoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(max_length=80)


class CreatePromo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(min_length=1, max_length=80)
    usageLimit: int = Field(default=1, ge=1, le=100, strict=True)
    expiresInHours: int = Field(default=24, ge=1, le=8760, strict=True)


class UpdatePromo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str | None = Field(default=None, min_length=1, max_length=80)
    usageLimit: int | None = Field(default=None, ge=1, le=100, strict=True)
    expiresAt: datetime | None = None


def for_guest(request, session, operation):
    settings = request.app.state.settings
    with session.begin():
        guest = authenticated_guest(session, settings, read_token(request, settings))
        result = operation(guest, settings)
    if isinstance(result, AccessError):
        raise result
    return result


@router.post("/payments/mock/initiate", status_code=201)
def initiate_payment(payload: PaymentRequest, request: Request, session: DatabaseSession):
    return for_guest(
        request,
        session,
        lambda guest, settings: initiate(
            session, settings, guest, payload.provider, payload.idempotencyKey
        ),
    )


@router.get("/payments/{payment_id}/status")
def payment_status(payment_id: UUID, request: Request, session: DatabaseSession):
    def lookup(guest, settings):
        if not settings.mock_allowed:
            raise AccessError("MOCK_DISABLED", 403)
        row = session.scalar(
            select(PaymentTransaction).where(
                PaymentTransaction.id == payment_id, PaymentTransaction.guest_session_id == guest.id
            )
        )
        if row is None:
            raise AccessError("PAYMENT_NOT_FOUND", 404)
        return payment_view(row)

    return for_guest(request, session, lookup)


@router.post("/promos/redeem")
def redeem_code(payload: PromoRequest, request: Request, session: DatabaseSession):
    return for_guest(request, session, lambda guest, _: redeem(session, guest, payload.code))


@router.get("/exam-access/me")
def access(request: Request, session: DatabaseSession):
    def state(guest, settings):
        query = select(ExamEntitlement).where(ExamEntitlement.guest_session_id == guest.id)
        if not settings.mock_allowed:
            query = query.where(ExamEntitlement.promo_id.is_not(None))
        grants = session.scalars(
            query.order_by(
                (ExamEntitlement.status == "AVAILABLE").desc(),
                ExamEntitlement.created_at.desc(),
                ExamEntitlement.id,
            ).limit(50)
        ).all()
        from app.models import Student

        student = session.get(Student, guest.student_id)
        available = any(grant.status == "AVAILABLE" for grant in grants)
        bank_ready, bank_reason = readiness(session, guest.id, audit=False)
        exam_ready = available and bank_ready
        return {
            "fullName": student.full_name,
            "phoneNumber": student.phone_number,
            "mockEnabled": settings.mock_allowed,
            "accessStatus": "ACTIVE" if available else "INACTIVE",
            "bankReady": bank_ready,
            "bankReason": bank_reason,
            "examReady": exam_ready,
            "reason": (
                None
                if exam_ready
                else "ACCESS_REQUIRED"
                if not available
                else "EXAM_UNAVAILABLE"
            ),
            "entitlements": [grant_view(row) for row in grants],
        }

    return for_guest(request, session, state)


@router.post("/admin/promo-codes", status_code=201)
def generate(payload: CreatePromo, admin: Admin, session: DatabaseSession):
    with session.begin():
        return new_promo(
            session,
            admin.id,
            payload.code,
            payload.usageLimit,
            payload.expiresInHours,
        )


@router.get("/admin/promo-codes")
def list_promos(_admin: Admin, session: DatabaseSession, offset: int = 0):
    if not 0 <= offset <= 100000:
        raise AccessError("INVALID_OFFSET", 422)
    timestamp = now(session)
    used = select(func.count()).where(ExamEntitlement.promo_id == PromoCode.id).correlate(PromoCode)
    rows = session.execute(
        select(PromoCode, used.scalar_subquery())
        .where(PromoCode.deleted_at.is_(None))
        .order_by(PromoCode.created_at.desc(), PromoCode.id)
        .offset(offset)
        .limit(51)
    ).all()
    return {
        "items": [promo_view(row, count, timestamp) for row, count in rows[:50]],
        "hasMore": len(rows) > 50,
    }


@router.post("/admin/promo-codes/{promo_id}/disable")
def disable(promo_id: UUID, _admin: Admin, session: DatabaseSession):
    with session.begin():
        return disable_promo(session, promo_id)


@router.post("/admin/promo-codes/{promo_id}/enable")
def enable(promo_id: UUID, _admin: Admin, session: DatabaseSession):
    with session.begin():
        return enable_promo(session, promo_id)


@router.patch("/admin/promo-codes/{promo_id}")
def edit(promo_id: UUID, payload: UpdatePromo, _admin: Admin, session: DatabaseSession):
    changes = {}
    if payload.code is not None:
        changes["code"] = payload.code
    if payload.usageLimit is not None:
        changes["usage_limit"] = payload.usageLimit
    if payload.expiresAt is not None:
        changes["expires_at"] = payload.expiresAt
    with session.begin():
        return update_promo(session, promo_id, **changes)


@router.delete("/admin/promo-codes/{promo_id}")
def remove(promo_id: UUID, _admin: Admin, session: DatabaseSession):
    with session.begin():
        return delete_promo(session, promo_id)


@router.get("/admin/promo-codes/{promo_id}/redemptions")
def redemptions(promo_id: UUID, _admin: Admin, session: DatabaseSession):
    if session.get(PromoCode, promo_id) is None:
        raise AccessError("PROMO_NOT_FOUND", 404)
    rows = session.scalars(
        select(ExamEntitlement)
        .where(ExamEntitlement.promo_id == promo_id)
        .order_by(ExamEntitlement.created_at.desc())
    ).all()
    return [
        {
            "id": row.id,
            "createdAt": row.created_at,
            "status": row.status,
            "accessStatus": "ACTIVE" if row.status == "AVAILABLE" else "INACTIVE",
        }
        for row in rows
    ]


@router.get("/admin/mock-payments/summary")
def mock_summary(_admin: Admin, session: DatabaseSession):
    rows = session.execute(
        select(PaymentTransaction.status, func.count())
        .where(PaymentTransaction.mode == "MOCK")
        .group_by(PaymentTransaction.status)
    ).all()
    return {"mode": "MOCK", "counts": dict(rows)}
