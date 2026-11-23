"""Private, project-scoped file storage for Engineering AI source documents.

Files are never mounted as static assets.  Every read goes through an API route
that first checks project membership.  Storage layout::

    <root>/projects/<project_id>/documents/<sha[:2]>/<sha>.pdf
    <root>/projects/<project_id>/documents/<document_id>/pages/page-0001.png

Uploads are disabled; the module only resolves existing original/render paths.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

_SAFE_COMPONENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


class StorageError(ValueError):
    """Raised when a path component is unsafe."""


def storage_root() -> Path:
    from .dependencies import storage_dir

    return storage_dir()


def safe_component(value: str, label: str = "id") -> str:
    if not isinstance(value, str) or not _SAFE_COMPONENT.match(value):
        raise StorageError(f"invalid {label}")
    return value


def project_root(project_id: str) -> Path:
    return storage_root() / "projects" / safe_component(project_id, "project_id")


def page_render_path(project_id: str, document_id: str, page_number: int) -> Path:
    doc_id = safe_component(document_id, "document_id")
    if not isinstance(page_number, int) or page_number < 1:
        raise StorageError("invalid page_number")
    return project_root(project_id) / "documents" / doc_id / "pages" / f"page-{page_number:04d}.png"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
