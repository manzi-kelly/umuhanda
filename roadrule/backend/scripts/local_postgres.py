"""Manage only this backend's optional development cluster; never remove its data."""

import argparse
import json
import os
import secrets
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / ".local"
DATA = LOCAL / "pgdata"
BIN = Path(os.environ.get("POSTGRES_BIN", "C:/Program Files/PostgreSQL/18/bin"))


def run(*arguments: str) -> None:
    # On Windows, a detached server may inherit pipe handles and prevent communicate()
    # from seeing EOF even after pg_ctl exits. A file avoids that startup deadlock.
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as output:
        result = subprocess.run(
            arguments,
            check=False,
            stdout=output,
            stderr=subprocess.STDOUT,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        output.seek(0)
        print(output.read().strip())
    if result.returncode:
        raise RuntimeError("PostgreSQL utility failed; no existing data was removed.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["start", "stop", "status"])
    action = parser.parse_args().action
    LOCAL.mkdir(exist_ok=True)
    if LOCAL.is_symlink() or DATA.is_symlink() or DATA.resolve().parent != LOCAL.resolve():
        raise RuntimeError("Refusing an unexpected cluster directory.")
    admin_file = LOCAL / "admin.json"
    if action == "start" and not (DATA / "PG_VERSION").exists():
        if DATA.exists() and any(DATA.iterdir()):
            raise RuntimeError("Refusing to initialize a nonempty unrecognized directory.")
        if not admin_file.exists():
            admin_file.write_text(
                json.dumps({"password": secrets.token_urlsafe(32)}), encoding="utf-8"
            )
            admin_file.chmod(0o600)
        password_file = LOCAL / "init-password"
        try:
            password_file.write_text(
                json.loads(admin_file.read_text())["password"], encoding="utf-8"
            )
            password_file.chmod(0o600)
            run(
                str(BIN / "initdb.exe"),
                "-D",
                str(DATA),
                "-U",
                "roadrules_local_admin",
                "--encoding=UTF8",
                "--locale=C",
                "--auth=scram-sha-256",
                "--pwfile",
                str(password_file),
            )
        finally:
            password_file.unlink(missing_ok=True)
        with (DATA / "postgresql.conf").open("a", encoding="utf-8") as config:
            config.write(
                "\n# Road Rules isolated local development only\n"
                "listen_addresses = '127.0.0.1'\nport = 55432\n"
                "max_connections = 30\nshared_buffers = '32MB'\n"
                "log_statement = 'none'\nlog_min_error_statement = 'panic'\n"
            )
    if not (DATA / "PG_VERSION").exists() or not admin_file.exists():
        raise RuntimeError("No recognized project cluster exists. Run start first.")
    if action == "start":
        status = subprocess.run(
            [str(BIN / "pg_ctl.exe"), "-D", str(DATA), "status"], capture_output=True, check=False
        )
        if status.returncode == 0:
            print("Project PostgreSQL cluster is already running.")
            return
        run(
            str(BIN / "pg_ctl.exe"),
            "-D",
            str(DATA),
            "-l",
            str(LOCAL / "postgres.log"),
            "-w",
            "start",
        )
    elif action == "stop":
        run(str(BIN / "pg_ctl.exe"), "-D", str(DATA), "-m", "fast", "-w", "stop")
    else:
        run(str(BIN / "pg_ctl.exe"), "-D", str(DATA), "status")


if __name__ == "__main__":
    main()
