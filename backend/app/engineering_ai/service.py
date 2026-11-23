"""Business logic for document ingestion, retrieval, chat and vision proposals."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, List, Optional, Tuple

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import fts, storage, vector_store
from .chunking import chunk_text, chunk_text_with_sections
from .component_chat import answer_component_query, parse_component_query
from .constants import (
    CROSS_REFERENCE_DISCLAIMER,
    CROSS_REFERENCE_NO_FINDING,
    DAILY_REPORT_DRAFT_DISCLAIMER,
    DAILY_REPORT_DRAFT_WARNING,
    DOCUMENT_TYPES,
    INSPECTION_CHECKLIST_DISCLAIMER,
    LOW_OCR_THRESHOLD,
    LOW_OCR_WARNING,
    NO_SOURCE_ANSWER,
    UNVERIFIED_KB_NOTE,
    VERSION_COMPARE_DISCLAIMER,
    VISION_CHAT_DISCLAIMER,
    VISION_DISCLAIMER,
)
from .crossref import suggest_discrepancies
from .database_chat import answer_database_question, answer_structured_question
from .embeddings import EmbeddingProvider, HashingEmbeddingProvider, tokenize
from .extraction import ExtractionError, extract_document
from .inspection import choose_checklist_criterion
from .models import (
    AICitation,
    AIConversation,
    DocumentChunk,
    DocumentEmbedding,
    DocumentPage,
    PageExtraction,
    SourceDocument,
)
from .ocr import OcrEngine
from .page_extraction import validate_extraction
from .page_navigation import answer_page_navigation
from .providers import (
    AnswerProvider,
    ProviderAnswer,
)
from .retrieval import RetrievedChunk, quote_window, search_chunks
from .schemas import (
    ChatResponse,
    CitationOut,
    ConversationMessageOut,
    ConversationOut,
    CrossReferenceResponse,
    CrossReferenceSuggestionOut,
    DailyReportDraftContent,
    DailyReportDraftRequest,
    DailyReportDraftResponse,
    DocumentOut,
    InspectionChecklistRequest,
    InspectionChecklistResponse,
    InspectionChecklistSuggestionOut,
    InspectionWorkItemOut,
    MissingFieldOut,
    PageOut,
    PageSummaryOut,
    PageExtractionIn,
    PageExtractionOut,
    PhotoSuggestionOut,
    ReportDraftManpower,
    ReportDraftPlan,
    ReportDraftSource,
    ReportDraftWorkLog,
    SearchResponse,
    VersionCompareOut,
    VersionSummaryOut,
    PageVersionChangeOut,
    VisionRegionOut,
)
from .vision import NoopVisionProvider, VisionProvider


class DocumentValidationError(ValueError):
    """Uploaded bytes or metadata are invalid."""


class DocumentConflict(RuntimeError):
    """Ingest cannot start because the document is already running."""


class PageExtractionConflict(RuntimeError):
    """Verified extraction must not be overwritten by the same version key."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _json_list(raw: Optional[str]) -> List[Any]:
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        return []
    return value if isinstance(value, list) else []


def _warnings(raw: Optional[str]) -> List[str]:
    return [str(item) for item in _json_list(raw)]


def _utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _page_url(project_id: str, document_id: str, page_number: int) -> str:
    return f"/api/v1/projects/{project_id}/documents/{document_id}/pages/{page_number}"


def document_to_out(
    db: Session,
    document: SourceDocument,
    *,
    include_pages: bool = False,
    deduplicated: bool = False,
) -> DocumentOut:
    pages: List[PageSummaryOut] = []
    if include_pages:
        rows = db.scalars(
            select(DocumentPage)
            .where(DocumentPage.document_id == document.id)
            .order_by(DocumentPage.page_number)
        ).all()
        pages = [
            PageSummaryOut(
                id=page.id,
                page_number=page.page_number,
                extraction_method=page.extraction_method,
                ocr_confidence=page.ocr_confidence,
                drawing_number=page.drawing_number,
                revision=page.revision,
                needs_review=page.needs_review,
                url=_page_url(document.project_id, document.id, page.page_number),
            )
            for page in rows
        ]
    return DocumentOut(
        id=document.id,
        project_id=document.project_id,
        type=document.type,
        original_name=document.original_name,
        document_key=document.document_key,
        version=document.version,
        is_current=document.is_current,
        is_effective=document.is_effective,
        change_note=document.change_note,
        effective_at=_utc(document.effective_at),
        effective_by=document.effective_by,
        sha256=document.sha256,
        status=document.status,
        mime_type=document.mime_type,
        size_bytes=document.size_bytes,
        page_count=document.page_count,
        drawing_number=document.drawing_number,
        revision=document.revision,
        ocr_languages=document.ocr_languages,
        warnings=_warnings(document.warnings_json),
        error_message=document.error_message,
        created_by=document.created_by,
        ingest_started_at=_utc(document.ingest_started_at),
        ingest_finished_at=_utc(document.ingest_finished_at),
        created_at=_utc(document.created_at),
        updated_at=_utc(document.updated_at),
        original_url=f"/api/v1/projects/{document.project_id}/documents/{document.id}/original",
        pages=pages,
        deduplicated=deduplicated,
    )


def page_to_out(page: DocumentPage) -> PageOut:
    render_url = None
    if page.rendered_path:
        render_url = (
            f"/api/v1/projects/{page.project_id}/documents/{page.document_id}"
            f"/pages/{page.page_number}/render"
        )
    return PageOut(
        id=page.id,
        project_id=page.project_id,
        document_id=page.document_id,
        page_number=page.page_number,
        extraction_method=page.extraction_method,
        text=page.text,
        ocr_text=page.ocr_text,
        tables=_json_list(page.tables_json),
        ocr_confidence=page.ocr_confidence,
        drawing_number=page.drawing_number,
        revision=page.revision,
        width=page.width,
        height=page.height,
        needs_review=page.needs_review,
        warnings=_warnings(page.warnings_json),
        render_url=render_url,
        original_url=(
            f"/api/v1/projects/{page.project_id}/documents/{page.document_id}/original"
        ),
    )


def citation_to_out(result: RetrievedChunk, quote: Optional[str] = None) -> CitationOut:
    return CitationOut(
        document_id=result.document_id,
        document_name=result.document_name,
        version=result.version,
        page_number=result.page_number,
        drawing_number=result.drawing_number,
        revision=result.revision,
        quote=quote if quote is not None else result.quote,
        url=result.url,
        ocr_confidence=result.ocr_confidence,
        chunk_id=result.chunk_id,
        page_id=result.page_id,
        extraction_method=result.extraction_method,
        score=result.score,
        section=result.section,
    )


def _page_citation_out(
    project_id: str,
    document: SourceDocument,
    page: DocumentPage,
    quote: str,
) -> CitationOut:
    return CitationOut(
        document_id=document.id,
        document_name=document.original_name,
        version=document.version,
        page_number=page.page_number,
        drawing_number=page.drawing_number or document.drawing_number,
        revision=page.revision or document.revision,
        quote=quote,
        url=_page_url(project_id, document.id, page.page_number),
        ocr_confidence=(
            page.ocr_confidence if page.extraction_method == "ocr" else None
        ),
        chunk_id=None,
        page_id=page.id,
        extraction_method=page.extraction_method,
        score=None,
    )


