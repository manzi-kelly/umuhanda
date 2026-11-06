from contextlib import asynccontextmanager
from time import perf_counter

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.v1.router import router
from app.core.admin_security import (
    ADMIN_PATH,
    AdminLoginLimited,
    AdminUnauthorized,
    clear_admin_cookie,
)
from app.core.config import Settings, get_settings
from app.core.session_security import (
    SESSION_PATH,
    InvalidGuestSession,
    SessionCreationLimited,
    clear_guest_cookie,
    session_request_allowed,
)
from app.db.session import Database
from app.services.exam_access import AccessError
from app.services.pdf.storage import PdfError


def error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code, content={"error": {"code": code, "message": message}}
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.database = Database(settings)
        try:
            yield
        finally:
            app.state.database.dispose()

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        debug=False,
        lifespan=lifespan,
        docs_url="/docs" if settings.docs_enabled else None,
        redoc_url="/redoc" if settings.docs_enabled else None,
        openapi_url="/openapi.json" if settings.docs_enabled else None,
    )
    app.state.settings = settings
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)

    @app.exception_handler(AccessError)
    async def access_error(_request: Request, error: AccessError):
        response = error_response(
            error.status, error.code, "Access request could not be completed."
        )
        if error.status == 429:
            response.headers["Retry-After"] = "300"
        return response

    @app.exception_handler(PdfError)
    async def pdf_error(_request: Request, error: PdfError):
        response = error_response(error.status, error.code, "PDF operation could not be completed.")
        if error.status == 429:
            response.headers["Retry-After"] = str(settings.pdf_upload_window_seconds)
        return response

    @app.exception_handler(AdminUnauthorized)
    async def admin_unauthorized(_request: Request, _error: AdminUnauthorized):
        response = error_response(
            401, "ADMIN_AUTH_REQUIRED", "Administrator authentication failed."
        )
        clear_admin_cookie(response, settings)
        return response

    @app.exception_handler(AdminLoginLimited)
    async def admin_limited(_request: Request, _error: AdminLoginLimited):
        response = error_response(429, "ADMIN_LOGIN_LIMITED", "Please try again later.")
        response.headers["Retry-After"] = str(settings.admin_login_window_seconds)
        return response

    @app.exception_handler(InvalidGuestSession)
    async def invalid_session(_request: Request, _error: InvalidGuestSession) -> JSONResponse:
        response = error_response(
            401, "GUEST_SESSION_REQUIRED", "A valid guest session is required."
        )
        clear_guest_cookie(response, settings)
        return response

    @app.exception_handler(SessionCreationLimited)
    async def creation_limited(_request: Request, _error: SessionCreationLimited) -> JSONResponse:
        response = error_response(429, "SESSION_CREATION_LIMITED", "Please try again later.")
        response.headers["Retry-After"] = str(settings.session_creation_window_seconds)
        return response

    @app.exception_handler(SQLAlchemyError)
    async def database_error(_request: Request, _error: SQLAlchemyError) -> JSONResponse:
        return error_response(503, "DATABASE_UNAVAILABLE", "Database service is unavailable.")

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, _error: RequestValidationError) -> JSONResponse:
        # Do not reflect raw request values, secrets or internal validation context.
        return error_response(422, "VALIDATION_ERROR", "Request validation failed.")

    @app.exception_handler(HTTPException)
    async def http_error(_request: Request, error: HTTPException) -> JSONResponse:
        return error_response(
            error.status_code, "HTTP_ERROR", "The request could not be completed."
        )

    @app.middleware("http")
    async def safe_errors(request: Request, call_next):
        started = perf_counter()
        # Handle before ServerErrorMiddleware can re-raise into server traceback logs.
        is_session = (
            request.url.path.rstrip("/") == SESSION_PATH
            or request.url.path.startswith(SESSION_PATH + "/")
            or request.url.path.startswith(
                (
                    "/api/v1/payments/",
                    "/api/v1/promos/",
                    "/api/v1/exam-access/",
                    "/api/v1/exams/",
                    "/api/v1/students/exams/",
                )
            )
        )
        is_admin = request.url.path == ADMIN_PATH or request.url.path.startswith(ADMIN_PATH + "/")
        try:
            if (is_session or is_admin) and not session_request_allowed(request, settings):
                response = error_response(
                    403, "ORIGIN_REJECTED", "Request origin or CSRF protection is invalid."
                )
            else:
                response = await call_next(request)
        except Exception:
            response = error_response(500, "INTERNAL_ERROR", "An unexpected error occurred.")
        if is_session or is_admin:
            if settings.app_env in {"development", "testing"}:
                response.headers["Server-Timing"] = (
                    f"api;dur={(perf_counter() - started) * 1000:.2f}"
                )
            response.headers["Cache-Control"] = "no-store"
            response.headers["Pragma"] = "no-cache"
            response.headers["Referrer-Policy"] = "no-referrer"
        return response

    app.include_router(router)
    # Outermost user middleware also adds CORS to safe handled error responses.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Accept", "Content-Type", "X-CSRF-Protection", "X-PDF-Filename"],
    )
    original_openapi = app.openapi

    def session_openapi():
        schema = original_openapi()
        schema.setdefault("components", {}).setdefault("securitySchemes", {})["GuestCookie"] = {
            "type": "apiKey",
            "in": "cookie",
            "name": settings.guest_cookie_name,
        }
        schema["components"]["securitySchemes"]["AdminCookie"] = {
            "type": "apiKey",
            "in": "cookie",
            "name": settings.admin_cookie_name,
        }
        return schema

    app.openapi = session_openapi
    return app
