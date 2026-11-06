"""Only generated relative storage keys are accepted. Nothing is publicly mounted."""

import hashlib
import re
import stat
import tempfile
from pathlib import Path

from app.core.config import Settings

KEY = re.compile(r"(?:sources/[0-9a-f]{32}[.]pdf|assets/[0-9a-f]{64}[.]png)")


class PdfError(Exception):
    def __init__(self, code: str, status: int = 422):
        self.code = code
        self.status = status


class PdfStorage:
    def __init__(self, settings: Settings):
        try:
            self.root = settings.pdf_storage_root.resolve()
            if any(
                part.lower() in {"public", "static", "node_modules", ".next"}
                for part in self.root.parts
            ):
                raise PdfError("UNSAFE_STORAGE_CONFIGURATION", 503)
            self.root.mkdir(parents=True, exist_ok=True)
            for folder in ("sources", "assets", "incoming"):
                target = self.root / folder
                if target.is_symlink() or target.resolve().parent != self.root:
                    raise PdfError("UNSAFE_STORAGE_CONFIGURATION", 503)
                target.mkdir(exist_ok=True)
        except OSError:
            raise PdfError("PDF_STORAGE_UNAVAILABLE", 503) from None

    def path(self, key: str) -> Path:
        if not KEY.fullmatch(key):
            raise PdfError("INVALID_STORAGE_KEY", 404)
        path = self.root / key
        if path.is_symlink() or not path.resolve().is_relative_to(self.root):
            raise PdfError("INVALID_STORAGE_KEY", 404)
        return path

    def source(self, key: str, digest: str, size: int) -> Path:
        path = self.path(key)
        if not key.startswith("sources/"):
            raise PdfError("INVALID_STORAGE_KEY", 404)
        try:
            metadata = path.stat()
            if not stat.S_ISREG(metadata.st_mode):
                raise PdfError("SOURCE_UNREADABLE", 503)
            if metadata.st_size != size:
                raise PdfError("SOURCE_INTEGRITY_FAILURE", 503)
            with path.open("rb") as stream:
                remaining = size
                actual = hashlib.sha256()
                while remaining and (chunk := stream.read(min(remaining, 1024 * 1024))):
                    actual.update(chunk)
                    remaining -= len(chunk)
                if remaining or stream.read(1) or actual.hexdigest() != digest:
                    raise PdfError("SOURCE_INTEGRITY_FAILURE", 503)
        except FileNotFoundError:
            raise PdfError("SOURCE_MISSING", 404) from None
        except OSError:
            raise PdfError("SOURCE_UNREADABLE", 503) from None
        return path

    def asset(self, data: bytes) -> tuple[str, str]:
        digest = hashlib.sha256(data).hexdigest()
        key = f"assets/{digest}.png"
        path = self.path(key)
        if path.exists():
            if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                raise PdfError("ASSET_INTEGRITY_FAILURE", 503)
        else:
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(
                    dir=self.root / "incoming", delete=False
                ) as stream:
                    temporary = Path(stream.name)
                    stream.write(data)
                temporary.replace(path)
            finally:
                if temporary:
                    temporary.unlink(missing_ok=True)
        return key, digest