def create_document(
    db: Session,
    project_id: str,
    data: bytes,
    filename: Optional[str],
    declared_mime: Optional[str],
    document_type: Optional[str],
    created_by: Optional[str],
    change_note: Optional[str] = None,
) -> Tuple[SourceDocument, bool]:
    if not data:
        raise DocumentValidationError("Tệp rỗng.")
    if len(data) > storage.max_pdf_bytes():
        raise DocumentValidationError("Tệp PDF vượt quá dung lượng cho phép.")
    if not storage.is_pdf_header(data):
        raise DocumentValidationError("Tệp tải lên không phải PDF hợp lệ.")

    name = os.path.basename((filename or "document.pdf").replace("\\", "/")).strip() or "document.pdf"
    name = name[:255]
    key = name.casefold()[:255]
    mime = declared_mime if declared_mime == "application/pdf" else "application/pdf"
    if document_type is None:
        lowered = name.casefold()
        if any(word in lowered for word in ("ban-ve", "bản vẽ", "drawing", "dwg", "bv")):
            document_type = "drawing"
        elif any(word in lowered for word in ("thuyet-minh", "thuyết minh", "spec")):
            document_type = "specification"
        elif any(word in lowered for word in ("huong-dan", "hướng dẫn", "guideline")):
            document_type = "technical_guideline"
        elif any(word in lowered for word in ("bien-phap", "biện pháp", "method")):
            document_type = "construction_method"
        elif any(word in lowered for word in ("vat-lieu", "vật liệu", "material")):
            document_type = "material_record"
        elif any(word in lowered for word in ("thi-nghiem", "thí nghiệm", "test")):
            document_type = "test_record"
        elif any(word in lowered for word in ("nghiem-thu", "nghiệm thu", "acceptance")):
            document_type = "acceptance_record"
        elif "tieu-chuan" in lowered or "tiêu chuẩn" in lowered or "standard" in lowered:
            document_type = "standard"
        else:
            document_type = "other"
    if document_type not in DOCUMENT_TYPES:
        raise DocumentValidationError("Loại hồ sơ không hợp lệ.")

    digest = storage.sha256_bytes(data)
    existing = db.scalar(
        select(SourceDocument).where(
            SourceDocument.project_id == project_id,
            SourceDocument.sha256 == digest,
        )
    )
    if existing is not None:
        return existing, False

    path = storage.save_pdf(project_id, digest, data)
    for attempt in range(4):
        latest_version = db.scalar(
            select(func.max(SourceDocument.version)).where(
                SourceDocument.project_id == project_id,
                SourceDocument.document_key == key,
            )
        )
        version = int(latest_version or 0) + 1
        if version > 1:
            db.execute(
                SourceDocument.__table__.update()
                .where(
                    SourceDocument.project_id == project_id,
                    SourceDocument.document_key == key,
                    SourceDocument.is_current.is_(True),
                )
                .values(is_current=False)
            )
        document = SourceDocument(
            project_id=project_id,
            type=document_type,
            original_name=name,
            document_key=key,
            original_path=str(path),
            sha256=digest,
            version=version,
            is_current=True,
            is_effective=version == 1,
            change_note=(change_note or "").strip()[:2000] or None,
            status="pending",
            mime_type=mime,
            size_bytes=len(data),
            page_count=0,
            created_by=created_by,
        )
        db.add(document)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            existing = db.scalar(
                select(SourceDocument).where(
                    SourceDocument.project_id == project_id,
                    SourceDocument.sha256 == digest,
                )
            )
            if existing is not None:
                return existing, False
            if attempt == 3:
                raise DocumentConflict(
                    "Không cấp được phiên bản hồ sơ do tải lên đồng thời; thử lại."
                ) from exc
            continue
        db.refresh(document)
        return document, True
    raise DocumentConflict("Không cấp được phiên bản hồ sơ; thử lại.")


def get_document(db: Session, project_id: str, document_id: str) -> Optional[SourceDocument]:
    return db.scalar(
        select(SourceDocument).where(
            SourceDocument.project_id == project_id,
            SourceDocument.id == document_id,
        )
    )


def list_documents(
    db: Session,
    project_id: str,
    *,
    include_history: bool = True,
) -> List[SourceDocument]:
    query = select(SourceDocument).where(SourceDocument.project_id == project_id)
    if not include_history:
        query = query.where(SourceDocument.is_current.is_(True))
    return list(
        db.scalars(query.order_by(SourceDocument.created_at.desc(), SourceDocument.version.desc())).all()
    )


def get_page(
    db: Session,
    project_id: str,
    document_id: str,
    page_number: int,
) -> Optional[DocumentPage]:
    return db.scalar(
        select(DocumentPage)
        .join(SourceDocument, DocumentPage.document_id == SourceDocument.id)
        .where(
            DocumentPage.project_id == project_id,
            DocumentPage.document_id == document_id,
            DocumentPage.page_number == page_number,
            SourceDocument.project_id == project_id,
        )
    )


def _table_count(page: DocumentPage) -> int:
    try:
        value = json.loads(page.tables_json or "[]")
    except (TypeError, ValueError):
        return 0
    return len(value) if isinstance(value, list) else 0


def _version_summary(db: Session, document: SourceDocument) -> VersionSummaryOut:
    chunk_count = int(
        db.scalar(
            select(func.count())
            .select_from(DocumentChunk)
            .where(DocumentChunk.document_id == document.id)
        )
        or 0
    )
    total_chars = int(
        db.scalar(
            select(func.coalesce(func.sum(DocumentChunk.char_count), 0)).where(
                DocumentChunk.document_id == document.id
            )
        )
        or 0
    )
    return VersionSummaryOut(
        id=document.id,
        version=document.version,
        is_current=document.is_current,
        is_effective=document.is_effective,
        status=document.status,
        original_name=document.original_name,
        sha256=document.sha256,
        page_count=document.page_count,
        chunk_count=chunk_count,
        total_chars=total_chars,
        effective_at=_utc(document.effective_at),
        effective_by=document.effective_by,
    )


def confirm_effective(
    db: Session,
    project_id: str,
    document_id: str,
    change_note: str,
    actor_id: Optional[str],
) -> SourceDocument:
    document = get_document(db, project_id, document_id)
    if document is None:
        raise LookupError("Hồ sơ không thuộc công trình này.")
    note = change_note.strip()
    if not note:
        raise DocumentValidationError("change_note không được để trống.")
    db.execute(
        update(SourceDocument)
        .where(
            SourceDocument.project_id == project_id,
            SourceDocument.document_key == document.document_key,
            SourceDocument.id != document.id,
        )
        .values(is_effective=False)
    )
    document.is_effective = True
    document.change_note = note
    document.effective_at = _now()
    document.effective_by = actor_id
    db.commit()
    db.refresh(document)
    return document


