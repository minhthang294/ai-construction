"""Business logic for read-only documents, page extractions and AI chat."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional

from sqlalchemy import delete, or_, select, update
from sqlalchemy.orm import Session

from . import storage
from .component_chat import answer_component_query, parse_component_query
from .constants import NO_SOURCE_ANSWER, UNVERIFIED_KB_NOTE
from .database_chat import (
    answer_database_question,
    answer_design_parameter_question,
    answer_progress_question,
    answer_structured_question,
)
from .models import (
    AICitation,
    AIConversation,
    DocumentPage,
    PageExtraction,
    SourceDocument,
)
from .page_extraction import validate_extraction
from .page_navigation import answer_page_navigation
from .providers import (
    AnswerProvider,
    ProviderAnswer,
)
from .schemas import (
    ChatResponse,
    CitationOut,
    ConversationMessageOut,
    ConversationOut,
    DocumentOut,
    PageOut,
    PageSummaryOut,
    PageExtractionIn,
    PageExtractionOut,
)


class DocumentValidationError(ValueError):
    """Uploaded bytes or metadata are invalid."""


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


def ask(
    db: Session,
    project_id: str,
    message: str,
    conversation_id: Optional[str],
    top_k: int,
    provider: AnswerProvider,
    created_by: Optional[str],
    scope: str = "effective",
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
        design_parameter = answer_design_parameter_question(db, project_id, message)
        if design_parameter is not None:
            answer, citations, parameter_warnings, no_source, confidence = design_parameter
            warnings.extend(parameter_warnings)
        else:
            progress = answer_progress_question(db, project_id, message)
            if progress is not None:
                answer, citations, progress_warnings, no_source, confidence = progress
                warnings.extend(progress_warnings)
            else:
                component_query = parse_component_query(message)
                if component_query is not None:
                    answer, citations, component_warnings, no_source, confidence = (
                        answer_component_query(
                            db, project_id, message, component_query, scope
                        )
                    )
                    warnings.extend(component_warnings)
                    # The component DB can still answer the same question when the
                    # extraction facts do not; never fall through to generic pages.
                    if no_source:
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


