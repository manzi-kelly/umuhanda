"""Provision only the existing Railway database. Default mode is read-only."""

import argparse
import os
import ssl
import sys
import warnings
from getpass import GetPassWarning, getpass
from pathlib import Path

import psycopg
from alembic.config import Config
from alembic.script import ScriptDirectory
from psycopg import sql
from sqlalchemy import text
from sqlalchemy.engine import URL

from alembic import command
from app.core.config import MIGRATION_LOCK

HOST = "postgres.railway.internal"
DATABASE = "railway"
MARKER = "roadrules-production-setup-v1"
ROOT = Path(__file__).resolve().parents[1]
DELETE_TABLES = {"question_draft_answers", "question_drafts"}
UPDATE_TABLES = {
    "admin_users",
    "admin_sessions",
    "guest_sessions",
    "payment_transactions",
    "promo_codes",
    "exam_entitlements",
    "exam_bank_revisions",
    "exam_attempts",
    "exam_timing",
    "exam_responses",
    "pdf_documents",
    "pdf_import_jobs",
}
INSERT_TABLES = {
    "admin_users",
    "admin_sessions",
    "admin_audit_events",
    "students",
    "guest_sessions",
    "student_activity_events",
    "payment_transactions",
    "promo_codes",
    "exam_entitlements",
    "promo_attempts",
    "exam_bank_revisions",
    "exam_bank_questions",
    "exam_attempts",
    "exam_attempt_items",
    "exam_operational_events",
    "exam_timing",
    "exam_responses",
    "exam_results",
    "exam_grading_failures",
    "pdf_documents",
    "pdf_import_jobs",
    "question_drafts",
    "question_draft_options",
    "question_draft_answers",
    "question_draft_assets",
}
LARGE_OBJECT_CREATORS = (
    "pg_catalog.lo_creat(integer)",
    "pg_catalog.lo_create(oid)",
    "pg_catalog.lo_from_bytea(oid, bytea)",
    "pg_catalog.lo_import(text)",
    "pg_catalog.lo_import(text, oid)",
)
TABLE_PRIVILEGES = (
    "SELECT",
    "INSERT",
    "UPDATE",
    "DELETE",
    "TRUNCATE",
    "REFERENCES",
    "TRIGGER",
    "MAINTAIN",
)


class SetupError(Exception):
    """Safe operator-facing failure."""


def read_password(prompt):
    with warnings.catch_warnings():
        warnings.simplefilter("error", GetPassWarning)
        try:
            return getpass(prompt)
        except GetPassWarning:
            raise SetupError("A terminal with masked password input is required.") from None


def connect(role, password, ca):
    return psycopg.connect(
        host=HOST,
        dbname=DATABASE,
        user=role,
        password=password,
        sslmode="verify-full",
        sslrootcert=str(ca),
        gssencmode="disable",
        connect_timeout=5,
        autocommit=True,
    )


def require_tls(connection):
    tls_status = connection.execute(
        "SELECT ssl FROM pg_catalog.pg_stat_ssl WHERE pid = pg_backend_pid()"
    ).fetchone()
    if tls_status is None or tls_status[0] is not True:
        raise SetupError("Verified TLS is required.")


def inspect(connection, scripts, migrator):
    database, user, version = connection.execute(
        "SELECT current_database(), current_user, current_setting('server_version_num')"
    ).fetchone()
    if (database, user) != (DATABASE, "postgres") or not 180000 <= int(version) < 190000:
        raise SetupError("Unexpected PostgreSQL identity or version.")
    require_tls(connection)
    objects = connection.execute(
        """SELECT c.relname, pg_get_userbyid(c.relowner), c.relkind
           FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
           WHERE n.nspname='public' AND c.relkind IN ('r','p','v','m','f','S')
           UNION ALL
           SELECT p.proname, pg_get_userbyid(p.proowner), 'function'
           FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
           WHERE n.nspname='public'
           ORDER BY 1"""
    ).fetchall()
    existing = {name for name, _, _ in objects}
    if any(kind == "S" for _, _, kind in objects):
        raise SetupError("Unexpected sequence. Review its ownership and required privileges.")
    revision = None
    if any(name == "alembic_version" and kind == "r" for name, _, kind in objects):
        versions = connection.execute("SELECT version_num FROM public.alembic_version").fetchall()
        if len(versions) != 1 or scripts.get_revision(versions[0][0]) is None:
            raise SetupError("Unrecognized migration state. Review ownership and history.")
        revision = versions[0][0]
    elif existing:
        raise SetupError("Existing public relations without Alembic history. Review manually.")
    if any(owner != migrator for _, owner, _ in objects):
        raise SetupError("Existing public relations have another owner. Review manually.")
    print(f"Database={database} PostgreSQL={version} TLS=verified public_relations={len(objects)}")
    print(f"Current revision={revision or 'empty'} repository head={scripts.get_current_head()}")
    return revision


