"""Check actual local credentials against source and evidence without printing them."""

import hashlib
import json
import os
import re
from datetime import timedelta
from pathlib import Path

from sqlalchemy import func, select

from app.core.config import Settings
from app.db.session import Database
from app.models import AdminSession, GuestSession

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT.parent / "docs/evidence/phase04a"


def main() -> None:
    credentials = [
        Settings(app_env=mode).connection_url.password for mode in ("development", "testing")
    ]
    admin_file = ROOT / ".local/admin.json"
    if admin_file.exists():
        credentials.append(json.loads(admin_file.read_text())["password"])
    sources = []
    for directory, children, files in os.walk(ROOT.parent):
        children[:] = [
            name
            for name in children
            if name
            not in {
                ".venv",
                ".local",
                "__pycache__",
                ".pytest_cache",
                ".ruff_cache",
                "node_modules",
                ".next",
                ".git",
                "test-results",
            }
            and not name.endswith(".egg-info")
        ]
        sources.extend(
            Path(directory) / name
            for name in files
            if name != ".env"
            and Path(name).suffix
            in {
                ".py",
                ".toml",
                ".ini",
                ".mako",
                ".txt",
                ".md",
                ".example",
                ".ts",
                ".tsx",
                ".mjs",
                ".json",
                ".css",
            }
        )
    sources.extend(
        [
            ROOT.parent / "docs/phase03a-backend-foundation.md",
            ROOT.parent / "docs/phase03b-student-sessions.md",
        ]
    )
    logs = list(EVIDENCE.glob("*.log")) + [ROOT / ".local/postgres.log"]
    matches = []
    for path in sources + logs:
        if path.exists() and any(
            secret and secret in path.read_text(encoding="utf-8-sig", errors="replace")
            for secret in credentials
        ):
            matches.append(str(path.relative_to(ROOT.parent)))
    result = {
        "source_files_checked": len(sources),
        "log_files_checked": len(logs),
        "plaintext_credential_matches": matches,
        "excluded_secret_locations": ["backend/.env", "backend/.local/"],
    }
    postgres_log = ROOT / ".local/postgres.log"
    candidates = set(
        re.findall(
            r"(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{43}(?![A-Za-z0-9_-])",
            postgres_log.read_text(encoding="utf-8", errors="replace"),
        )
    )
    verifiers = [hashlib.sha256(value.encode("ascii")).hexdigest() for value in candidates]
    active_matches = 0
    admin_matches = 0
    admin_verifiers = [
        hashlib.sha256(("admin:" + value).encode("ascii")).hexdigest() for value in candidates
    ]
    for mode in ("development", "testing"):
        settings = Settings(app_env=mode)
        database = Database(settings)
        try:
            with database.session_factory() as session:
                if verifiers:
                    active_matches += session.scalar(
                        select(func.count())
                        .select_from(GuestSession)
                        .where(
                            GuestSession.token_hash.in_(verifiers),
                            GuestSession.revoked_at.is_(None),
                            GuestSession.expires_at > func.clock_timestamp(),
                            GuestSession.last_activity_at
                            > func.clock_timestamp()
                            - timedelta(seconds=settings.guest_session_idle_seconds),
                        )
                    )
                if admin_verifiers:
                    admin_matches += session.scalar(
                        select(func.count())
                        .select_from(AdminSession)
                        .where(
                            AdminSession.token_hash.in_(admin_verifiers),
                            AdminSession.revoked_at.is_(None),
                            AdminSession.expires_at > func.clock_timestamp(),
                            AdminSession.last_activity_at
                            > func.clock_timestamp()
                            - timedelta(seconds=settings.admin_session_idle_seconds),
                        )
                    )
        finally:
            database.dispose()
    result["historical_credential_shaped_log_values"] = len(candidates)
    result["active_guest_credentials_matching_log_values"] = active_matches
    result["active_admin_credentials_matching_log_values"] = admin_matches
    (EVIDENCE / "security-audit.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    if matches or active_matches or admin_matches:
        raise RuntimeError(
            "A credential was found outside intended secret storage; inspect audit paths."
        )
    print("No local database credentials found in backend source, documentation or audited logs.")


if __name__ == "__main__":
    main()