def list_versions(db: Session, project_id: str, document_id: str) -> List[SourceDocument]:
    document = get_document(db, project_id, document_id)
    if document is None:
        raise LookupError("Hồ sơ không thuộc công trình này.")
    return list(
        db.scalars(
            select(SourceDocument)
            .where(
                SourceDocument.project_id == project_id,
                SourceDocument.document_key == document.document_key,
            )
            .order_by(SourceDocument.version.desc())
        ).all()
    )


def compare_versions(
    db: Session,
    project_id: str,
    left_id: str,
    right_id: str,
) -> VersionCompareOut:
    left = get_document(db, project_id, left_id)
    right = get_document(db, project_id, right_id)
    if left is None or right is None:
        raise LookupError("Hồ sơ không thuộc công trình này.")
    if left.document_key != right.document_key:
        raise DocumentValidationError("Chỉ so sánh các phiên bản của cùng một họ hồ sơ.")
    left_pages = {
        page.page_number: page
        for page in db.scalars(
            select(DocumentPage).where(DocumentPage.document_id == left.id)
        ).all()
    }
    right_pages = {
        page.page_number: page
        for page in db.scalars(
            select(DocumentPage).where(DocumentPage.document_id == right.id)
        ).all()
    }
    page_changes = []
    for page_number in sorted(set(left_pages) | set(right_pages)):
        left_page = left_pages.get(page_number)
        right_page = right_pages.get(page_number)
        left_text = (left_page.text if left_page else "") or ""
        right_text = (right_page.text if right_page else "") or ""
        page_changes.append(
            PageVersionChangeOut(
                page_number=page_number,
                left_chars=len(left_text),
                right_chars=len(right_text),
                changed=left_text != right_text,
            )
        )
    left_summary = _version_summary(db, left)
    right_summary = _version_summary(db, right)
    return VersionCompareOut(
        project_id=project_id,
        same_document_key=True,
        left=left_summary,
        right=right_summary,
        page_count_delta=right.page_count - left.page_count,
        chunk_count_delta=right_summary.chunk_count - left_summary.chunk_count,
        total_chars_delta=right_summary.total_chars - left_summary.total_chars,
        left_table_count=sum(_table_count(page) for page in left_pages.values()),
        right_table_count=sum(_table_count(page) for page in right_pages.values()),
        page_changes=page_changes,
        warnings=["Chỉ so sánh metadata/thống kê; không kết luận thay đổi thiết kế."],
        disclaimer=VERSION_COMPARE_DISCLAIMER,
    )


def _page_sha256(page: DocumentPage, project_id: str) -> Optional[str]:
    if not page.rendered_path:
        return None
    try:
        path = Path(page.rendered_path).resolve()
        root = storage.project_root(project_id).resolve()
        path.relative_to(root)
        data = path.read_bytes()
        return storage.sha256_bytes(data)
    except (OSError, ValueError):
        return None


def page_extraction_to_out(row: PageExtraction) -> PageExtractionOut:
    try:
        extraction = json.loads(row.extraction_json)
    except (TypeError, ValueError):
        extraction = {}
    if not isinstance(extraction, dict):
        extraction = {}
    warnings = _warnings(row.warnings_json)
    return PageExtractionOut(
        id=row.id,
        project_id=row.project_id,
        document_id=row.document_id,
        page_id=row.page_id,
        page_number=row.page_number,
        page_sha256=row.page_sha256,
        model=row.model,
        prompt_version=row.prompt_version,
        mode=row.mode,
        status=row.status,
        confidence=row.confidence,
        extraction=extraction,
        warnings=warnings,
        created_by=row.created_by,
        verified_by=row.verified_by,
        verified_at=_utc(row.verified_at),
        verify_note=row.verify_note,
        created_at=_utc(row.created_at),
        updated_at=_utc(row.updated_at),
    )


def save_page_extraction(
    db: Session,
    project_id: str,
    document_id: str,
    page_number: int,
    payload: PageExtractionIn,
    actor_id: Optional[str],
) -> PageExtractionOut:
    page = get_page(db, project_id, document_id, page_number)
    if page is None:
        raise LookupError("Trang không thuộc công trình/hồ sơ này.")
    errors = validate_extraction(payload.extraction)
    if errors:
        raise DocumentValidationError(
            "Extraction không đúng schema: " + "; ".join(errors[:8])
        )
    extraction = payload.extraction
    confidence = payload.confidence
    if confidence is None and isinstance(extraction.get("confidence"), (int, float)):
        confidence = float(extraction["confidence"])
    warnings = payload.warnings
    if not warnings and isinstance(extraction.get("warnings"), list):
        warnings = [str(item) for item in extraction["warnings"] if isinstance(item, str)]
    page_hash = _page_sha256(page, project_id)
    row = db.scalar(
        select(PageExtraction).where(
            PageExtraction.page_id == page.id,
            PageExtraction.model == payload.model,
            PageExtraction.prompt_version == payload.prompt_version,
            PageExtraction.mode == payload.mode,
        )
    )
    if row is not None and row.status == "verified":
        raise PageExtractionConflict(
            "Extraction đã được xác minh; không ghi đè. "
            "Hãy tạo phiên bản mới bằng model, prompt_version hoặc mode khác."
        )
    if row is None:
        row = PageExtraction(
            project_id=project_id,
            document_id=document_id,
            page_id=page.id,
            page_number=page_number,
            page_sha256=page_hash,
            model=payload.model,
            prompt_version=payload.prompt_version,
            mode=payload.mode,
            status="proposed",
            confidence=confidence,
            extraction_json=json.dumps(extraction, ensure_ascii=False),
            warnings_json=json.dumps(warnings, ensure_ascii=False),
            created_by=actor_id,
        )
        db.add(row)
    else:
        row.project_id = project_id
        row.document_id = document_id
        row.page_number = page_number
        row.page_sha256 = page_hash
        row.status = "proposed"
        row.confidence = confidence
        row.extraction_json = json.dumps(extraction, ensure_ascii=False)
        row.warnings_json = json.dumps(warnings, ensure_ascii=False)
        row.created_by = row.created_by or actor_id
        row.verified_by = None
        row.verified_at = None
        row.verify_note = None
    db.commit()
    db.refresh(row)
    return page_extraction_to_out(row)


def list_page_extractions(
    db: Session,
    project_id: str,
    document_id: str,
    page_number: Optional[int] = None,
    status: Optional[str] = None,
) -> List[PageExtractionOut]:
    if get_document(db, project_id, document_id) is None:
        raise LookupError("Hồ sơ không thuộc công trình này.")
    query = select(PageExtraction).where(
        PageExtraction.project_id == project_id,
        PageExtraction.document_id == document_id,
    )
    if page_number is not None:
        query = query.where(PageExtraction.page_number == page_number)
    if status:
        query = query.where(PageExtraction.status == status)
    rows = db.scalars(
        query.order_by(PageExtraction.page_number, PageExtraction.created_at.desc())
    ).all()
    return [page_extraction_to_out(row) for row in rows]


