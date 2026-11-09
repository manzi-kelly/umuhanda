from sqlalchemy import text

from alembic import context
from app import models  # noqa: F401 -- registers approved metadata for migrations
from app.core.config import MIGRATION_LOCK, get_settings
from app.db.base import Base
from app.db.session import Database

config = context.config
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=get_settings().connection_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def migrate(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    supplied = config.attributes.get("connection")
    if supplied is not None:
        if not supplied.in_transaction():
            raise RuntimeError("Supplied Alembic connection must have an active transaction.")
        # The setup coordinator holds the session advisory lock on its admin connection.
        migrate(supplied)
        return
    database = Database(get_settings())
    try:
        with database.engine.begin() as connection:
            if not connection.scalar(
                text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": MIGRATION_LOCK}
            ):
                raise RuntimeError("Another database migration or setup is running.")
            migrate(connection)
    finally:
        database.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
