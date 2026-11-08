"""Sanitized database failure diagnostics.

Only non-secret routing and error-class information is reported. Raw database
exceptions, connection URLs, usernames and passwords must never reach logs.
"""

import logging

from sqlalchemy.exc import SQLAlchemyError

from app.core.config import Settings

logger = logging.getLogger("roadrules.api")

SQLSTATE_CATEGORIES = {
    "08000": "connection_exception",
    "08001": "connection_unable",
    "08003": "connection_missing",
    "08004": "connection_rejected",
    "08006": "connection_failure",
    "08007": "transaction_resolution_unknown",
    "08P01": "protocol_violation",
    "28000": "invalid_authorization",
    "28P01": "invalid_password",
    "3D000": "database_missing",
    "42501": "insufficient_privilege",
    "53300": "too_many_connections",
    "57014": "statement_timeout",
    "57P01": "admin_shutdown",
    "57P02": "crash_shutdown",
    "57P03": "cannot_connect_now",
}


def database_failure_context(settings: Settings, error: SQLAlchemyError) -> dict[str, str]:
    """Return safe, structured diagnostics for a failed database operation."""
    original = getattr(error, "orig", None)
    sqlstate = None
    if original is not None:
        try:
            sqlstate = getattr(original, "sqlstate", None) or getattr(original, "pgcode", None)
        except Exception:
            sqlstate = None
    sqlstate_text = str(sqlstate) if sqlstate else "unknown"

    try:
        url = settings.connection_url
        target = f"{url.host}:{url.port or 5432}/{url.database}"
        ssl_mode = str(url.query.get("sslmode", "prefer"))
    except Exception:
        target = "unknown"
        ssl_mode = "unknown"

    return {
        "error": type(error).__name__,
        "driver_error": type(original).__name__ if original is not None else "none",
        "sqlstate": sqlstate_text,
        "category": SQLSTATE_CATEGORIES.get(sqlstate_text, "unclassified"),
        "target": target,
        "ssl_mode": ssl_mode,
        "connection_invalidated": str(
            bool(getattr(error, "connection_invalidated", False))
        ).lower(),
    }


def log_database_failure(settings: Settings, error: SQLAlchemyError) -> None:
    """Log a warning without exception text, credentials or query parameters."""
    context = database_failure_context(settings, error)
    logger.warning(
        "database_unavailable error=%s driver_error=%s sqlstate=%s category=%s "
        "target=%s ssl_mode=%s connection_invalidated=%s",
        context["error"],
        context["driver_error"],
        context["sqlstate"],
        context["category"],
        context["target"],
        context["ssl_mode"],
        context["connection_invalidated"],
    )