def get_page_extraction(
    db: Session, project_id: str, extraction_id: str
) -> Optional[PageExtraction]:
    return db.scalar(
        select(PageExtraction).where(
            PageExtraction.project_id == project_id,
            PageExtraction.id == extraction_id,
        )
    )


def verify_page_extraction(
    db: Session,
    project_id: str,
    extraction_id: str,
    status: str,
    note: Optional[str],
    actor_id: Optional[str],
) -> PageExtractionOut:
    if status not in {"verified", "rejected"}:
        raise DocumentValidationError("Chỉ chấp nhận verified hoặc rejected.")
    row = get_page_extraction(db, project_id, extraction_id)
    if row is None:
        raise LookupError("Extraction không thuộc công trình này.")
    row.status = status
    row.verified_by = actor_id
    row.verified_at = _now()
    row.verify_note = (note or "").strip() or None
    db.commit()
    db.refresh(row)
    return page_extraction_to_out(row)


def _safe_embedding(provider: EmbeddingProvider, text: str) -> Tuple[List[float], str]:
    try:
        vector = provider.embed(text)
        if vector:
            return vector, provider.name
    except Exception:  # noqa: BLE001 - fall back to deterministic local vectors
        pass
    fallback = HashingEmbeddingProvider()
    return fallback.embed(text), fallback.name


def run_ingest_job(
    document_id: str,
    project_id: str,
    session_factory: Callable[[], Session],
    ocr_engine: OcrEngine,
    embedding_provider: EmbeddingProvider,
    max_pages: int,
    languages: str,
    status_hook: Optional[Callable[[str], None]] = None,
) -> None:
    """Background ingest. Safe to retry; rows are rebuilt, never duplicated.

    Status order: pending -> running -> ocr_completed -> indexing -> ready;
    any failure becomes failed.  ``status_hook`` is a test/diagnostic hook.
    """

    db = session_factory()
    try:
        document = db.get(SourceDocument, document_id)
        if document is None or document.project_id != project_id:
            return
        had_ready_index = bool(
            document.page_count
            and db.scalar(select(DocumentChunk.id).where(DocumentChunk.document_id == document.id))
            and db.scalar(select(DocumentPage.id).where(DocumentPage.document_id == document.id))
        )
        try:
            if status_hook:
                status_hook("pending")
            document.status = "running"
            document.ingest_started_at = _now()
            document.ingest_finished_at = None
            document.error_message = None
            if status_hook:
                status_hook("running")
            db.commit()

            source_path = Path(document.original_path)
            if storage.sha256_bytes(source_path.read_bytes()) != document.sha256:
                raise ExtractionError("PDF gốc đã thay đổi; cần tải lên như phiên bản mới.")
            old_pages = {
                page.page_number: page
                for page in db.scalars(
                    select(DocumentPage).where(DocumentPage.document_id == document.id)
                ).all()
            }
            old_render_hashes = {
                number: _page_sha256(page, project_id)
                for number, page in old_pages.items()
            }
            extraction = extract_document(
                Path(document.original_path),
                project_id,
                document.id,
                ocr_engine=ocr_engine,
                languages=languages,
                max_pages=max_pages,
            )

            old_embeddings = db.execute(
                select(
                    DocumentEmbedding.model,
                    DocumentEmbedding.dim,
                    DocumentEmbedding.chunk_id,
                ).where(DocumentEmbedding.document_id == document.id)
            ).all()
            grouped_old: dict[tuple[str, int], list[str]] = {}
            for model, dim, chunk_id in old_embeddings:
                grouped_old.setdefault((model, dim), []).append(chunk_id)
            for (model, dim), chunk_ids in grouped_old.items():
                vector_store.delete_chunks(db, project_id, model, dim, chunk_ids)

            db.execute(
                delete(DocumentEmbedding).where(DocumentEmbedding.document_id == document.id)
            )
            db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))
            existing_pages = {
                page.page_number: page
                for page in db.scalars(
                    select(DocumentPage).where(DocumentPage.document_id == document.id)
                ).all()
            }
            extracted_numbers = {page.page_number for page in extraction.pages}
            for page_number, old_page in existing_pages.items():
                if page_number not in extracted_numbers:
                    if db.scalar(select(PageExtraction.id).where(PageExtraction.page_id == old_page.id)):
                        raise ExtractionError(
                            f"Trang {page_number} đã biến mất nhưng có dữ kiện trích xuất; cần xử lý thủ công."
                        )
                    db.delete(old_page)
            db.flush()
            if fts.ensure_fts(db):
                fts.delete_document_rows(db, document.id)

            for extracted in extraction.pages:
                page = existing_pages.get(extracted.page_number)
                if page is None:
                    page = DocumentPage(
                        project_id=project_id,
                        document_id=document.id,
                        page_number=extracted.page_number,
                    )
                    db.add(page)
                elif (
                    page.text != extracted.text
                    or page.tables_json != json.dumps(extracted.tables, ensure_ascii=False)
                    or old_render_hashes.get(extracted.page_number)
                    != (
                        storage.sha256_bytes(Path(extracted.rendered_path).read_bytes())
                        if extracted.rendered_path else None
                    )
                ):
                    # A changed source text needs a fresh engineer review.
                    db.execute(
                        update(PageExtraction)
                        .where(PageExtraction.page_id == page.id)
                        .values(status="proposed", verified_by=None, verified_at=None, verify_note=None)
                    )
                page.rendered_path = extracted.rendered_path
                page.text = extracted.text
                page.ocr_text = extracted.ocr_text
                page.tables_json = json.dumps(extracted.tables, ensure_ascii=False)
                page.ocr_confidence = extracted.ocr_confidence
                page.extraction_method = extracted.extraction_method
                page.drawing_number = extracted.drawing_number
                page.revision = extracted.revision
                page.width = extracted.width
                page.height = extracted.height
                page.needs_review = extracted.needs_review
                page.warnings_json = json.dumps(extracted.warnings, ensure_ascii=False)
                db.flush()

            document.page_count = extraction.page_count
            document.drawing_number = extraction.drawing_number
            document.revision = extraction.revision
            document.ocr_languages = extraction.ocr_languages
            document.warnings_json = json.dumps(extraction.warnings, ensure_ascii=False)
            document.status = "ocr_completed"
            if status_hook:
                status_hook("ocr_completed")
            db.commit()

            document.status = "indexing"
            if status_hook:
                status_hook("indexing")
            db.commit()

            fts_rows = []
            vectors_to_store: dict[tuple[str, int], list[tuple]] = {}
            page_by_number = {
                page.page_number: page
                for page in db.scalars(
                    select(DocumentPage).where(DocumentPage.document_id == document.id)
                ).all()
            }
            for extracted in extraction.pages:
                page = page_by_number[extracted.page_number]
                for piece in chunk_text_with_sections(extracted.text or ""):
                    chunk = DocumentChunk(
                        project_id=project_id,
                        document_id=document.id,
                        page_id=page.id,
                        page_number=page.page_number,
                        chunk_index=piece.index,
                        section=piece.section,
                        text=piece.text,
                        start_offset=piece.start_offset,
                        end_offset=piece.end_offset,
                        char_count=len(piece.text),
                    )
                    db.add(chunk)
                    db.flush()
                    vector, model = _safe_embedding(embedding_provider, piece.text)
                    db.add(
                        DocumentEmbedding(
                            project_id=project_id,
                            document_id=document.id,
                            page_id=page.id,
                            chunk_id=chunk.id,
                            model=model,
                            dim=len(vector),
                            vector_json=json.dumps(vector),
                        )
                    )
                    vectors_to_store.setdefault((model, len(vector)), []).append(
                        (chunk.id, document.id, page.id, vector)
                    )
                    fts_rows.append(
                        {
                            "chunk_id": chunk.id,
                            "project_id": project_id,
                            "document_id": document.id,
                            "page_number": page.page_number,
                            "text": piece.text,
                        }
                    )
            fts.insert_chunks(db, fts_rows)
            for (model, dim), rows in vectors_to_store.items():
                vector_store.upsert_vectors(db, project_id, model, dim, rows)

            document.page_stats_json = json.dumps(
                [
                    {
                        "page_number": page.page_number,
                        "method": page.extraction_method,
                        "chars": len(page.text or ""),
                        "ocr_confidence": page.ocr_confidence,
                        "needs_review": page.needs_review,
                        "tables": len(extracted_tables),
                    }
                    for page, extracted_tables in (
                        (page, json.loads(page.tables_json or "[]"))
                        for page in page_by_number.values()
                    )
                ],
                ensure_ascii=False,
            )
            document.status = "ready"
            document.ingest_finished_at = _now()
            document.error_message = None
            if status_hook:
                status_hook("ready")
            db.commit()
        except Exception as exc:  # noqa: BLE001 - persist a retryable failure
            db.rollback()
            failed = db.get(SourceDocument, document_id)
            if failed is not None:
                failed.status = "ready" if had_ready_index else "failed"
                failed.ingest_finished_at = _now()
                message = str(exc) if isinstance(exc, ExtractionError) else (
                    f"Không thể xử lý PDF ({type(exc).__name__})."
                )
                failed.error_message = message[:500]
                failed.warnings_json = json.dumps([message[:500]], ensure_ascii=False)
                if status_hook:
                    status_hook("failed")
                db.commit()
    finally:
        db.close()