def role_state(connection, role):
    return connection.execute(
        """SELECT r.rolcanlogin, r.rolsuper, r.rolcreatedb, r.rolcreaterole,
                  r.rolreplication, r.rolbypassrls, r.rolinherit,
                  shobj_description(r.oid, 'pg_authid'),
                  EXISTS (SELECT 1 FROM pg_auth_members m
                          WHERE m.member=r.oid OR m.roleid=r.oid)
           FROM pg_roles r WHERE r.rolname=%s""",
        (role,),
    ).fetchone()


def ensure_role(connection, role, password):
    state = role_state(connection, role)
    if state is not None:
        if state != (True, False, False, False, False, False, False, MARKER, False):
            raise SetupError("Existing role is unmanaged or has unexpected privileges.")
        return
    verifier = connection.pgconn.encrypt_password(
        password.encode(), role.encode(), b"scram-sha-256"
    ).decode()
    connection.execute(
        sql.SQL(
            "CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
            "NOREPLICATION NOBYPASSRLS NOINHERIT PASSWORD {}"
        ).format(sql.Identifier(role), sql.Literal(verifier))
    )
    connection.execute(
        sql.SQL("COMMENT ON ROLE {} IS {}").format(sql.Identifier(role), sql.Literal(MARKER))
    )


def admin_query(connection, statement, params):
    return connection.execute(
        statement.replace(":role", "%(role)s").replace(":creators", "%(creators)s"), params
    ).fetchone()[0]


def audit_runtime(query, role):
    forbidden = query(
        """SELECT has_database_privilege(:role, current_database(), 'CREATE')
               OR has_database_privilege(:role, current_database(), 'TEMP')
               OR EXISTS (SELECT 1 FROM pg_namespace WHERE
                   has_schema_privilege(:role, oid, 'CREATE'))
               OR EXISTS (SELECT 1 FROM pg_shdepend WHERE refclassid='pg_authid'::regclass
                   AND refobjid=CAST(:role AS regrole) AND deptype='o')
               OR EXISTS (SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
                   WHERE p.prosecdef AND n.nspname NOT IN ('pg_catalog','information_schema')
                   AND has_schema_privilege(:role, n.oid, 'USAGE')
                   AND has_function_privilege(:role, p.oid, 'EXECUTE'))
               OR EXISTS (SELECT 1 FROM unnest(CAST(:creators AS text[])) AS f(signature)
                   WHERE has_function_privilege(:role, to_regprocedure(f.signature), 'EXECUTE'))""",
        {"role": role, "creators": list(LARGE_OBJECT_CREATORS)},
    )
    if forbidden:
        raise SetupError(
            "Runtime has effective CREATE, TEMP, ownership, or object-creating routine access."
        )


