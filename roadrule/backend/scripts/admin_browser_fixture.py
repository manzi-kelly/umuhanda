"""Isolated synthetic browser fixture. Cannot target the development database."""

import argparse
import hashlib
import json
import os
import secrets
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from uuid import UUID, uuid4

import uvicorn
from alembic.config import Config
from sqlalchemy import delete, func, select, text

from alembic import command
from app.core.config import Settings
from app.db.session import Database
from app.main import create_app
from app.models import AdminAuditEvent, AdminSession, AdminUser, Student
from app.models.pdf_import import PdfDocument, PdfImportJob
from app.services.admin_auth import AdminAuthService
from app.services.exam_access import AccessError, settle_mock
from app.services.pdf.jobs import process_job, reset_drafts
from app.services.pdf.storage import PdfStorage
from tests.pdf_fixtures import sample_pdf

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / (
    ".local/phase04l-browser" if os.getenv("PHASE04L_ISOLATED_BROWSER") == "1" else ".local"
)
FILE = FIXTURE_ROOT / "admin-browser.json"
PDF_FILE = FIXTURE_ROOT / "admin-browser-synthetic.pdf"
CLOCK_FILE = FIXTURE_ROOT / "exam-browser-clock.txt"
STORAGE = FIXTURE_ROOT / "admin-browser-pdf-storage"


