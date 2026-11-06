"""Bounded upload ingestion and isolated, timeout-limited PDF inspection."""

import hashlib
import json
import subprocess
import sys
import uuid
from datetime import timedelta
from pathlib import Path
from threading import BoundedSemaphore
from urllib.parse import unquote

from sqlalchemy import func, select, text

from app.models import AdminAuditEvent
from app.models.pdf_import import PdfDocument, PdfImportJob
from app.services.pdf.storage import PdfError, PdfStorage

PROBE_SLOTS = BoundedSemaphore(2)


def inspect_source(path, settings, page=None, output=None):
    arguments = [
        sys.executable,
        "-m",
        "app.services.pdf.probe",
        str(path),
        str(settings.pdf_max_pages),
        str(settings.pdf_max_page_points),
        str(settings.pdf_worker_memory_mb),
    ]
    if page is not None:
        arguments += [str(page), str(output)]
    if not PROBE_SLOTS.acquire(blocking=False):
        raise PdfError("PDF_PARSER_BUSY", 503)
    try:
        result = subprocess.run(
            arguments,
            cwd=Path(__file__).resolve().parents[3],
            capture_output=True,
            timeout=15,
            check=True,
        )
        value = json.loads(result.stdout)
    except Exception:
        raise PdfError("PDF_VALIDATION_TIMEOUT_OR_FAILURE") from None
    finally:
        PROBE_SLOTS.release()
    if "error" in value:
        raise PdfError(value["error"])
    return value


def upload_budget(session, settings, admin_id):
    with session.begin():
        if not session.scalar(text("SELECT pg_try_advisory_xact_lock(138112, 7)")):
            raise PdfError("UPLOAD_RATE_LIMIT", 429)
        now = session.scalar(select(func.clock_timestamp()))
        count = session.scalar(
            select(func.count())
            .select_from(AdminAuditEvent)
            .where(
                AdminAuditEvent.event_type == "PDF_UPLOAD_ATTEMPT",
                AdminAuditEvent.created_at
                >= now - timedelta(seconds=settings.pdf_upload_window_seconds),
            )
        )
        if count >= settings.pdf_upload_limit:
            raise PdfError("UPLOAD_RATE_LIMIT", 429)
        session.add(
            AdminAuditEvent(
                actor_admin_id=admin_id,
                event_type="PDF_UPLOAD_ATTEMPT",
                created_at=now,
                sanitized_metadata={"result": "success"},
            )
        )


async def accept_upload(request, session, admin, filename):
    settings = request.app.state.settings
    upload_budget(session, settings, admin.id)
    if request.headers.get("content-type", "").split(";")[0] != "application/pdf":
        raise PdfError("PDF_CONTENT_TYPE_REQUIRED", 415)
    try:
        filename = unquote(filename, errors="strict")
    except UnicodeError:
        raise PdfError("INVALID_FILENAME") from None
    if len(filename) > 255:
        raise PdfError("INVALID_FILENAME")
    # Original filename is display metadata only and stays out of access-log URLs.
    if not filename.lower().endswith(".pdf") or any(ord(c) < 32 or c in "/\\" for c in filename):
        raise PdfError("INVALID_FILENAME")
    storage = PdfStorage(settings)
    incoming = storage.root / "incoming" / (uuid.uuid4().hex + ".part")
    size = 0
    digest = hashlib.sha256()
    final = None
    committed = False
    try:
        with incoming.open("xb") as output:
            async for chunk in request.stream():
                size += len(chunk)
                if size > settings.pdf_max_file_bytes:
                    raise PdfError("FILE_SIZE_LIMIT", 413)
                digest.update(chunk)
                output.write(chunk)
        if size == 0:
            raise PdfError("EMPTY_PDF")
        # Isolated native parser; never execute PDF actions or shell commands.
        from starlette.concurrency import run_in_threadpool

        details = await run_in_threadpool(inspect_source, incoming, settings)
        with session.begin():
            # Serialize content deduplication across processes; uniqueness is a second guard.
            session.execute(text("SELECT pg_advisory_xact_lock(138112, 8)"))
            existing = session.scalar(
                select(PdfDocument).where(PdfDocument.sha256_hash == digest.hexdigest())
            )
            if existing:
                try:
                    storage.source(
                        existing.storage_key, existing.sha256_hash, existing.file_size_bytes
                    )
                except PdfError as error:
                    if error.code not in {"SOURCE_MISSING", "SOURCE_INTEGRITY_FAILURE"}:
                        raise
                    # The validated upload has the original hash. Restore the same key so
                    # historical drafts and immutable bank revisions keep their source.
                    incoming.replace(storage.path(existing.storage_key))
                job = session.scalar(
                    select(PdfImportJob)
                    .where(PdfImportJob.document_id == existing.id)
                    .with_for_update()
                )
                if (
                    job
                    and job.status == "FAILED"
                    and existing.error_summary
                    in {"SOURCE_MISSING", "SOURCE_INTEGRITY_FAILURE", "SOURCE_UNREADABLE"}
                ):
                    job.status = existing.import_status = "QUEUED"
                    existing.error_summary = None
                return existing.id, True
            identifier = uuid.uuid4()
            key = f"sources/{identifier.hex}.pdf"
            final = storage.path(key)
            incoming.rename(final)
            document = PdfDocument(
                id=identifier,
                original_filename=filename,
                storage_key=key,
                sha256_hash=digest.hexdigest(),
                file_size_bytes=size,
                page_count=details["pageCount"],
                uploaded_by_admin_id=admin.id,
                import_status="QUEUED",
            )
            session.add(document)
            session.flush()
            session.add(
                PdfImportJob(
                    document_id=identifier, total_pages=document.page_count, status="QUEUED"
                )
            )
        committed = True
        return identifier, False
    except OSError:
        raise PdfError("PDF_STORAGE_UNAVAILABLE", 503) from None
    finally:
        incoming.unlink(missing_ok=True)
        if final and not committed:
            final.unlink(missing_ok=True)