def retry_ingest(db: Session, document: SourceDocument) -> None:
    if document.status in {"pending", "running", "ocr_completed", "indexing"}:
        reference = _utc(
            document.ingest_started_at or document.updated_at or document.created_at
        )
        stale_after = int(os.getenv("ENGINEERING_AI_INGEST_STALE_SECONDS", "900"))
        fresh = (
            reference is not None
            and (_now() - reference).total_seconds() < max(60, stale_after)
        )
        if fresh:
            raise DocumentConflict("Hồ sơ đang được xử lý.")
    document.status = "pending"
    document.error_message = None
    db.commit()


def perform_search(
    db: Session,
    project_id: str,
    query: str,
    top_k: int,
    embedding_provider: EmbeddingProvider,
    scope: str = "effective",
) -> SearchResponse:
    results = search_chunks(
        db, project_id, query, top_k, embedding_provider, scope=scope
    )
    citations = [citation_to_out(result) for result in results]
    return SearchResponse(
        query=query,
        citations=citations,
        results=citations,
        has_sources=bool(citations),
        message=None if citations else NO_SOURCE_ANSWER,
    )


def _format_report_date(value) -> str:
    return value.strftime("%d/%m/%Y")


def _load_linked_report_source(
    db: Session,
    project_id: str,
    report_id: Optional[str] = None,
    report_date=None,
) -> Tuple[ReportDraftSource, str]:
    try:
        from app.site.models import (  # type: ignore
            DailyReport,
            DailyWorkLog,
            ManpowerEntry,
            NextDayPlan,
        )
    except Exception as exc:  # pragma: no cover - integration without site module
        raise DocumentValidationError("Không đọc được module báo cáo ngày.") from exc

    query = select(DailyReport).where(DailyReport.project_id == project_id)
    if report_id is not None:
        query = query.where(DailyReport.id == report_id)
    else:
        query = query.where(DailyReport.report_date == report_date)
    report = db.scalar(query)
    if report is None:
        raise LookupError("Báo cáo ngày không thuộc công trình này.")
    if report.status not in {"draft", "reviewed"}:
        raise DocumentValidationError("Báo cáo nguồn phải ở trạng thái draft hoặc reviewed.")

    manpower_rows = db.scalars(
        select(ManpowerEntry)
        .where(ManpowerEntry.report_id == report.id)
        .order_by(ManpowerEntry.created_at, ManpowerEntry.id)
    ).all()
    work_rows = db.scalars(
        select(DailyWorkLog)
        .where(DailyWorkLog.report_id == report.id)
        .order_by(DailyWorkLog.created_at, DailyWorkLog.id)
    ).all()
    plan_rows = db.scalars(
        select(NextDayPlan)
        .where(NextDayPlan.report_id == report.id)
        .order_by(NextDayPlan.plan_date, NextDayPlan.created_at, NextDayPlan.id)
    ).all()

    source = ReportDraftSource(
        status=report.status,
        report_date=report.report_date,
        notes=report.notes,
        manpower=[
            ReportDraftManpower(
                entry_id=row.id,
                group_name=row.group_name,
                person_name=row.person_name,
                count=row.count,
                organization_id=row.organization_id,
            )
            for row in manpower_rows
        ],
        work_logs=[
            ReportDraftWorkLog(
                entry_id=row.id,
                work_item_id=row.work_item_id,
                location=row.location,
                component=row.component,
                quantity=row.quantity,
                unit=row.unit,
                start_time=row.start_time,
                end_time=row.end_time,
                status=row.status,
                notes=row.notes,
            )
            for row in work_rows
        ],
        next_day_plans=[
            ReportDraftPlan(
                entry_id=row.id,
                plan_date=row.plan_date,
                work_item_id=row.work_item_id,
                description=row.description,
                location=row.location,
                manpower=row.manpower,
                equipment=row.equipment,
                dependency=row.dependency,
            )
            for row in plan_rows
        ],
    )
    return source, report.id


def _report_summary_lines(source: ReportDraftSource) -> List[str]:
    lines = [
        f"Ngày báo cáo: {_format_report_date(source.report_date)}",
        f"Trạng thái nguồn: {source.status}",
    ]
    if source.notes and source.notes.strip():
        lines.append(f"Ghi chú đã ghi: {source.notes.strip()}")

    for entry in source.manpower:
        label = entry.group_name
        if entry.person_name:
            label += f" ({entry.person_name})"
        if entry.count is None:
            lines.append(f"Nhân lực - {label}: chưa ghi số lượng")
        else:
            lines.append(f"Nhân lực - {label}: {entry.count} người")

    for entry in source.work_logs:
        base = (
            f"Công việc - {entry.location or 'chưa ghi vị trí'} / "
            f"{entry.component or 'chưa ghi hạng mục'}"
        )
        if entry.quantity is not None:
            unit = f" {entry.unit}" if entry.unit else " (chưa ghi đơn vị)"
            base += f": {entry.quantity:g}{unit}"
        if entry.notes and entry.notes.strip():
            base += f" — {entry.notes.strip()}"
        lines.append(base)

    for plan in source.next_day_plans:
        base = f"Kế hoạch {_format_report_date(plan.plan_date)} - {plan.description or 'chưa ghi nội dung'}"
        if plan.manpower:
            base += f"; nhân lực: {plan.manpower}"
        if plan.equipment:
            base += f"; thiết bị: {plan.equipment}"
        lines.append(base)
    return lines


