from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.api.v1.student_sessions import CSRF_DOCS
from app.core.admin_security import admin_token, clear_admin_cookie, set_admin_cookie
from app.db.session import get_session
from app.schemas.admin import AdminIdentity, AdminLoginRequest, DashboardSummary
from app.services.admin_auth import AdminAuthService
from app.services.admin_reporting import dashboard_summary, exam_bank_status

router = APIRouter(prefix="/admin", tags=["admin"])
DatabaseSession = Annotated[Session, Depends(get_session)]


def require_admin(request: Request, session: DatabaseSession) -> AdminIdentity:
    settings = request.app.state.settings
    return AdminAuthService(session, settings).authenticate(admin_token(request, settings))


@router.post("/auth/login", response_model=AdminIdentity, openapi_extra=CSRF_DOCS)
def login(
    payload: AdminLoginRequest, request: Request, response: Response, session: DatabaseSession
):
    settings = request.app.state.settings
    result, token = AdminAuthService(session, settings).login(
        payload, admin_token(request, settings)
    )
    set_admin_cookie(response, token, result.expiresAt, settings)
    return result


@router.get(
    "/auth/me", response_model=AdminIdentity, openapi_extra={"security": [{"AdminCookie": []}]}
)
def me(admin: Annotated[AdminIdentity, Depends(require_admin)]):
    return admin


@router.post(
    "/auth/logout", status_code=204, openapi_extra={**CSRF_DOCS, "security": [{"AdminCookie": []}]}
)
def logout(request: Request, session: DatabaseSession):
    settings = request.app.state.settings
    AdminAuthService(session, settings).authenticate(admin_token(request, settings), logout=True)
    response = Response(status_code=204)
    clear_admin_cookie(response, settings)
    return response


@router.get(
    "/dashboard/summary",
    response_model=DashboardSummary,
    openapi_extra={"security": [{"AdminCookie": []}]},
)
def summary(_admin: Annotated[AdminIdentity, Depends(require_admin)], session: DatabaseSession):
    return dashboard_summary(session)


@router.get("/exam-bank/status", openapi_extra={"security": [{"AdminCookie": []}]})
def bank_status(_admin: Annotated[AdminIdentity, Depends(require_admin)], session: DatabaseSession):
    return exam_bank_status(session)
