"""One-time, local, interactive first-admin bootstrap. Never accepts password arguments."""

import argparse
import getpass
import sys

from app.core.admin_security import BootstrapRefused
from app.core.config import Settings
from app.db.session import Database
from app.services.admin_auth import AdminAuthService


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm-first-admin", action="store_true", required=True)
    parser.parse_args()
    if not sys.stdin.isatty():
        print("An interactive local terminal is required. Password piping is not supported.")
        return 1
    name = input("Full name: ")
    email = input("Email: ")
    password = getpass.getpass("Passphrase (15–256 characters): ")
    confirmation = getpass.getpass("Confirm passphrase: ")
    if password != confirmation:
        print("Passphrases did not match; no administrator created.")
        return 1
    database = None
    try:
        settings = Settings()
        database = Database(settings)
        with database.session_factory() as session:
            AdminAuthService(session, settings).bootstrap(name, email, password)
    except BootstrapRefused:
        print("First-administrator bootstrap is already consumed; no account created.")
        return 1
    except Exception:
        print("Administrator creation failed. Check inputs and database configuration safely.")
        return 1
    finally:
        if database is not None:
            database.dispose()
    print("First administrator created. No credentials were printed or stored in plaintext.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