def settings():
    return Settings(
        app_env="testing",
        cors_allowed_origins=["http://127.0.0.1:3100", "http://localhost:3000"],
        admin_login_limit=200,
        pdf_upload_limit=30,
        pdf_storage_root=STORAGE,
        mock_payments_enabled=os.environ.get("PHASE04D_BROWSER_ACCESS") == "1",
        exam_selection_policy="UNSTRATIFIED",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["serve", "cleanup", "expire", "drain", "settle"])
    parser.add_argument("payment_id", type=UUID, nargs="?")
    args = parser.parse_args()
    action = args.action
    config = settings()
    database = Database(config)
    try:
        with database.engine.connect() as connection:
            assert connection.execute(text("SELECT current_database(), current_user")).one() == (
                "roadrules_test",
                "roadrules_test_app",
            )
        if action == "serve":
            # Config loaded through APP_ENV=testing for Alembic too; never use a dev URL.
            os.environ["APP_ENV"] = "testing"
            command.upgrade(Config(str(ROOT / "alembic.ini")), "head")
            FIXTURE_ROOT.mkdir(exist_ok=True)
            assert not FILE.exists() and not STORAGE.exists() and not PDF_FILE.exists()
            with database.session_factory() as session:
                assert session.scalar(select(func.count()).select_from(PdfDocument)) == 0
                assert session.scalar(select(func.count()).select_from(Student)) == 0
                assert session.scalar(select(func.count()).select_from(AdminUser)) == 0
                assert session.scalar(select(func.count()).select_from(AdminAuditEvent)) == 0
                assert session.scalar(text("SELECT count(*) FROM exam_operational_events")) == 0
                session.rollback()
                password = secrets.token_urlsafe(32)
                admin_id = AdminAuthService(session, config).bootstrap(
                    "Dashboard Reviewer", "qa.admin@example.com", password
                )
            student_id = uuid4()
            with database.session_factory.begin() as session:
                session.add(
                    Student(
                        id=student_id,
                        full_name="Dashboard Verification",
                        phone_number="+250770000000",
                    )
                )
            FILE.write_text(
                json.dumps(
                    {
                        "adminId": str(admin_id),
                        "studentId": str(student_id),
                        "email": "qa.admin@example.com",
                        "password": password,
                    }
                ),
                encoding="utf-8",
            )
            FILE.chmod(0o600)
            PDF_FILE.write_bytes(sample_pdf())
            if config.mock_allowed:
                from tests.integration.test_exam_bank import fixture_pdf

                source = fixture_pdf(42, sign_interval=2)
                document_id = uuid4()
                key = f"sources/{document_id.hex}.pdf"
                PdfStorage(config).path(key).write_bytes(source)
                with database.session_factory.begin() as session:
                    pdf = PdfDocument(
                        id=document_id,
                        original_filename="synthetic-ready-bank.pdf",
                        storage_key=key,
                        sha256_hash=hashlib.sha256(source).hexdigest(),
                        file_size_bytes=len(source),
                        page_count=7,
                        uploaded_by_admin_id=admin_id,
                    )
                    session.add(pdf)
                    session.flush()
                    job = PdfImportJob(document_id=document_id, total_pages=7)
                    session.add(job)
                    session.flush()
                    job_id = job.id
                assert process_job(config, job_id), "Synthetic bank setup failed."
            if config.mock_allowed:
                from app.api.v1 import exam_execution
                from app.services.exam_access import now

                def browser_clock(session):
                    if CLOCK_FILE.exists():
                        return datetime.fromisoformat(CLOCK_FILE.read_text(encoding="utf-8"))
                    return now(session)

                exam_execution.now = browser_clock
            uvicorn.run(
                create_app(config),
                host="127.0.0.1",
                port=8310,
                log_level="warning",
                access_log=False,
                proxy_headers=False,
            )
        elif action == "settle":
            assert args.payment_id and FILE.exists() and config.mock_allowed
            with database.session_factory() as session:
                result = settle_mock(session, config, args.payment_id, "SUCCESSFUL")
                assert not isinstance(result, AccessError)
        elif action == "drain":
            assert FILE.exists(), "Browser fixture is not active."
            subprocess.run(
                [sys.executable, str(ROOT / "scripts/pdf_worker.py"), "--once"],
                env={
                    **os.environ,
                    "APP_ENV": "testing",
                    "PDF_STORAGE_ROOT": str(STORAGE),
                    # The synthetic fixture has no difficulty metadata; keep the
                    # worker aligned with the fixture server's declared policy.
                    "EXAM_SELECTION_POLICY": config.exam_selection_policy,
                },
                check=True,
                timeout=60,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        elif FILE.exists():
            data = json.loads(FILE.read_text(encoding="utf-8"))
            identifier = UUID(data["adminId"])
            if action == "cleanup":
                with database.session_factory.begin() as session:
                    documents = session.scalars(select(PdfDocument)).all()
                    assert all(doc.uploaded_by_admin_id == identifier for doc in documents)
                    if not config.mock_allowed:
                        assert session.scalar(text("SELECT count(*) FROM exam_attempts")) == 0
                    session.execute(
                        text(
                            "TRUNCATE refund_requests, exam_results, exam_grading_failures, "
                            "exam_responses, exam_timing, exam_entitlements, "
                            "payment_transactions, "
                            "promo_codes, promo_attempts, exam_operational_events, "
                            "exam_attempt_items, exam_attempts, exam_bank_questions, "
                            "exam_bank_revisions"
                        )
                    )

                    for document in documents:
                        jobs = session.scalars(
                            select(PdfImportJob).where(PdfImportJob.document_id == document.id)
                        ).all()
                        for job in jobs:
                            reset_drafts(session, job.id)
                            session.delete(job)
                        session.flush()
                        session.delete(document)
            with database.engine.begin() as connection:
                identifiers = set(connection.scalars(select(AdminUser.id)))
                assert identifiers <= {identifier}, (
                    "Refusing to touch unrelated test administrators."
                )
                if action == "expire":
                    connection.execute(
                        text(
                            "UPDATE admin_sessions SET "
                            "created_at=clock_timestamp()-interval '10 hours', "
                            "last_activity_at=clock_timestamp()-interval '2 minutes', "
                            "expires_at=clock_timestamp()-interval '1 minute' "
                            "WHERE admin_id=:identifier AND revoked_at IS NULL"
                        ),
                        {"identifier": identifier},
                    )
                else:
                    connection.execute(delete(AdminAuditEvent))
                    connection.execute(
                        delete(AdminSession).where(AdminSession.admin_id == identifier)
                    )
                    connection.execute(delete(AdminUser).where(AdminUser.id == identifier))
                    if config.mock_allowed:
                        connection.execute(
                            text(
                                "TRUNCATE refund_requests, exam_results, exam_grading_failures, "
                                "exam_responses, exam_timing, exam_entitlements, "
                                "payment_transactions, promo_attempts, "
                                "exam_attempt_items, exam_attempts, student_activity_events, "
                                "guest_sessions, students"
                            )
                        )
                    else:
                        connection.execute(
                            delete(Student).where(Student.id == UUID(data["studentId"]))
                        )
            if action == "cleanup":
                FILE.unlink()
                PDF_FILE.unlink(missing_ok=True)
                CLOCK_FILE.unlink(missing_ok=True)
                if STORAGE.exists():
                    resolved = STORAGE.resolve(strict=True)
                    assert (
                        resolved == ROOT.resolve() / FIXTURE_ROOT.relative_to(ROOT) / STORAGE.name
                    )
                    assert not STORAGE.is_symlink() and not STORAGE.is_junction()
                    shutil.rmtree(resolved)
                print("Synthetic admin browser fixture removed; no credentials printed.")
    finally:
        database.dispose()


if __name__ == "__main__":
    main()
