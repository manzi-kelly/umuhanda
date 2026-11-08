"""Run only on the disposable PostgreSQL cluster provisioned for this ACL test."""

import os
from pathlib import Path

import psycopg
import pytest
from alembic.config import Config
from sqlalchemy.engine import make_url

from app.core.config import Settings
from scripts import setup_railway_production as setup

pytestmark = pytest.mark.integration


def test_transactional_bootstrap_and_effective_acl(monkeypatch):
    dsn = os.getenv("RR_SETUP_TEST_ADMIN")
    if not dsn:
        pytest.skip("Requires the dedicated local ACL test cluster.")
    target = make_url(dsn)
    assert (target.host, target.port, target.database) == (
        "127.0.0.1",
        55447,
        "roadrules_setup_test",
    )
    runtime, migrator = "acl_runtime", "acl_migrator"
    password = "local-fixture-password-only"
    settings = Settings().model_copy(
        update={
            "app_env": "development",
            "database_url": target.set(
                drivername="postgresql+psycopg", username=migrator, password=password
            ).render_as_string(hide_password=False),
        }
    )
    from pydantic import SecretStr

    settings = settings.model_copy(update={"database_url": SecretStr(settings.database_url)})
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    with psycopg.connect(dsn, autocommit=True) as admin:
        assert admin.execute("SELECT current_database()").fetchone() == ("roadrules_setup_test",)
        for role in (runtime, migrator):
            setup.ensure_role(admin, role, password)
        with pytest.raises(setup.SetupError, match="effective"):
            setup.audit_runtime(
                lambda query, params: setup.admin_query(admin, query, params), runtime
            )
        admin.execute("REVOKE TEMP ON DATABASE roadrules_setup_test FROM PUBLIC")
        with pytest.raises(setup.SetupError, match="effective"):
            setup.audit_runtime(
                lambda query, params: setup.admin_query(admin, query, params), runtime
            )
        creators = ", ".join(setup.LARGE_OBJECT_CREATORS)
        admin.execute(f"REVOKE EXECUTE ON FUNCTION {creators} FROM PUBLIC")
        admin.execute("GRANT USAGE ON SCHEMA public TO acl_runtime")
        admin.execute("GRANT USAGE, CREATE ON SCHEMA public TO acl_migrator")
        check = setup.command.check

        def fail_check(_config):
            raise RuntimeError("injected post-migration failure")

        monkeypatch.setattr(setup.command, "check", fail_check)
        with pytest.raises(RuntimeError, match="injected"):
            setup.provision_schema(config, settings, runtime, migrator, "20261106_0010")
        assert admin.execute("SELECT to_regclass('public.alembic_version')").fetchone() == (None,)
        assert admin.execute("SELECT to_regclass('public.students')").fetchone() == (None,)
        monkeypatch.setattr(setup.command, "check", check)
        for _ in range(2):
            setup.provision_schema(config, settings, runtime, migrator, "20261106_0010")
        assert admin.execute("SELECT version_num FROM public.alembic_version").fetchone() == (
            "20261106_0010",
        )
        assert admin.execute("""
            SELECT tableowner FROM pg_tables WHERE schemaname='public' AND tablename='students'
        """).fetchone() == (migrator,)
        assert admin.execute("""
            SELECT pg_get_userbyid(proowner) FROM pg_proc WHERE proname='guard_exam_history'
        """).fetchone() == (migrator,)
        admin.execute("SET ROLE acl_runtime")
        for statement in (
            "CREATE TABLE public.forbidden(id int)",
            "CREATE TEMP TABLE forbidden(id int)",
            "SELECT pg_catalog.lo_create(0)",
            "ALTER TABLE public.students ADD COLUMN forbidden int",
            "DELETE FROM public.students WHERE false",
            "INSERT INTO public.refund_requests DEFAULT VALUES",
            "SELECT * FROM public.refund_requests",
            "SELECT * FROM public.alembic_version",
        ):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                admin.execute(statement)
        assert admin.execute("SELECT count(*) FROM public.students").fetchone() == (0,)
        admin.execute("RESET ROLE")
        admin.execute("GRANT CREATE ON SCHEMA public TO PUBLIC")
        with pytest.raises(setup.SetupError, match="effective"):
            setup.audit_runtime(
                lambda query, params: setup.admin_query(admin, query, params), runtime
            )