def provision_schema(config, settings, runtime, migrator, head):
    from app import models  # noqa: F401
    from app.db.base import Base
    from app.db.session import Database

    if set(Base.metadata.tables) != INSERT_TABLES | {"refund_requests"}:
        raise SetupError("Application table inventory changed. Review runtime privileges first.")
    database = Database(settings)
    try:
        with database.engine.begin() as connection:
            connection.execute(text("SET LOCAL search_path TO public"))
            if connection.scalar(text("SELECT current_user")) != migrator:
                raise SetupError("Migration connection identity mismatch.")
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
            command.check(config)
            revision = connection.scalar(text("SELECT version_num FROM public.alembic_version"))
            if revision != head:
                raise SetupError("Alembic did not reach the expected head.")
            for table in sorted(Base.metadata.tables):
                privileges = {"SELECT", "INSERT"} if table in INSERT_TABLES else set()
                if table in UPDATE_TABLES:
                    privileges.add("UPDATE")
                if table in DELETE_TABLES:
                    privileges.add("DELETE")
                relation = sql.Identifier("public", table).as_string()
                role = sql.Identifier(runtime).as_string()
                connection.exec_driver_sql(f"REVOKE ALL ON TABLE {relation} FROM {role}")
                if privileges:
                    grants = ", ".join(sorted(privileges))
                    connection.exec_driver_sql(f"GRANT {grants} ON TABLE {relation} TO {role}")
                for privilege in TABLE_PRIVILEGES:
                    allowed = connection.scalar(
                        text("SELECT has_table_privilege(:role, :relation, :privilege)"),
                        {"role": runtime, "relation": relation, "privilege": privilege},
                    )
                    if privilege not in privileges and privilege in {
                        "SELECT",
                        "INSERT",
                        "UPDATE",
                        "REFERENCES",
                    }:
                        allowed = allowed or connection.scalar(
                            text("SELECT has_any_column_privilege(:role, :relation, :privilege)"),
                            {"role": runtime, "relation": relation, "privilege": privilege},
                        )
                    if privilege in privileges and connection.scalar(
                        text("""
                            SELECT has_table_privilege(:role, :relation, :grant_option)
                            OR CASE WHEN :column_privilege THEN
                                has_any_column_privilege(:role, :relation, :grant_option)
                                ELSE false END
                        """),
                        {
                            "role": runtime,
                            "relation": relation,
                            "grant_option": f"{privilege} WITH GRANT OPTION",
                            "column_privilege": privilege in {"SELECT", "INSERT", "UPDATE"},
                        },
                    ):
                        raise SetupError("Runtime can delegate application table privileges.")
                    if allowed != (privilege in privileges):
                        raise SetupError("Runtime table grants differ from the audited policy.")
            if connection.scalar(
                text("""
                SELECT EXISTS (
                    SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                    WHERE n.nspname='public' AND (c.relkind='S' OR
                        (c.relkind IN ('r','p','v','m','f') AND c.relowner<>current_user::regrole))
                    UNION ALL
                    SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
                    WHERE n.nspname='public' AND p.proowner<>current_user::regrole
                )
            """)
            ):
                raise SetupError("Migration ownership mismatch or an unaudited sequence exists.")
            if connection.scalar(
                text("""
                    SELECT EXISTS (SELECT 1 FROM unnest(ARRAY[
                        'SELECT','INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER','MAINTAIN'
                    ]) AS p WHERE has_table_privilege(:role, 'public.alembic_version', p))
                    OR EXISTS (SELECT 1 FROM unnest(ARRAY['SELECT','INSERT','UPDATE','REFERENCES'])
                        AS p WHERE has_any_column_privilege(:role, 'public.alembic_version', p))
                """),
                {"role": runtime},
            ):
                raise SetupError("Runtime has unexpected access to Alembic history.")
            audit_runtime(
                lambda statement, params: connection.scalar(text(statement), params), runtime
            )
    finally:
        config.attributes.pop("connection", None)
        database.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ca", type=Path, required=True)
    parser.add_argument("--runtime", required=True)
    parser.add_argument("--migrator", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--revoke-public-temp", action="store_true")
    parser.add_argument("--revoke-public-large-objects", action="store_true")
    parser.add_argument("--api-host")
    parser.add_argument("--frontend-origin")
    args = parser.parse_args()
    if not sys.stdin.isatty():
        parser.error("Run in an interactive Railway SSH terminal for masked password prompts.")
    if args.apply and not (args.api_host and args.frontend_origin):
        parser.error("--apply requires --api-host and --frontend-origin.")
    roles = (args.runtime, args.migrator)
    if len(set(roles)) != 2 or any(
        not role.isascii()
        or not role.isidentifier()
        or role != role.lower()
        or len(role) > 63
        or role in {"postgres", "root"}
        or role.startswith("pg_")
        for role in roles
    ):
        parser.error("Use two distinct lowercase application role identifiers.")
    if not args.ca.is_absolute() or not args.ca.is_file():
        parser.error("Supply the verified CA as an absolute runtime file path.")
    try:
        ssl.create_default_context(cafile=str(args.ca))
    except (OSError, ValueError):
        parser.error("The verified CA must be readable PEM.")
    os.chdir(ROOT)
    config = Config(str(ROOT / "alembic.ini"))
    scripts = ScriptDirectory.from_config(config)
    with connect("postgres", read_password("Postgres operator password: "), args.ca) as admin:
        inspect(admin, scripts, args.migrator)
        for label, role in zip(("Runtime", "Migration"), roles, strict=True):
            print(f"{label} role {'exists' if role_state(admin, role) else 'is absent'}")
        if not args.apply:
            return
        if (
            input("Confirm verified backup and approved changes. Type APPLY railway: ")
            != "APPLY railway"
        ):
            raise SetupError("Approval phrase did not match.")
        if (
            args.revoke_public_temp
            and input("This affects all roles inheriting TEMP. Type REVOKE PUBLIC TEMP railway: ")
            != "REVOKE PUBLIC TEMP railway"
        ):
            raise SetupError("The PUBLIC TEMP change was not approved.")
        if (
            args.revoke_public_large_objects
            and input(
                "This affects inherited large-object access. "
                "Type REVOKE PUBLIC LARGE OBJECT railway: "
            )
            != "REVOKE PUBLIC LARGE OBJECT railway"
        ):
            raise SetupError("The PUBLIC large-object change was not approved.")
        passwords = {role: read_password(f"Password for {role}: ") for role in roles}
        if (
            any(len(password) < 20 for password in passwords.values())
            or len(set(passwords.values())) != 2
        ):
            raise SetupError("Use distinct role passwords with at least 20 characters.")
        os.environ["APP_ENV"] = "production"
        os.environ["DATABASE_URL"] = URL.create(
            "postgresql+psycopg",
            username=args.migrator,
            password=passwords[args.migrator],
            host=HOST,
            database=DATABASE,
            query={"sslmode": "verify-full", "sslrootcert": str(args.ca)},
        ).render_as_string(hide_password=False)
        os.environ.pop("TEST_DATABASE_URL", None)
        os.environ["ALLOWED_HOSTS"] = f"{args.api_host},healthcheck.railway.app"
        os.environ["CORS_ALLOWED_ORIGINS"] = args.frontend_origin
        from app.core.config import Settings

        settings = Settings()
        if not admin.execute("SELECT pg_try_advisory_lock(%s)", (MIGRATION_LOCK,)).fetchone()[0]:
            raise SetupError("Another production setup is running.")
        inspect(admin, scripts, args.migrator)
        with admin.transaction():
            for role in roles:
                ensure_role(admin, role, passwords[role])
                admin.execute(
                    sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                        sql.Identifier(DATABASE), sql.Identifier(role)
                    )
                )
            admin.execute(
                sql.SQL("GRANT USAGE, CREATE ON SCHEMA public TO {}").format(
                    sql.Identifier(args.migrator)
                )
            )
            admin.execute(
                sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(args.runtime))
            )
            if args.revoke_public_temp:
                admin.execute(
                    sql.SQL("REVOKE TEMP ON DATABASE {} FROM PUBLIC").format(
                        sql.Identifier(DATABASE)
                    )
                )
            if args.revoke_public_large_objects:
                # Signatures are fixed, audited constants rather than operator input.
                creators = ", ".join(LARGE_OBJECT_CREATORS)
                admin.execute(f"REVOKE EXECUTE ON FUNCTION {creators} FROM PUBLIC")
            audit_runtime(
                lambda statement, params: admin_query(admin, statement, params), args.runtime
            )
        with connect(args.runtime, passwords[args.runtime], args.ca) as runtime:
            require_tls(runtime)
        with connect(args.migrator, passwords[args.migrator], args.ca) as migration:
            require_tls(migration)
        print("Role checkpoint committed. Starting transactional schema and ACL checkpoint.")
        try:
            provision_schema(
                config, settings, args.runtime, args.migrator, scripts.get_current_head()
            )
        except Exception:
            print("Schema checkpoint failed. Inspect the persisted revision before retrying.")
            try:
                inspect(admin, scripts, args.migrator)
            except Exception:
                print("Persisted revision could not be inspected. Stop for operator review.")
            raise
        inspect(admin, scripts, args.migrator)
        print("Schema and runtime grants applied. Stage Railway variables separately.")


if __name__ == "__main__":
    try:
        main()
    except (Exception, KeyboardInterrupt) as error:
        if isinstance(error, SetupError):
            print(str(error))
        else:
            print(
                f"Setup stopped ({type(error).__name__}); "
                f"SQLSTATE={getattr(error, 'sqlstate', None)}."
            )
        raise SystemExit(1) from None
