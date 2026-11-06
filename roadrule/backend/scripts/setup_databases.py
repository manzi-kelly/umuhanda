"""Idempotent creation of dedicated databases/roles; no DROP or password rotation."""

import json
import os
import secrets
import sys
from pathlib import Path

import psycopg
from psycopg import sql
from sqlalchemy.engine import URL, make_url

ROOT = Path(__file__).resolve().parents[1]
MARKER = "Road Rules Phase03A managed development resource"


def connect_url(url: URL) -> str:
    return url.set(drivername="postgresql").render_as_string(hide_password=False)


def setup() -> None:
    local = ROOT / ".local"
    local.mkdir(exist_ok=True)
    external_admin = os.environ.get("ADMIN_DATABASE_URL")
    admin = (
        make_url(external_admin)
        if external_admin
        else URL.create(
            "postgresql",
            username="roadrules_local_admin",
            password=json.loads((local / "admin.json").read_text())["password"],
            host="127.0.0.1",
            port=55432,
            database="postgres",
        )
    )
    passwords_file = local / "application-passwords.json"
    if not passwords_file.exists():
        passwords_file.write_text(
            json.dumps({environment: secrets.token_urlsafe(32) for environment in ("dev", "test")}),
            encoding="utf-8",
        )
        passwords_file.chmod(0o600)
    passwords = json.loads(passwords_file.read_text())
    urls = {}
    with psycopg.connect(connect_url(admin), autocommit=True, connect_timeout=3) as connection:
        # Preflight every name before making changes. Unknown existing resources are preserved.
        for environment in ("dev", "test"):
            database = f"roadrules_{environment}"
            existing = connection.execute(
                "SELECT pg_get_userbyid(datdba), shobj_description(oid, 'pg_database') "
                "FROM pg_database WHERE datname = %s",
                (database,),
            ).fetchone()
            if existing and existing != (f"{database}_owner", MARKER):
                raise RuntimeError(
                    "An unrecognized target database already exists; refusing changes."
                )
            for role in (f"{database}_owner", f"{database}_app"):
                existing_role = connection.execute(
                    "SELECT shobj_description(oid, 'pg_authid'), rolsuper, rolcreatedb, "
                    "rolcreaterole, rolreplication, rolbypassrls FROM pg_roles WHERE rolname = %s",
                    (role,),
                ).fetchone()
                if existing_role and existing_role != (MARKER, False, False, False, False, False):
                    raise RuntimeError(
                        "An unrecognized or privileged role already exists; refusing changes."
                    )
        for environment in ("dev", "test"):
            database = f"roadrules_{environment}"
            owner, role = f"{database}_owner", f"{database}_app"
            for name, login in ((owner, False), (role, True)):
                if not connection.execute(
                    "SELECT 1 FROM pg_roles WHERE rolname = %s", (name,)
                ).fetchone():
                    statement = sql.SQL(
                        "CREATE ROLE {} {} NOSUPERUSER NOCREATEDB NOCREATEROLE "
                        "NOINHERIT NOREPLICATION NOBYPASSRLS"
                    ).format(sql.Identifier(name), sql.SQL("LOGIN" if login else "NOLOGIN"))
                    if login:
                        statement += sql.SQL(" PASSWORD {}").format(
                            sql.Literal(passwords[environment])
                        )
                    connection.execute(statement)
                    connection.execute(
                        sql.SQL("COMMENT ON ROLE {} IS {}").format(
                            sql.Identifier(name), sql.Literal(MARKER)
                        )
                    )
            if not connection.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s", (database,)
            ).fetchone():
                connection.execute(
                    sql.SQL(
                        "CREATE DATABASE {} OWNER {} ENCODING 'UTF8' TEMPLATE template0 "
                        "LC_COLLATE 'C' LC_CTYPE 'C'"
                    ).format(sql.Identifier(database), sql.Identifier(owner))
                )
                connection.execute(
                    sql.SQL("COMMENT ON DATABASE {} IS {}").format(
                        sql.Identifier(database), sql.Literal(MARKER)
                    )
                )
            connection.execute(
                sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(sql.Identifier(database))
            )
            connection.execute(
                sql.SQL("GRANT CONNECT, TEMPORARY ON DATABASE {} TO {}").format(
                    sql.Identifier(database), sql.Identifier(role)
                )
            )
            with psycopg.connect(
                connect_url(admin.set(database=database)), autocommit=True
            ) as target:
                target.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC")
                target.execute(
                    sql.SQL("ALTER SCHEMA public OWNER TO {}").format(sql.Identifier(owner))
                )
                target.execute(
                    sql.SQL("GRANT USAGE, CREATE ON SCHEMA public TO {}").format(
                        sql.Identifier(role)
                    )
                )
            url = admin.set(
                drivername="postgresql+psycopg",
                username=role,
                password=passwords[environment],
                database=database,
            )
            with psycopg.connect(connect_url(url), connect_timeout=3) as runtime:
                observed = runtime.execute("SELECT current_database(), current_user").fetchone()
                if observed != (database, role):
                    raise RuntimeError("Database identity verification failed.")
            urls[environment] = url.render_as_string(hide_password=False)
    env_file = ROOT / ".env"
    if not env_file.exists():
        with env_file.open("x", encoding="utf-8") as output:
            output.write(
                "APP_ENV=development\nAPP_NAME=Road Rules API\n"
                f"DATABASE_URL={urls['dev']}\nTEST_DATABASE_URL={urls['test']}\n"
                "CORS_ALLOWED_ORIGINS=http://localhost:3000\n"
                "ALLOWED_HOSTS=localhost,127.0.0.1\n"
            )
        env_file.chmod(0o600)
    print("Dedicated UTF-8 databases and non-superuser roles verified. Existing .env preserved.")


if __name__ == "__main__":
    try:
        setup()
    except Exception as error:
        # Never print connection strings, SQL containing passwords, or raw driver exceptions.
        print(
            f"Database setup failed ({type(error).__name__}); inspect local configuration safely."
        )
        sys.exit(1)
