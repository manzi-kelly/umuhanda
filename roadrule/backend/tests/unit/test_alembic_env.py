import runpy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from alembic import context
from app.core.config import MIGRATION_LOCK
from app.db import session

ENV = Path(__file__).resolve().parents[2] / "alembic" / "env.py"


@pytest.fixture
def migration_environment(monkeypatch):
    connection = MagicMock()
    database = MagicMock()
    database.engine.begin.return_value.__enter__.return_value = connection
    monkeypatch.setattr(session, "Database", lambda _: database)
    monkeypatch.setattr(context, "config", SimpleNamespace(attributes={}), raising=False)
    monkeypatch.setattr(context, "is_offline_mode", lambda: False)
    for method in ("configure", "begin_transaction", "run_migrations"):
        monkeypatch.setattr(context, method, MagicMock())
    return connection, database


@pytest.mark.parametrize("locked", [True, False])
def test_standalone_alembic_shares_setup_lock(migration_environment, locked):
    connection, database = migration_environment
    connection.scalar.return_value = locked
    if locked:
        runpy.run_path(str(ENV))
        context.run_migrations.assert_called_once_with()
    else:
        with pytest.raises(RuntimeError, match="Another database migration or setup"):
            runpy.run_path(str(ENV))
        context.run_migrations.assert_not_called()
    statement, params = connection.scalar.call_args.args
    assert "pg_try_advisory_xact_lock" in str(statement)
    assert params == {"key": MIGRATION_LOCK}
    database.dispose.assert_called_once_with()


@pytest.mark.parametrize("active", [True, False])
def test_supplied_alembic_connection_requires_outer_transaction(migration_environment, active):
    connection, database = migration_environment
    connection.in_transaction.return_value = active
    context.config.attributes["connection"] = connection
    if active:
        runpy.run_path(str(ENV))
        context.configure.assert_called_once()
        context.run_migrations.assert_called_once_with()
    else:
        with pytest.raises(RuntimeError, match="active transaction"):
            runpy.run_path(str(ENV))
        context.run_migrations.assert_not_called()
    connection.scalar.assert_not_called()
    database.engine.begin.assert_not_called()
