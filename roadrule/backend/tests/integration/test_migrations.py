import pytest
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from alembic.util.exc import CommandError
from sqlalchemy import inspect, text

from alembic import command

pytestmark = pytest.mark.integration


def test_alembic_upgrade_downgrade_repeatability_and_metadata(database, migration_config):
    baseline_tables = {"alembic_version", "students", "guest_sessions", "student_activity_events"}
    approved = baseline_tables | {
        "admin_users",
        "admin_sessions",
        "admin_audit_events",
        "exam_bank_revisions",
        "exam_bank_questions",
        "exam_attempts",
        "exam_attempt_items",
        "exam_operational_events",
        "exam_timing",
        "refund_requests",
        "exam_results",
        "exam_grading_failures",
        "exam_responses",
        "exam_entitlements",
        "payment_transactions",
        "promo_codes",
        "promo_attempts",
        "pdf_documents",
        "pdf_import_jobs",
        "question_drafts",
        "question_draft_options",
        "question_draft_answers",
        "question_draft_assets",
    }
    # Only empty approved tables in the isolated test database may be downgraded.
    with database.engine.connect() as connection:
        tables = set(inspect(connection).get_table_names())
        assert tables <= approved
        for table in tables - {"alembic_version"}:
            assert connection.execute(text(f'SELECT count(*) FROM "{table}"')).scalar_one() == 0
    command.upgrade(migration_config, "head")
    command.downgrade(migration_config, "20261104_0002")
    with database.engine.connect() as connection:
        assert set(inspect(connection).get_table_names()) == baseline_tables
        assert MigrationContext.configure(connection).get_current_revision() == "20261104_0002"
    command.upgrade(migration_config, "head")
    command.upgrade(migration_config, "head")
    with database.engine.connect() as connection:
        head = ScriptDirectory.from_config(migration_config).get_current_head()
        assert (
            MigrationContext.configure(connection).get_current_revision() == head == "20261106_0010"
        )
        assert (
            connection.execute(text("SELECT current_database()")).scalar_one() == "roadrules_test"
        )
        assert set(inspect(connection).get_table_names()) == approved
    command.check(migration_config)
    command.downgrade(migration_config, "20261104_0002")
    with database.engine.connect() as connection:
        assert MigrationContext.configure(connection).get_current_revision() == "20261104_0002"
    command.upgrade(migration_config, "head")


def test_invalid_migration_is_reported(database, migration_config):
    with pytest.raises(CommandError):
        command.upgrade(migration_config, "unapproved_revision_does_not_exist")
    with database.engine.connect() as connection:
        assert MigrationContext.configure(connection).get_current_revision() == "20261106_0010"
