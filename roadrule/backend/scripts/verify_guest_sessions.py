"""Live guest-cookie HTTP verification, only against the isolated test database."""

import io
import json
import logging
import socket
import threading
import time
from pathlib import Path
from uuid import UUID

import httpx
import uvicorn
from sqlalchemy import delete, text

from app.core.config import Settings
from app.core.session_security import COOKIE_PATH
from app.db.session import Database
from app.main import create_app
from app.models import Student, StudentActivityEvent


def main() -> None:
    settings = Settings(app_env="testing")
    audit = Database(settings)
    with audit.engine.connect() as connection:
        assert connection.execute(text("SELECT current_database(), current_user")).one() == (
            "roadrules_test",
            "roadrules_test_app",
        )
    app = create_app(settings)
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host="127.0.0.1",
            port=port,
            log_level="warning",
            access_log=False,
            proxy_headers=False,
        )
    )
    worker = threading.Thread(target=lambda: server.run(sockets=[listener]), daemon=True)
    student_id = None
    log_buffer = io.StringIO()
    observer = logging.StreamHandler(log_buffer)
    watched = [
        logging.getLogger(name) for name in ("uvicorn.error", "uvicorn.access", "httpx", "app")
    ]
    for logger in watched:
        logger.addHandler(observer)
    worker.start()
    try:
        deadline = time.monotonic() + 15
        while not server.started and worker.is_alive() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert server.started
        path = "/api/v1/students/sessions"
        headers = {"Origin": "http://localhost:3000", "X-CSRF-Protection": "1"}
        with httpx.Client(
            base_url=f"http://127.0.0.1:{port}", timeout=10, trust_env=False
        ) as client:
            assert client.get("/api/v1/health").status_code == 200
            assert client.get("/api/v1/health/ready").status_code == 200
            assert client.get(path + "/me").status_code == 401
            assert client.post(path, json={}).status_code == 403
            created = client.post(
                path,
                headers=headers,
                json={"fullName": "Guest Verification", "phoneNumber": "0779876543"},
            )
            assert created.status_code == 201
            body = created.json()
            student_id = UUID(body["studentId"])
            token = client.cookies.get(settings.guest_cookie_name)
            assert token and token not in created.text and "+250779876543" not in created.text
            cookie = created.headers["set-cookie"]
            assert "HttpOnly" in cookie and "Path=/api/v1" in cookie and "SameSite=lax" in cookie
            assert client.get(path + "/me", headers=headers).json() == body
            assert body["accessGranted"] is False
            assert client.post(path + "/revoke", headers=headers).status_code == 204
            assert client.post(path + "/revoke", headers=headers).status_code == 204
            client.cookies.clear()
            client.cookies.set(settings.guest_cookie_name, token, path=COOKIE_PATH)
            assert client.get(path + "/me", headers=headers).status_code == 401
        postgres_log = (Path(__file__).resolve().parents[1] / ".local/postgres.log").read_text(
            encoding="utf-8", errors="replace"
        )
        assert token not in log_buffer.getvalue() and token not in postgres_log
        assert "+250779876543" not in log_buffer.getvalue()
        evidence = {
            "health": 200,
            "ready": 200,
            "missing_session": 401,
            "csrf_missing": 403,
            "create": 201,
            "authenticated_me": 200,
            "revoke": 204,
            "repeat_revoke": 204,
            "replay_after_revoke": 401,
            "http_only": True,
            "same_site": "lax",
            "cookie_path": COOKIE_PATH,
            "raw_token_in_json": False,
            "raw_token_in_logs": False,
            "access_granted": False,
        }
    finally:
        server.should_exit = True
        worker.join(timeout=15)
        listener.close()
        for logger in watched:
            logger.removeHandler(observer)
        try:
            if student_id is not None:
                with audit.engine.begin() as connection:
                    connection.execute(
                        delete(StudentActivityEvent).where(
                            StudentActivityEvent.student_id == student_id
                        )
                    )
                    connection.execute(delete(Student).where(Student.id == student_id))
        finally:
            audit.dispose()
        if worker.is_alive():
            raise RuntimeError("Guest verification server did not stop cleanly.")
    evidence["clean_shutdown"] = True
    evidence["synthetic_test_data_removed"] = True
    target = Path(__file__).resolve().parents[2] / "docs/evidence/phase03b/live-sessions.json"
    target.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(
        "Live guest-session checks passed; sanitized evidence saved; synthetic test data removed."
    )


if __name__ == "__main__":
    main()
