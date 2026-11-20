"""Project-scoped evidence references for shared component routes.

Accepted forms mirror the acceptance checklist contract:
``<photo_id>``, ``photo:<photo_id>``, ``document:<document_id>``,
``page:<page_id>`` and ``page:<document_id>:<page_number>`` (or ``#``).
Unresolved references and references from another project are rejected.
"""

import re
from typing import Sequence

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session


def _photo_confirmed(photo) -> bool:
    return bool((getattr(photo, "confirmed_caption", None) or "").strip()
                or (getattr(photo, "category", None) or "").strip())


def validate_evidence_refs(db: Session, project_id: str, refs: Sequence[str]) -> list[str]:
    try:
        from app.site.models import SitePhoto
    except Exception:  # pragma: no cover - isolated core deployments
        SitePhoto = None
    try:
        from app.engineering_ai.models import DocumentPage, SourceDocument
    except Exception:  # pragma: no cover - isolated core deployments
        DocumentPage = SourceDocument = None

    def photo(photo_id: str) -> None:
        if SitePhoto is None:
            return
        item = db.get(SitePhoto, photo_id)
        if item is None or item.project_id != project_id:
            raise HTTPException(404, "Evidence photo not found in this project")
        if not _photo_confirmed(item):
            raise HTTPException(422, "Evidence photo is not confirmed")

    def document(document_id: str) -> None:
        if SourceDocument is None:
            return
        item = db.get(SourceDocument, document_id)
        if item is None or item.project_id != project_id:
            raise HTTPException(404, "Evidence document not found in this project")

    def page(page_id: str) -> None:
        if DocumentPage is None:
            return
        item = db.get(DocumentPage, page_id)
        if item is None or item.project_id != project_id:
            raise HTTPException(404, "Evidence page not found in this project")

    def page_number(document_id: str, number: int) -> None:
        document(document_id)
        if DocumentPage is None:
            return
        item = db.scalar(select(DocumentPage).where(
            DocumentPage.document_id == document_id, DocumentPage.page_number == number))
        if item is None or item.project_id != project_id:
            raise HTTPException(404, "Evidence page not found in this project")

    cleaned: list[str] = []
    for raw in refs:
        ref = (raw or "").strip()
        if not ref:
            raise HTTPException(422, "Empty evidence reference")
        if len(ref) > 120:
            raise HTTPException(422, "Evidence reference is too long")
        lowered = ref.lower()
        if lowered.startswith("photo:"):
            photo_id = ref[len("photo:"):].strip()
            if not photo_id:
                raise HTTPException(422, "Evidence photo id is required")
            photo(photo_id)
        elif lowered.startswith("document:"):
            document_id = ref[len("document:"):].strip()
            if not document_id:
                raise HTTPException(422, "Evidence document id is required")
            document(document_id)
        elif lowered.startswith("page:"):
            target = ref[len("page:"):].strip()
            if not target:
                raise HTTPException(422, "Evidence page id is required")
            if "#" in target:
                document_id, number = target.rsplit("#", 1)
            elif ":" in target:
                document_id, number = target.rsplit(":", 1)
            else:
                page(target)
                cleaned.append(ref)
                continue
            try:
                page_no = int(number.strip())
            except ValueError:
                raise HTTPException(422, "Evidence page number is invalid") from None
            if page_no < 1:
                raise HTTPException(422, "Evidence page number is invalid")
            page_number(document_id.strip(), page_no)
        elif re.match(r"^[a-z][a-z0-9_]*:", lowered):
            raise HTTPException(422, f"Unsupported evidence type: {ref.split(':', 1)[0]}")
        else:
            photo(ref)
        cleaned.append(ref)
    return cleaned
