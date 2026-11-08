"""Bounded local worker. Run separately from Uvicorn. No PDF content in output."""

import argparse
import subprocess
import sys
import time
from pathlib import Path
from uuid import UUID

from sqlalchemy import and_, or_, select, text
from sqlalchemy.dialects.postgresql import insert

# Allow `python scripts/pdf_worker.py` from the backend directory. Python puts
# the script directory on sys.path, not the backend root.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import Settings  # noqa: E402
from app.db.session import Database  # noqa: E402
from app.models.exam_bank import BankRevision  # noqa: E402
from app.models.pdf_import import PdfDocument, PdfImportJob  # noqa: E402
from app.services.pdf.jobs import fail_job, process_job, try_lock, unlock  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--job", type=UUID)
    arguments = parser.parse_args()
    settings = Settings()
    if arguments.job:
        from app.services.pdf.limits import limit_memory

        limit_memory(settings.pdf_worker_memory_mb)
        process_job(settings, arguments.job)
        return
    database = Database(settings)
    # One coordinator per database. The connection is dedicated, not held in a transaction.
    with database.engine.connect() as coordinator:
        if not coordinator.scalar(text("SELECT pg_try_advisory_lock(138112, 6)")):
            raise SystemExit("A PDF worker is already active for this database.")
        coordinator.commit()
        try:
            while True:
                with database.session_factory.begin() as session:
                    # Discover authenticated uploads from the durable storage registry.
                    # A disk-only file has no uploader identity and is never adopted.
                    missing = session.execute(
                        select(PdfDocument.id, PdfDocument.page_count)
                        .where(
                            ~select(PdfImportJob.id)
                            .where(PdfImportJob.document_id == PdfDocument.id)
                            .exists()
                        )
                        .limit(100)
                    ).all()
                    if missing:
                        session.execute(
                            insert(PdfImportJob)
                            .values(
                                [
                                    {
                                        "document_id": document_id,
                                        "total_pages": pages,
                                        "status": "QUEUED",
                                    }
                                    for document_id, pages in missing
                                ]
                            )
                            .on_conflict_do_nothing(index_elements=[PdfImportJob.document_id])
                        )
                    identifier = session.scalar(
                        select(PdfImportJob.id)
                        .join(PdfDocument, PdfDocument.id == PdfImportJob.document_id)
                        .where(
                            or_(
                                PdfImportJob.status.in_(["QUEUED", "PROCESSING"]),
                                and_(
                                    PdfImportJob.status.in_(
                                        ["COMPLETED", "COMPLETED_WITH_WARNINGS"]
                                    ),
                                    ~select(BankRevision.id)
                                    .where(BankRevision.job_id == PdfImportJob.id)
                                    .exists(),
                                ),
                            )
                        )
                        .order_by(PdfDocument.created_at, PdfImportJob.id)
                        .limit(1)
                    )
                if identifier:
                    try:
                        subprocess.run(
                            [
                                sys.executable,
                                str(Path(__file__).resolve()),
                                "--job",
                                str(identifier),
                            ],
                            timeout=settings.pdf_job_timeout_seconds,
                            check=True,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        )
                    except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
                        with database.engine.connect() as connection:
                            if try_lock(connection, identifier):
                                try:
                                    fail_job(
                                        database,
                                        identifier,
                                        "WORKER_TIMEOUT_OR_EXIT",
                                        include_queued=True,
                                    )
                                finally:
                                    unlock(connection, identifier)
                elif arguments.once:
                    break
                else:
                    time.sleep(2)
        finally:
            coordinator.execute(text("SELECT pg_advisory_unlock(138112, 6)"))
            coordinator.commit()
            database.dispose()


if __name__ == "__main__":
    main()
