import os
import secrets
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, inspect, select, text
from sqlalchemy.exc import IntegrityError

from alembic import command
from app.core.config import Settings
from app.db.session import Database
from app.main import create_app
from app.models.pdf_import import PdfDocument, PdfImportJob, QuestionDraft
from app.services.admin_auth import AdminAuthService
from app.services.pdf.jobs import process_job, try_lock, unlock
from app.services.pdf.storage import PdfStorage
from tests.pdf_fixtures import bulk_pdf, sample_pdf

pytestmark = pytest.mark.integration
HEADERS = {
    "Origin": "http://localhost:3000",
    "X-CSRF-Protection": "1",
    "Content-Type": "application/pdf",
}
ROOT = "/api/v1/admin"
TABLES = {
    "alembic_version",
    "students",
    "guest_sessions",
    "student_activity_events",
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


@pytest.fixture
def environment(integration_settings, migration_config, tmp_path):
    command.upgrade(migration_config, "head")
    settings = Settings(
        _env_file=None,
        app_env="testing",
        test_database_url=integration_settings.test_database_url,
        cors_allowed_origins=["http://localhost:3000"],
        pdf_storage_root=tmp_path / "private",
        admin_login_limit=100,
    )
    database = Database(settings)

    def clear():
        with database.engine.begin() as connection:
            assert tuple(
                connection.execute(text("SELECT current_database(),current_user")).one()
            ) == ("roadrules_test", "roadrules_test_app")
            assert set(inspect(connection).get_table_names()) == TABLES
            connection.execute(text("TRUNCATE " + ", ".join(sorted(TABLES - {"alembic_version"}))))

    clear()
    password = secrets.token_urlsafe(24)
    with database.session_factory() as session:
        AdminAuthService(session, settings).bootstrap(
            "PDF Test Operator", "pdf-test@example.com", password
        )
    try:
        with TestClient(
            create_app(settings), base_url="http://localhost", raise_server_exceptions=False
        ) as client:
            response = client.post(
                ROOT + "/auth/login",
                headers={**HEADERS, "Content-Type": "application/json"},
                json={"email": "pdf-test@example.com", "password": password},
            )
            assert response.status_code == 200
            yield client, database, settings
    finally:
        clear()
        database.dispose()


def upload(client, data=None, filename="synthetic-test.pdf", headers=None):
    return client.post(
        ROOT + "/pdf-documents",
        headers={**(headers or HEADERS), "X-PDF-Filename": quote(filename, safe="")},
        content=sample_pdf() if data is None else data,
    )


def job_id(client, identifier):
    result = client.get(ROOT + f"/pdf-documents/{identifier}/jobs")
    assert result.status_code == 200
    return UUID(result.json()[0]["id"])


def test_upload_persistence_extraction_images_answers_preview_and_pagination(environment):
    client, database, settings = environment
    source = sample_pdf()
    response = upload(client, source)
    assert response.status_code == 202, response.text
    document = response.json()["document"]
    identifier = document["id"]
    assert document["page_count"] == 3 and document["import_status"] == "QUEUED"
    assert "storage_key" not in document and response.json()["duplicate"] is False
    job = job_id(client, identifier)
    assert process_job(settings, job)
    assert not process_job(settings, job)  # Completed jobs do not run twice.
    progress = client.get(ROOT + f"/pdf-import-jobs/{job}").json()
    assert progress["status"] == "COMPLETED" and progress["processed_pages"] == 3
    assert progress["extracted_question_count"] == progress["review_required_count"] == 2
    result = client.get(
        ROOT + "/question-drafts", params={"document_id": identifier, "page_size": 1}
    ).json()
    assert result["total"] == 2 and len(result["items"]) == 1
    draft = result["items"][0]
    assert draft["question_text"] == "Iki ni ikibazo cy'igerageza?\nUyu ni umurongo wa kabiri."
    assert [o["option_label"] for o in draft["options"]] == ["A", "B"]
    assert draft["answer"]["selected_option_id"] == draft["options"][0]["id"]
    assert draft["answer"]["raw_answer_text"] == "1. A"
    assert draft["answer"]["verification_status"] == "EXTRACTED_UNVERIFIED"
    assert draft["answer"]["evidence_page_number"] == 3
    assert {a["asset_type"] for a in draft["assets"]} == {"RASTER_REGION", "VECTOR_REGION"}
    assert len(draft["assets"]) == 2  # The unrelated header image is excluded.
    for asset in draft["assets"]:
        image = client.get(ROOT + f"/question-draft-assets/{asset['id']}")
        assert image.status_code == 200 and image.content.startswith(b"\x89PNG")
        assert image.headers["cache-control"] == "no-store"
    page = client.get(ROOT + f"/pdf-documents/{identifier}/pages/1")
    assert page.status_code == 200 and page.content.startswith(b"\x89PNG")
    assert client.get(ROOT + f"/pdf-documents/{identifier}/pages/99").status_code == 404
    assert client.get(ROOT + f"/question-drafts/{draft['id']}").json() == draft
    second = client.get(
        ROOT + "/question-drafts", params={"document_id": identifier, "page_size": 1, "page": 2}
    ).json()["items"][0]
    assert second["options"][1]["source_page_number"] == 2
    assert client.get(ROOT + "/question-drafts?page_size=1000").status_code == 422
    with database.session_factory() as session:
        row = session.get(PdfDocument, UUID(identifier))
        assert PdfStorage(settings).path(row.storage_key).read_bytes() == source
        assert session.scalar(select(func.count()).select_from(QuestionDraft)) == 2


def test_duplicate_upload_and_operation_retry_do_not_duplicate_records(environment):
    client, database, settings = environment
    data = sample_pdf()
    first = upload(client, data).json()["document"]
    second = upload(client, data, filename="another-name.pdf")
    assert second.status_code == 202 and second.json()["duplicate"]
    assert second.json()["document"]["id"] == first["id"]
    assert client.get(ROOT + "/pdf-documents").json()["total"] == 1
    job = job_id(client, first["id"])
    assert process_job(settings, job)
    with database.session_factory.begin() as session:
        row = session.get(PdfImportJob, job)
        row.status = "FAILED"
    response = client.post(ROOT + f"/pdf-import-jobs/{job}/retry", headers=HEADERS)
    assert response.status_code == 202, response.text
    assert process_job(settings, job)
    assert client.get(ROOT + "/question-drafts").json()["total"] == 2


def test_worker_discovers_uploads_and_resumes_after_restart(environment):
    client, database, settings = environment
    first = upload(client, filename="first.pdf").json()["document"]
    second = upload(client, sample_pdf() + b"\n", filename="second.pdf").json()["document"]
    interrupted = job_id(client, first["id"])
    missing_job = job_id(client, second["id"])
    with database.session_factory.begin() as session:
        session.get(PdfImportJob, interrupted).status = "PROCESSING"
        session.delete(session.get(PdfImportJob, missing_job))
    orphan = PdfStorage(settings).path("sources/" + "f" * 32 + ".pdf")
    orphan.write_bytes(sample_pdf())
    subprocess.run(
        [sys.executable, "scripts/pdf_worker.py", "--once"],
        cwd=Path(__file__).resolve().parents[2],
        env={
            **os.environ,
            "APP_ENV": "testing",
            "TEST_DATABASE_URL": settings.test_database_url.get_secret_value(),
            "PDF_STORAGE_ROOT": str(settings.pdf_storage_root),
        },
        timeout=90,
        check=True,
    )
    assert client.get(ROOT + "/pdf-documents").json()["total"] == 2
    for document in (first, second):
        identifier = document["id"]
        job = client.get(ROOT + f"/pdf-import-jobs/{job_id(client, identifier)}").json()
        assert job["status"] == "COMPLETED"
        assert job["extracted_question_count"] == 2


@pytest.mark.parametrize("damage", [None, b"corrupt"])
def test_matching_admin_upload_restores_source(environment, damage):
    client, database, settings = environment
    data = sample_pdf()
    document = upload(client, data).json()["document"]
    identifier = UUID(document["id"])
    job = job_id(client, identifier)
    with database.session_factory() as session:
        row = session.get(PdfDocument, identifier)
        path = PdfStorage(settings).path(row.storage_key)
    if damage is None:
        path.unlink()
    else:
        path.write_bytes(damage)
    assert not process_job(settings, job)
    code = "SOURCE_MISSING" if damage is None else "SOURCE_INTEGRITY_FAILURE"
    preview = client.get(ROOT + f"/pdf-documents/{identifier}/pages/1")
    assert preview.json()["error"]["code"] == code
    failed = client.get(ROOT + f"/pdf-import-jobs/{job}").json()
    assert failed["status"] == "FAILED" and failed["diagnostics"] == [{"code": code}]
    repaired = upload(client, data).json()
    assert repaired["duplicate"] and repaired["document"]["id"] == str(identifier)
    assert repaired["document"]["import_status"] == "QUEUED"
    assert process_job(settings, job)
    assert path.read_bytes() == data


@pytest.mark.parametrize(
    "data,filename,kind,code",
    [
        (b"not a PDF", "bad.pdf", "application/pdf", "INVALID_PDF"),
        (b"%PDF-broken", "bad.pdf", "application/pdf", "INVALID_PDF"),
        (b"", "empty.pdf", "application/pdf", "EMPTY_PDF"),
        (b"x", "script.exe", "application/pdf", "INVALID_FILENAME"),
        (b"x", "../bad.pdf", "application/pdf", "INVALID_FILENAME"),
        (b"x", "bad.pdf", "text/plain", "PDF_CONTENT_TYPE_REQUIRED"),
    ],
)
def test_invalid_uploads_are_rejected_without_source_rows(environment, data, filename, kind, code):
    client, database, _ = environment
    result = upload(client, data, filename, {**HEADERS, "Content-Type": kind})
    assert result.status_code in {415, 422} and result.json()["error"]["code"] == code
    with database.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(PdfDocument)) == 0


