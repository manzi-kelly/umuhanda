"""Read-only PostgreSQL connectivity diagnostic for deployment shells.

Prints routing and TLS metadata plus error class/SQLSTATE. Passwords and full
connection strings are never printed. Exit code 0 means the connection and a
real SELECT succeeded; 1 means it failed.
"""

from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import quote

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

# Allow `python scripts/diagnose_database.py` from the backend directory.
# Python puts the script directory on sys.path, not the backend root.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import Settings  # noqa: E402
from app.core.db_diagnostics import database_failure_context  # noqa: E402
from app.db.session import Database  # noqa: E402

ACTIONS = {
    "08001": "Confirm the host/port, private networking and that PostgreSQL is running.",
    "08006": (
        "Check TLS (sslmode/sslrootcert), the certificate SAN/hostname match, "
        "and network reachability."
    ),
    "28000": "Check pg_hba.conf, role membership and connection database grants.",
    "28P01": "The role password is wrong. Rotate it deliberately and update DATABASE_URL.",
    "3D000": "The database does not exist. Create it or correct DATABASE_URL.",
    "42501": "Grant only the required schema/table/sequence privileges to the runtime role.",
    "53300": "Reduce pool sizes or raise max_connections; check for leaked connections.",
    "57014": "Inspect the slow query or raise DB_STATEMENT_TIMEOUT_MS deliberately.",
    "57P03": "PostgreSQL is starting or shutting down; retry once it is ready.",
}


def _sanitize(value: str, secrets: list[str]) -> str:
    for secret in secrets:
        if secret:
            value = value.replace(secret, "***")
    return " ".join(value.split())[:500]


def main() -> int:
    try:
        settings = Settings()
        url = settings.connection_url
    except Exception as error:
        print("connected=false")
        print(f"config_error={type(error).__name__}: {' '.join(str(error).split())[:500]}")
        print(
            "action=Set APP_ENV and a dedicated-role DATABASE_URL with "
            "sslmode=verify-full; see docs/railway-production-recovery.md."
        )
        return 1

    sslrootcert = url.query.get("sslrootcert")
    if not sslrootcert:
        root_state = "not-configured"
    elif Path(sslrootcert).is_file():
        root_state = "present"
    else:
        root_state = "missing"

    print(f"app_env={settings.app_env}")
    print(f"target={url.host}:{url.port or 5432}/{url.database}")
    print(f"sslmode={url.query.get('sslmode', 'prefer')}")
    print(f"sslrootcert={sslrootcert or 'not-configured'} ({root_state})")

    password = url.password or ""
    secrets: list[str] = []
    if password:
        secrets.extend([password, quote(password, safe="")])
    if settings.database_url is not None:
        secrets.append(settings.database_url.get_secret_value())
    database = Database(settings)
    try:
        with database.engine.connect() as connection:
            row = connection.execute(
                text(
                    "SELECT current_database(), current_user, "
                    "coalesce((SELECT ssl FROM pg_stat_ssl WHERE pid = pg_backend_pid()), false)"
                )
            ).one()
        print(f"connected=true database={row[0]} role={row[1]} tls={row[2]}")
        return 0
    except SQLAlchemyError as error:
        context = database_failure_context(settings, error)
        print("connected=false")
        print(f"error={context['error']}")
        print(f"driver_error={context['driver_error']}")
        print(f"sqlstate={context['sqlstate']}")
        print(f"category={context['category']}")
        print(f"connection_invalidated={context['connection_invalidated']}")
        print(f"detail={_sanitize(str(getattr(error, 'orig', error)), secrets)}")
        action = ACTIONS.get(context["sqlstate"], "Inspect the Railway service logs and variables.")
        print(f"action={action}")
        return 1
    finally:
        database.dispose()


if __name__ == "__main__":
    sys.exit(main())
