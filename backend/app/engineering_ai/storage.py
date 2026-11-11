"""Private, project-scoped file storage for Engineering AI source documents.

Files are never mounted as static assets.  Every read goes through an API route
that first checks project membership.  Storage layout::

    <root>/projects/<project_id>/documents/<sha[:2]>/<sha>.pdf
    <root>/projects/<project_id>/documents/<document_id>/pages/page-0001.png

The original file is written atomically and keyed by its SHA-256, so a retry or
duplicate upload cannot fork the bytes.
"""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path

_SAFE_COMPONENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


class StorageError(ValueError):
    """Raised when a path component or file payload is unsafe."""


def storage_root() -> Path:
    from .dependencies import storage_dir

    return storage_dir()


def safe_component(value: str, label: str = "id") -> str:
    if not isinstance(value, str) or not _SAFE_COMPONENT.match(value):
        raise StorageError(f"invalid {label}")
    return value


def project_root(project_id: str) -> Path:
    return storage_root() / "projects" / safe_component(project_id, "project_id")


def document_path(project_id: str, sha256: str) -> Path:
    digest = safe_component(sha256, "sha256")
    return project_root(project_id) / "documents" / digest[:2] / f"{digest}.pdf"


def page_render_path(project_id: str, document_id: str, page_number: int) -> Path:
    doc_id = safe_component(document_id, "document_id")
    if not isinstance(page_number, int) or page_number < 1:
        raise StorageError("invalid page_number")
    return project_root(project_id) / "documents" / doc_id / "pages" / f"page-{page_number:04d}.png"


def max_pdf_bytes() -> int:
    return int(os.getenv("ENGINEERING_AI_MAX_PDF_BYTES", str(50 * 1024 * 1024)))


def max_image_bytes() -> int:
    return int(os.getenv("ENGINEERING_AI_MAX_IMAGE_BYTES", str(15 * 1024 * 1024)))


def max_pages() -> int:
    return int(os.getenv("ENGINEERING_AI_MAX_PAGES", "500"))


def is_pdf_header(data: bytes) -> bool:
    """PDF header may legally appear up to byte 1024 (leading junk allowed)."""

    return b"%PDF-" in data[:1024]


def is_pdf(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            return is_pdf_header(handle.read(1024))
    except OSError:
        return False


IMAGE_MAGIC = (
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
)


def detect_image_mime(data: bytes) -> str | None:
    for magic, mime in IMAGE_MAGIC:
        if data.startswith(magic):
            return mime
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def save_pdf(project_id: str, sha256: str, data: bytes) -> Path:
    """Atomically persist original PDF bytes; safe to call twice with same hash."""

    target = document_path(project_id, sha256)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.stat().st_size == len(data):
        return target
    fd, tmp_name = tempfile.mkstemp(prefix=".upload-", suffix=".pdf", dir=str(target.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, target)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
    return target


def write_render(path: Path, data: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=".render-", suffix=".png", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
    return path


def sha256_bytes(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()