def _report_missing_fields(source: ReportDraftSource) -> List[MissingFieldOut]:
    missing: List[MissingFieldOut] = []
    if not source.manpower:
        missing.append(
            MissingFieldOut(
                section="report",
                field="manpower",
                message="Báo cáo chưa ghi nhân lực.",
            )
        )
    if not source.work_logs:
        missing.append(
            MissingFieldOut(
                section="report",
                field="work_logs",
                message="Báo cáo chưa ghi công việc trong ngày.",
            )
        )
    if not source.next_day_plans:
        missing.append(
            MissingFieldOut(
                section="report",
                field="next_day_plans",
                message="Báo cáo chưa ghi kế hoạch ngày tiếp theo.",
            )
        )

    for index, entry in enumerate(source.manpower):
        if entry.count is None:
            missing.append(
                MissingFieldOut(
                    section="manpower",
                    index=index,
                    field="count",
                    message="Chưa ghi số lượng; giữ null, không suy đoán.",
                )
            )
    for index, entry in enumerate(source.work_logs):
        if not entry.location:
            missing.append(
                MissingFieldOut(
                    section="work_logs",
                    index=index,
                    field="location",
                    message="Chưa ghi vị trí thi công.",
                )
            )
        if not entry.component:
            missing.append(
                MissingFieldOut(
                    section="work_logs",
                    index=index,
                    field="component",
                    message="Chưa ghi hạng mục/cấu kiện.",
                )
            )
        if not entry.work_item_id:
            missing.append(
                MissingFieldOut(
                    section="work_logs",
                    index=index,
                    field="work_item_id",
                    message="Chưa liên kết danh mục công việc.",
                )
            )
        if entry.quantity is None:
            missing.append(
                MissingFieldOut(
                    section="work_logs",
                    index=index,
                    field="quantity",
                    message="Chưa ghi khối lượng; không tự tạo giá trị.",
                )
            )
        elif not entry.unit:
            missing.append(
                MissingFieldOut(
                    section="work_logs",
                    index=index,
                    field="unit",
                    message="Đã ghi khối lượng nhưng chưa ghi đơn vị.",
                )
            )
    for index, plan in enumerate(source.next_day_plans):
        if not plan.description:
            missing.append(
                MissingFieldOut(
                    section="next_day_plans",
                    index=index,
                    field="description",
                    message="Chưa ghi nội dung kế hoạch.",
                )
            )
        if not plan.manpower:
            missing.append(
                MissingFieldOut(
                    section="next_day_plans",
                    index=index,
                    field="manpower",
                    message="Chưa ghi nhân lực dự kiến.",
                )
            )
        if not plan.equipment:
            missing.append(
                MissingFieldOut(
                    section="next_day_plans",
                    index=index,
                    field="equipment",
                    message="Chưa ghi thiết bị dự kiến.",
                )
            )
    return missing


def daily_report_draft(
    db: Session,
    project_id: str,
    request: DailyReportDraftRequest,
) -> DailyReportDraftResponse:
    source_report_id: Optional[str] = None
    if request.report is not None:
        source = request.report
        source_kind = "provided"
    else:
        source, source_report_id = _load_linked_report_source(
            db,
            project_id,
            report_id=request.report_id,
            report_date=request.report_date,
        )
        source_kind = "linked"

    draft = DailyReportDraftContent(
        report_date=source.report_date,
        status=source.status,
        notes=source.notes,
        manpower=source.manpower,
        work_logs=source.work_logs,
        next_day_plans=source.next_day_plans,
        summary_lines=_report_summary_lines(source),
    )
    return DailyReportDraftResponse(
        project_id=project_id,
        source=source_kind,
        source_report_id=source_report_id,
        source_status=source.status,
        draft=draft,
        missing_fields=_report_missing_fields(source),
        warnings=[DAILY_REPORT_DRAFT_WARNING],
        disclaimer=DAILY_REPORT_DRAFT_DISCLAIMER,
        no_invented_quantities=True,
    )


def _inspection_work_item(
    db: Session,
    project_id: str,
    request: InspectionChecklistRequest,
) -> InspectionWorkItemOut:
    if request.work_item is not None:
        return InspectionWorkItemOut(
            code=request.work_item.code,
            name=request.work_item.name,
            location=request.work_item.location,
            component=request.work_item.component,
        )
    try:
        from app.core.models import WorkItem  # type: ignore
    except Exception as exc:  # pragma: no cover - shared core unavailable
        raise DocumentValidationError("Không đọc được danh mục công việc.") from exc
    item = db.get(WorkItem, request.work_item_id)
    if item is None or item.project_id != project_id:
        raise LookupError("Công việc không thuộc công trình này.")
    return InspectionWorkItemOut(
        id=item.id,
        code=item.code,
        name=item.name,
        location=item.location,
        component=item.component,
    )


def inspection_checklist(
    db: Session,
    project_id: str,
    request: InspectionChecklistRequest,
    embedding_provider: EmbeddingProvider,
) -> InspectionChecklistResponse:
    work_item = _inspection_work_item(db, project_id, request)
    query_text = " ".join(
        value
        for value in (
            work_item.code,
            work_item.name,
            work_item.location,
            work_item.component,
            request.focus,
        )
        if value and str(value).strip()
    ).strip()
    query_tokens = tokenize(query_text)
    if not query_tokens:
        raise DocumentValidationError("Cần mã hoặc tên công việc để tìm hồ sơ liên quan.")

    results = search_chunks(
        db,
        project_id,
        query_text,
        request.top_k,
        embedding_provider,
    )
    suggestions: List[InspectionChecklistSuggestionOut] = []
    seen_pages = set()
    for result in results:
        key = (result.document_id, result.page_number)
        if key in seen_pages:
            continue
        criterion, prompt = choose_checklist_criterion(
            result.text, query_tokens, result.quote
        )
        if not criterion:
            continue
        seen_pages.add(key)
        low_ocr = (
            result.ocr_confidence is not None
            and result.ocr_confidence < LOW_OCR_THRESHOLD
        )
        suggestions.append(
            InspectionChecklistSuggestionOut(
                item=prompt,
                criterion=criterion,
                citation=citation_to_out(result, quote=criterion),
                status="unconfirmed",
                requires_engineer_review=True,
                auto_approved=False,
                relevance_score=result.score,
                warnings=[LOW_OCR_WARNING] if low_ocr else [],
            )
        )

    has_sources = bool(suggestions)
    return InspectionChecklistResponse(
        project_id=project_id,
        work_item=work_item,
        suggestions=suggestions,
        has_sources=has_sources,
        no_source=not has_sources,
        message=(
            None
            if has_sources
            else NO_SOURCE_ANSWER
        ),
        warnings=[UNVERIFIED_KB_NOTE],
        disclaimer=INSPECTION_CHECKLIST_DISCLAIMER,
    )


