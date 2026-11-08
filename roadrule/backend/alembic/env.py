from alembic import context
from app import models  # noqa: F401 -- registers approved metadata for migrations
from app.core.config import get_settings
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
        migrate(supplied)
        return
    database = Database(get_settings())
    try:
        with database.engine.connect() as connection:
            migrate(connection)
    finally:
        database.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