def test_limits_and_durable_attempt_budget(environment):
    client, _, settings = environment
    small = settings.model_copy(update={"pdf_max_file_bytes": 1024, "pdf_upload_limit": 2})
    with TestClient(create_app(small), base_url="http://localhost") as other:
        other.cookies.update(client.cookies)
        assert upload(other, b"x" * 1025).status_code == 413
        assert upload(other, b"x").status_code == 422
    with TestClient(create_app(small), base_url="http://localhost") as another:
        another.cookies.update(client.cookies)
        assert upload(another, b"x").status_code == 429


def test_csrf_guest_isolation_and_all_private_endpoints(environment):
    client, _, settings = environment
    identifier = upload(client).json()["document"]["id"]
    assert upload(client, headers={"Content-Type": "application/pdf"}).status_code == 403
    with TestClient(create_app(settings), base_url="http://localhost") as guest:
        result = guest.post(
            "/api/v1/students/sessions",
            headers={**HEADERS, "Content-Type": "application/json"},
            json={"fullName": "Synthetic Guest", "phoneNumber": "0781234567"},
        )
        assert result.status_code == 201
        for endpoint in [
            "/pdf-documents",
            f"/pdf-documents/{identifier}",
            f"/pdf-documents/{identifier}/jobs",
            f"/pdf-documents/{identifier}/pages/1",
            "/question-drafts",
            f"/question-drafts/{identifier}",
            f"/question-draft-assets/{identifier}",
            f"/pdf-import-jobs/{identifier}",
        ]:
            denied = guest.get(ROOT + endpoint)
            assert denied.status_code == 401 and "original_filename" not in denied.text
        assert upload(guest).status_code == 401
        assert (
            guest.post(ROOT + f"/pdf-import-jobs/{identifier}/retry", headers=HEADERS).status_code
            == 401
        )
        assert guest.get("/api/v1/question-drafts").status_code == 404


