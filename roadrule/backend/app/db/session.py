from collections.abc import Iterator

from fastapi import Request
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings


class Database:
    def __init__(self, settings: Settings):
        # Engine creation is lazy: an unavailable database cannot break liveness.
        self.engine = create_engine(
            settings.connection_url,
            pool_pre_ping=True,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_timeout=settings.db_pool_timeout,
            pool_recycle=1800,
            hide_parameters=True,
            echo=False,
            isolation_level="READ COMMITTED",
            connect_args={
                "connect_timeout": settings.db_connect_timeout,
                "application_name": "roadrules_api",
                "options": (
                    f"-c statement_timeout={settings.db_statement_timeout_ms} -c timezone=UTC"
                ),
            },
        )
        self.session_factory = sessionmaker(
            bind=self.engine, autoflush=False, expire_on_commit=False
        )

    def dispose(self) -> None:
        self.engine.dispose()


def get_session(request: Request) -> Iterator[Session]:
    """No implicit commit; services must commit deliberate writes explicitly."""
    with request.app.state.database.session_factory() as session:
        try:
            yield session
        except Exception:
            session.rollback()
            raise
        # Session.close() also rolls back uncommitted work on successful requests.
