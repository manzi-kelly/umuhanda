from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.schemas.health import ErrorResponse, HealthResponse, ReadyResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


@router.get("/ready", response_model=ReadyResponse, responses={503: {"model": ErrorResponse}})
def ready(session: Annotated[Session, Depends(get_session)]) -> ReadyResponse:
    session.execute(text("SELECT 1")).scalar_one()
    return ReadyResponse()
