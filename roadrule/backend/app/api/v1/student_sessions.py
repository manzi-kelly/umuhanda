from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.core.session_security import clear_guest_cookie, read_token, set_guest_cookie
from app.db.session import get_session
from app.schemas.student_sessions import StudentSessionRequest, StudentSessionResponse
from app.services.student_sessions import StudentSessionService

router = APIRouter(prefix="/students/sessions", tags=["student sessions"])
CSRF_DOCS = {
    "parameters": [
        {"in": "header", "name": "Origin", "required": True, "schema": {"type": "string"}},
        {
            "in": "header",
            "name": "X-CSRF-Protection",
            "required": True,
            "schema": {"type": "string", "const": "1"},
        },
    ]
}


@router.post("", status_code=201, response_model=StudentSessionResponse, openapi_extra=CSRF_DOCS)
def create(
    payload: StudentSessionRequest,
    request: Request,
    response: Response,
    session: Annotated[Session, Depends(get_session)],
) -> StudentSessionResponse:
    settings = request.app.state.settings
    result, token = StudentSessionService(session, settings).create(payload)
    set_guest_cookie(response, token, result.expiresAt, settings)
    return result


@router.get(
    "/me", response_model=StudentSessionResponse, openapi_extra={"security": [{"GuestCookie": []}]}
)
def me(
    request: Request, session: Annotated[Session, Depends(get_session)]
) -> StudentSessionResponse:
    settings = request.app.state.settings
    return StudentSessionService(session, settings).authenticate(read_token(request, settings))


@router.post(
    "/revoke", status_code=204, openapi_extra={**CSRF_DOCS, "security": [{"GuestCookie": []}]}
)
def revoke(request: Request, session: Annotated[Session, Depends(get_session)]) -> Response:
    settings = request.app.state.settings
    StudentSessionService(session, settings).authenticate(
        read_token(request, settings), revoke=True
    )
    response = Response(status_code=204)
    clear_guest_cookie(response, settings)
    return response