def cross_reference(
    db: Session,
    project_id: str,
    first_document_id: str,
    first_page_number: int,
    second_document_id: str,
    second_page_number: int,
    topic: Optional[str] = None,
) -> CrossReferenceResponse:

    first_document = get_document(db, project_id, first_document_id)
    second_document = get_document(db, project_id, second_document_id)
    if first_document is None or second_document is None:
        raise LookupError("Hồ sơ không thuộc công trình này.")
    first_page = get_page(db, project_id, first_document_id, first_page_number)
    second_page = get_page(db, project_id, second_document_id, second_page_number)
    if first_page is None or second_page is None:
        raise LookupError("Trang không thuộc công trình này.")
    if first_document.id == second_document.id and first_page.page_number == second_page.page_number:
        raise DocumentValidationError("Hai trang đối chiếu phải khác nhau.")
    if len((first_page.text or "").strip()) < 10 or len((second_page.text or "").strip()) < 10:
        raise DocumentValidationError(
            "Một trong hai trang không có đủ text để đối chiếu; cần kiểm tra bản vẽ gốc."
        )

    low_ocr = any(
        page.extraction_method == "ocr"
        and page.ocr_confidence is not None
        and page.ocr_confidence < LOW_OCR_THRESHOLD
        for page in (first_page, second_page)
    )
    warnings = [UNVERIFIED_KB_NOTE]
    if low_ocr:
        warnings.append(LOW_OCR_WARNING)

    quote_tokens = tokenize(topic or "")
    first_citation = _page_citation_out(
        project_id,
        first_document,
        first_page,
        quote_window(first_page.text or "", quote_tokens),
    )
    second_citation = _page_citation_out(
        project_id,
        second_document,
        second_page,
        quote_window(second_page.text or "", quote_tokens),
    )
    candidates = suggest_discrepancies(
        first_page.text or "",
        second_page.text or "",
        first_page.page_number,
        second_page.page_number,
        topic=topic,
    )
    suggestions: List[CrossReferenceSuggestionOut] = []
    for candidate in candidates:
        confidence = min(candidate.confidence, 0.40) if low_ocr else candidate.confidence
        suggestions.append(
            CrossReferenceSuggestionOut(
                topic=candidate.topic,
                first_citation=_page_citation_out(
                    project_id, first_document, first_page, candidate.first_quote
                ),
                second_citation=_page_citation_out(
                    project_id, second_document, second_page, candidate.second_quote
                ),
                observation=candidate.observation,
                confidence=round(confidence, 2),
                requires_engineer_review=True,
                warnings=[LOW_OCR_WARNING] if low_ocr else [],
            )
        )

    message = (
        f"Có {len(suggestions)} điểm nghi vấn cần kỹ sư đối chiếu; "
        "không kết luận hồ sơ hay thiết kế sai."
        if suggestions
        else CROSS_REFERENCE_NO_FINDING
    )
    return CrossReferenceResponse(
        project_id=project_id,
        status="needs_engineer_review",
        citations=[first_citation, second_citation],
        suggestions=suggestions,
        message=message,
        disclaimer=CROSS_REFERENCE_DISCLAIMER,
        warnings=warnings,
    )


def _vision_for_page(
    db: Session,
    page_id: Optional[str],
    page_number: int,
    provider,
) -> tuple[bool, Optional[str], List[str]]:
    """Send only the cited top page render to an explicitly configured provider."""

    if not page_id:
        return False, None, []
    if provider is None or getattr(provider, "name", "none") in {"none", "noop"}:
        return False, None, ["Vision chưa được cấu hình; không gửi ảnh."]
    page = db.get(DocumentPage, page_id)
    if page is None or not page.rendered_path:
        return False, None, ["Không có trang render cho citation đầu tiên; bỏ qua Vision."]
    path = Path(page.rendered_path)
    if not path.is_file():
        return False, None, ["Trang render đầu tiên không tồn tại; bỏ qua Vision."]
    try:
        data = path.read_bytes()
        if len(data) > storage.max_image_bytes():
            return False, None, ["Trang render đầu tiên vượt dung lượng Vision; bỏ qua."]
        suggestion = provider.suggest(data, "image/png")
    except Exception:  # noqa: BLE001 - vision is optional
        return False, None, ["Vision provider lỗi; bỏ qua phân tích ảnh."]
    parts = []
    if suggestion.suggested_category:
        parts.append(f"loại ảnh: {suggestion.suggested_category}")
    if suggestion.suggested_caption:
        parts.append(f"caption đề xuất: {suggestion.suggested_caption}")
    note = (
        f"Vision trang {page_number}: " + "; ".join(parts)
        if parts
        else f"Vision trang {page_number}: không có đề xuất."
    )
    warnings = list(suggestion.warnings)
    warnings.append(VISION_CHAT_DISCLAIMER)
    return True, note, warnings


