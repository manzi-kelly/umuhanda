"""Only current-question projections cross the student API boundary."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from app.api.v1.admin import DatabaseSession, require_admin
from app.api.v1.exam_access import for_guest
from app.core.session_security import read_token
from app.models.exam_bank import ExamOperationalEvent
from app.schemas.admin import AdminIdentity
from app.services.exam_access import AccessError, now, start_with_entitlement
from app.services.exam_execution import (
    close_question,
    find_attempt,
    image_bytes,
    initialize_attempt,
    operational_summary,
    reconcile,
    save_answer,
    student_view,
)
from app.services.exam_generation import ExamUnavailable

router = APIRouter(tags=["timed exam"])


class StartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entitlementId: UUID


class QuestionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    position: int = Field(ge=1, le=20, strict=True)


class AnswerRequest(QuestionRequest):
    optionId: int = Field(ge=0, le=3, strict=True)
    answerVersion: int = Field(ge=0, le=2147483646, strict=True)


def execute(request, session, identifier, operation=None):
    def action(guest, settings):
        found = find_attempt(session, guest, identifier)
        if found is None:
            return AccessError("EXAM_NOT_FOUND", 404) if identifier is not None else {"exam": None}
        attempt, timing = found
        timestamp = now(session)
        current = reconcile(session, attempt, timing, timestamp)
        if operation:
            result = operation(settings, attempt, timing, current, timestamp)
            if result is not None:
                return result
        return {"exam": student_view(session, attempt, timing, current, timestamp)}

    return for_guest(request, session, action)


@router.post("/exams/start")
def start(payload: StartRequest, request: Request, session: DatabaseSession):
    settings = request.app.state.settings
    result = start_with_entitlement(
        session,
        settings,
        read_token(request, settings),
        payload.entitlementId,
        initialize=initialize_attempt,
    )
    if isinstance(result, ExamUnavailable):
        with session.begin():
            session.add(ExamOperationalEvent(code="TIMED_START_UNAVAILABLE"))
        raise AccessError("EXAM_UNAVAILABLE", 503)
    return execute(request, session, UUID(result["id"]))


@router.get("/exams/me")
def my_exam(request: Request, session: DatabaseSession):
    return execute(request, session, None)


@router.get("/exams/{attempt_id}/current")
def current_exam(attempt_id: UUID, request: Request, session: DatabaseSession):
    return execute(request, session, attempt_id)


@router.put("/exams/{attempt_id}/answer")
def answer(attempt_id: UUID, payload: AnswerRequest, request: Request, session: DatabaseSession):
    def save(_settings, attempt, timing, current, timestamp):
        if current is None:
            return AccessError("EXAM_COMPLETED")
        if timing.position != payload.position:
            return AccessError("STALE_QUESTION")
        return save_answer(
            session, attempt, current, payload.optionId, payload.answerVersion, timestamp
        )

    return execute(request, session, attempt_id, save)


@router.post("/exams/{attempt_id}/next")
def next_question(
    attempt_id: UUID, payload: QuestionRequest, request: Request, session: DatabaseSession
):
    def advance(_settings, attempt, timing, current, timestamp):
        if timing.position != payload.position:
            return AccessError("STALE_QUESTION")
        if current is not None:
            current = close_question(session, attempt, timing, current, timestamp, "NEXT")
        return {"exam": student_view(session, attempt, timing, current, timestamp)}

    return execute(request, session, attempt_id, advance)


@router.get("/exams/{attempt_id}/media/{position}/{index}")
def media(
    attempt_id: UUID,
    position: Annotated[int, Path(ge=1, le=20)],
    index: Annotated[int, Path(ge=0, le=19)],
    request: Request,
    session: DatabaseSession,
):
    def read(settings, attempt, timing, current, _timestamp):
        if current is None or position != timing.position:
            return AccessError("MEDIA_NOT_FOUND", 404)
        return image_bytes(session, settings, attempt, position, index)

    data = execute(request, session, attempt_id, read)
    return Response(data, media_type="image/png", headers={"X-Content-Type-Options": "nosniff"})


@router.get("/admin/exam-execution/summary")
def summary(_admin: Annotated[AdminIdentity, Depends(require_admin)], session: DatabaseSession):
    return operational_summary(session)
