from fastapi import APIRouter

from app.api.v1.admin import router as admin_router
from app.api.v1.admin_analytics import router as analytics_router
from app.api.v1.exam_access import router as access_router
from app.api.v1.exam_execution import router as execution_router
from app.api.v1.exam_results import router as results_router
from app.api.v1.health import router as health_router
from app.api.v1.pdf_import import router as pdf_router
from app.api.v1.student_sessions import router as student_sessions_router

router = APIRouter(prefix="/api/v1")
router.include_router(health_router)
router.include_router(student_sessions_router)
router.include_router(admin_router)

router.include_router(pdf_router)

router.include_router(access_router)

router.include_router(execution_router)
router.include_router(results_router)
router.include_router(analytics_router)