def ask(
    db: Session,
    project_id: str,
    message: str,
    conversation_id: Optional[str],
    top_k: int,
    provider: AnswerProvider,
    embedding_provider: EmbeddingProvider,
    created_by: Optional[str],
    scope: str = "effective",
    vision_provider=None,
    use_vision: bool = False,
) -> ChatResponse:
    conversation: Optional[AIConversation] = None
    if conversation_id:
        conversation = db.scalar(
            select(AIConversation).where(
                AIConversation.project_id == project_id,
                AIConversation.id == conversation_id,
            )
        )
        if conversation is None:
            raise LookupError("Hội thoại không thuộc công trình này.")

    page_action = None
    warnings: List[str] = []
    navigation = answer_page_navigation(db, project_id, message, scope)
    if navigation is not None:
        answer = navigation.answer
        citations = navigation.citations
        warnings = list(navigation.warnings)
        no_source = navigation.no_source
        confidence = navigation.confidence
        page_action = navigation.page_action
    else:
        component_query = parse_component_query(message)
        if component_query is not None:
            answer, citations, component_warnings, no_source, confidence = (
                answer_component_query(
                    db, project_id, message, component_query, scope
                )
            )
            warnings.extend(component_warnings)
            # The component DB can still answer an exact code that has no
            # verified extraction; never fall through to generic page matching.
            if no_source and component_query.code:
                database = answer_database_question(db, project_id, message)
                if database is not None:
                    answer, citations, db_warnings, no_source, confidence = database
                    warnings.extend(db_warnings)
        else:
            warnings = [UNVERIFIED_KB_NOTE]
            answer, citations, structured_warnings, no_source, confidence = (
                answer_structured_question(
                    db, project_id, message, top_k, provider, scope
                )
            )
            warnings.extend(structured_warnings)

    # A sourced answer without a citation is not acceptable.
    if not no_source and not citations:
        answer = ProviderAnswer(text=NO_SOURCE_ANSWER)
        no_source = True
        confidence = 0.0
        warnings.append("Câu trả lời không có citation nên đã thay bằng câu từ chối chuẩn.")

    vision_used = False
    vision_note = None
    if use_vision and citations:
        first = next(
            (citation for citation in citations if citation.page_id and citation.page_number > 0),
            None,
        )
        if first is not None:
            vision_used, vision_note, vision_warnings = _vision_for_page(
                db, first.page_id, first.page_number, vision_provider
            )
            warnings.extend(vision_warnings)

    if conversation is None:
        conversation = AIConversation(
            project_id=project_id,
            title=(message.strip()[:120] or "Hỏi đáp hồ sơ"),
            messages_json="[]",
            created_by=created_by,
        )
        db.add(conversation)
        db.flush()
    messages = _json_list(conversation.messages_json)
    user_index = len(messages)
    assistant_index = user_index + 1
    messages.append(
        {
            "role": "user",
            "content": message,
            "citations": [],
            "warnings": [],
            "created_at": _now().isoformat(),
        }
    )
    messages.append(
        {
            "role": "assistant",
            "content": answer.text,
            "citations": [citation.model_dump(mode="json") for citation in citations],
            "warnings": warnings,
            "confidence": confidence,
            "no_source": no_source,
            "vision_used": vision_used,
            "vision_note": vision_note,
            "created_at": _now().isoformat(),
        }
    )
    conversation.messages_json = json.dumps(messages, ensure_ascii=False)
    for citation in citations:
        db.add(
            AICitation(
                project_id=project_id,
                conversation_id=conversation.id,
                message_index=assistant_index,
                chunk_id=citation.chunk_id,
                document_id=citation.document_id,
                page_id=citation.page_id or "",
                document_name=citation.document_name,
                version=citation.version,
                page_number=citation.page_number,
                drawing_number=citation.drawing_number,
                revision=citation.revision,
                quote=citation.quote,
                url=citation.url,
                ocr_confidence=citation.ocr_confidence,
            )
        )
    db.commit()
    return ChatResponse(
        conversation_id=conversation.id,
        message_index=assistant_index,
        answer=answer.text,
        citations=citations,
        confidence=confidence,
        no_source=no_source,
        warnings=warnings,
        vision_used=vision_used,
        vision_note=vision_note,
        page_action=page_action,
    )


def _conversation_messages(raw: str) -> List[ConversationMessageOut]:
    output: List[ConversationMessageOut] = []
    for item in _json_list(raw):
        if not isinstance(item, dict):
            continue
        citations = []
        for citation in item.get("citations") or []:
            try:
                citations.append(CitationOut(**citation))
            except Exception:  # noqa: BLE001 - tolerate old message payloads
                continue
        created_at = None
        if item.get("created_at"):
            try:
                created_at = datetime.fromisoformat(str(item["created_at"]))
            except ValueError:
                created_at = None
        output.append(
            ConversationMessageOut(
                role=str(item.get("role") or "assistant"),
                content=str(item.get("content") or ""),
                citations=citations,
                warnings=[str(value) for value in item.get("warnings") or []],
                created_at=created_at,
                vision_used=bool(item.get("vision_used") or False),
                vision_note=(
                    str(item["vision_note"]) if item.get("vision_note") is not None else None
                ),
            )
        )
    return output


def conversation_to_out(conversation: AIConversation) -> ConversationOut:
    return ConversationOut(
        id=conversation.id,
        project_id=conversation.project_id,
        title=conversation.title,
        messages=_conversation_messages(conversation.messages_json),
        created_at=_utc(conversation.created_at),
        updated_at=_utc(conversation.updated_at),
    )


def list_conversations(
    db: Session, project_id: str, q: Optional[str] = None
) -> List[AIConversation]:
    query = select(AIConversation).where(AIConversation.project_id == project_id)
    if q and q.strip():
        pattern = f"%{q.strip()}%"
        query = query.where(
            or_(
                AIConversation.title.ilike(pattern),
                AIConversation.messages_json.ilike(pattern),
            )
        )
    return list(
        db.scalars(
            query.order_by(AIConversation.updated_at.desc())
        ).all()
    )


def create_conversation(
    db: Session,
    project_id: str,
    title: Optional[str],
    created_by: Optional[str],
) -> AIConversation:
    conversation = AIConversation(
        project_id=project_id,
        title=((title or "").strip() or "Hội thoại mới")[:255],
        messages_json="[]",
        created_by=created_by,
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def rename_conversation(
    db: Session,
    project_id: str,
    conversation_id: str,
    title: str,
) -> AIConversation:
    conversation = get_conversation(db, project_id, conversation_id)
    if conversation is None:
        raise LookupError("Hội thoại không thuộc công trình này.")
    conversation.title = title.strip()[:255]
    db.commit()
    db.refresh(conversation)
    return conversation


def delete_conversation(db: Session, project_id: str, conversation_id: str) -> None:
    conversation = get_conversation(db, project_id, conversation_id)
    if conversation is None:
        raise LookupError("Hội thoại không thuộc công trình này.")
    db.execute(delete(AICitation).where(AICitation.conversation_id == conversation.id))
    db.delete(conversation)
    db.commit()


def get_conversation(
    db: Session, project_id: str, conversation_id: str
) -> Optional[AIConversation]:
    return db.scalar(
        select(AIConversation).where(
            AIConversation.project_id == project_id,
            AIConversation.id == conversation_id,
        )
    )


def suggest_photo(
    data: bytes,
    mime_type: Optional[str],
    provider: VisionProvider,
) -> PhotoSuggestionOut:
    if not data:
        raise DocumentValidationError("Ảnh rỗng.")
    if len(data) > storage.max_image_bytes():
        raise DocumentValidationError("Ảnh vượt quá dung lượng cho phép.")
    detected = storage.detect_image_mime(data)
    if detected is None:
        raise DocumentValidationError("Tệp tải lên không phải ảnh JPEG/PNG/WEBP hợp lệ.")
    effective_mime = detected or mime_type or "application/octet-stream"
    try:
        suggestion = provider.suggest(data, effective_mime)
    except Exception:  # noqa: BLE001 - never fail the upload experience
        suggestion = NoopVisionProvider().suggest(data, effective_mime)
        suggestion.warnings.append("Vision provider lỗi; cần kỹ sư tự phân loại ảnh.")
    return PhotoSuggestionOut(
        suggested_category=suggestion.suggested_category,
        suggested_caption=suggestion.suggested_caption,
        regions=[
            VisionRegionOut(
                left=region.left,
                top=region.top,
                width=region.width,
                height=region.height,
            )
            for region in suggestion.regions
        ],
        confidence=max(0.0, min(1.0, suggestion.confidence)),
        requires_confirmation=True,
        disclaimer=VISION_DISCLAIMER,
        warnings=list(suggestion.warnings),
    )