@pytest.mark.parametrize("ambiguous", [False, True])
def test_missing_or_ambiguous_answers_stay_unverified(environment, ambiguous):
    client, _, settings = environment
    data = sample_pdf(answers=ambiguous, ambiguous=ambiguous)
    identifier = upload(client, data).json()["document"]["id"]
    assert process_job(settings, job_id(client, identifier))
    draft = client.get(ROOT + "/question-drafts").json()["items"][0]
    assert draft["answer"]["selected_option_id"] is None
    assert draft["answer_status"] == ("NEEDS_REVIEW" if ambiguous else "ANSWER_NOT_FOUND")


def test_worker_failure_stale_recovery_and_lock_exclusion(environment, monkeypatch):
    client, database, settings = environment
    identifier = upload(client).json()["document"]["id"]
    job = job_id(client, identifier)
    with database.engine.connect() as lock:
        assert try_lock(lock, job)
        assert not process_job(settings, job)
        assert (
            client.post(ROOT + f"/pdf-import-jobs/{job}/retry", headers=HEADERS).status_code == 409
        )
        unlock(lock, job)

    def fail(*args, **kwargs):
        raise RuntimeError("private PDF content must not escape")

    with monkeypatch.context() as patch:
        patch.setattr("app.services.pdf.jobs.page_lines", fail)
        assert not process_job(settings, job)
    result = client.get(ROOT + f"/pdf-import-jobs/{job}").json()
    assert result["status"] == "FAILED" and "private" not in str(result)
    assert client.post(ROOT + f"/pdf-import-jobs/{job}/retry", headers=HEADERS).status_code == 202
    assert process_job(settings, job)
    with database.session_factory.begin() as session:
        session.get(
            PdfImportJob, job
        ).status = "PROCESSING"  # A dead worker released its connection.
    assert client.post(ROOT + f"/pdf-import-jobs/{job}/retry", headers=HEADERS).status_code == 202
    assert process_job(settings, job)


def test_upload_transaction_rollback_removes_uncommitted_file(environment, monkeypatch):
    client, database, settings = environment

    def fail(*args, **kwargs):
        raise IntegrityError("synthetic rollback", {}, Exception())

    monkeypatch.setattr("app.services.pdf.uploads.PdfImportJob", fail)
    response = upload(client)
    assert response.status_code == 503
    with database.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(PdfDocument)) == 0
    assert not list((settings.pdf_storage_root / "sources").glob("*"))
    assert not list((settings.pdf_storage_root / "incoming").glob("*"))


def test_bulk_import_persists_400_synthetic_drafts(environment):
    client, database, settings = environment
    response = upload(client, bulk_pdf())
    assert response.status_code == 202
    job = job_id(client, response.json()["document"]["id"])
    assert process_job(settings, job)
    with database.session_factory() as session:
        row = session.get(PdfImportJob, job)
        assert row.total_pages == row.processed_pages == 50
        assert row.extracted_question_count == row.review_required_count == 400
        assert row.status == "COMPLETED_WITH_WARNINGS"
        assert session.scalar(select(func.count()).select_from(QuestionDraft)) == 400
