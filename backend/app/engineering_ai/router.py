"""FastAPI router for the Engineering AI module.

Mount under ``/api/v1`` when integrating with the shared application.  Every
route checks project access before touching metadata, files or model providers.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, List, Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from . import storage
from .dependencies import (
    current_user_id,
    get_answer_provider,
    get_current_user,
    get_db,
    get_embedding_provider,
    get_max_pages,
    get_ocr_engine,
    get_ocr_languages,
    get_session_factory,
    get_vision_provider,
    project_access,
    project_editor_access,
)
from .schemas import (
    ChatRequest,
    ChatResponse,
    ConversationCreateIn,
    ConversationOut,
    ConversationUpdateIn,
    CrossReferenceRequest,
    CrossReferenceResponse,
    DailyReportDraftRequest,
    DailyReportDraftResponse,
    DocumentOut,
    EffectiveConfirmIn,
    InspectionChecklistRequest,
    InspectionChecklistResponse,
    PageOut,
    PageExtractionIn,
    PageExtractionOut,
    PageExtractionVerifyIn,
    PhotoSuggestionOut,
    SearchRequest,
    SearchResponse,
    VersionCompareOut,
)
from .rate_limit import RateLimitExceeded, check_rate_limit
from .service import (
    DocumentConflict,
    DocumentValidationError,
    PageExtractionConflict,
    ask,
    compare_versions,
    confirm_effective,
    conversation_to_out,
    create_conversation,
    create_document,
    cross_reference,
    daily_report_draft,
    delete_conversation,
    document_to_out,
    get_conversation,
    get_document,
    get_page,
    get_page_extraction,
    inspection_checklist,
    list_conversations,
    list_documents,
    list_page_extractions,
    list_versions,
    page_to_out,
    page_extraction_to_out,
    perform_search,
    rename_conversation,
    retry_ingest,
    run_ingest_job,
    save_page_extraction,
    suggest_photo,
    verify_page_extraction,
)

router = APIRouter(prefix="", tags=["engineering-ai"])


def _ensure_private_file(path: Path, project_id: str) -> Path:
    """Reject paths outside the project's private storage root."""

    try:
        resolved = path.resolve()
        root = storage.project_root(project_id).resolve()
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="File not found") from exc
    if not resolved.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return resolved


def _guard_rate(project_id: str, user, scope: str) -> None:
    try:
        check_rate_limit(project_id, current_user_id(user), scope)
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=429,
            detail="Too many requests; retry later.",
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc


def _require_effective_manager(user) -> None:
    """Only a document manager may mark a revision effective.

    Isolated module tests use a user object without a role; in the shared app
    the authenticated user always carries one.
    """

    role = getattr(user, "role", None)
    if role is not None and role not in {"admin", "project_manager"}:
        raise HTTPException(
            status_code=403,
            detail="Chỉ quản lý hồ sơ được xác nhận phiên bản hiệu lực.",
        )


async def _read_bounded(upload: UploadFile, limit: int, label: str) -> bytes:
    """Read at most ``limit + 1`` bytes before any validation/work.

    Reading the extra byte is what lets us distinguish exactly-at-limit from
    oversized without ever buffering an unbounded upload.
    """

    declared_size = getattr(upload, "size", None)
    if isinstance(declared_size, int) and declared_size > limit:
        raise HTTPException(
            status_code=413,
            detail=f"{label} vượt quá dung lượng cho phép.",
        )
    data = await upload.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(
            status_code=413,
            detail=f"{label} vượt quá dung lượng cho phép.",
        )
    return data


def _queue_ingest(
    background_tasks: BackgroundTasks,
    document_id: str,
    project_id: str,
    session_factory: Callable[[], Session],
    ocr_engine,
    embedding_provider,
    max_pages: int,
    languages: str,
) -> None:
    background_tasks.add_task(
        run_ingest_job,
        document_id,
        project_id,
        session_factory,
        ocr_engine,
        embedding_provider,
        max_pages,
        languages,
    )


@router.post(
    "/projects/{project_id}/documents",
    response_model=DocumentOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    project_id: str,
    response: Response,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    doc_type: Optional[str] = Form(None, alias="type"),
    change_note: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    _access=Depends(project_access),
    session_factory: Callable[[], Session] = Depends(get_session_factory),
    ocr_engine=Depends(get_ocr_engine),
    embedding_provider=Depends(get_embedding_provider),
    max_pages: int = Depends(get_max_pages),
    languages: str = Depends(get_ocr_languages),
):
    _guard_rate(project_id, user, "upload")
    data = await _read_bounded(file, storage.max_pdf_bytes(), "Tệp PDF")
    try:
        document, created = create_document(
            db,
            project_id,
            data,
            filename=file.filename,
            declared_mime=file.content_type,
            document_type=doc_type,
            created_by=current_user_id(user),
            change_note=change_note,
        )
    except DocumentValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except DocumentConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if created:
        _queue_ingest(
            background_tasks,
            document.id,
            project_id,
            session_factory,
            ocr_engine,
            embedding_provider,
            max_pages,
            languages,
        )
    else:
        response.status_code = status.HTTP_200_OK
    return document_to_out(db, document, include_pages=not created, deduplicated=not created)


@router.get("/projects/{project_id}/documents", response_model=List[DocumentOut])
def list_document_route(
    project_id: str,
    include_history: bool = True,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    _access=Depends(project_access),
):
    documents = list_documents(db, project_id, include_history=include_history)
    return [document_to_out(db, document) for document in documents]


@router.get("/projects/{project_id}/documents/{document_id}", response_model=DocumentOut)
def get_document_route(
    project_id: str,
    document_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    _access=Depends(project_access),
):
    document = get_document(db, project_id, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return document_to_out(db, document, include_pages=True)


@router.post(
    "/projects/{project_id}/documents/{document_id}/reingest",
    response_model=DocumentOut,
    status_code=status.HTTP_202_ACCEPTED,
)
def reingest_document_route(
    project_id: str,
    document_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    _access=Depends(project_access),
    session_factory: Callable[[], Session] = Depends(get_session_factory),
    ocr_engine=Depends(get_ocr_engine),
    embedding_provider=Depends(get_embedding_provider),
    max_pages: int = Depends(get_max_pages),
    languages: str = Depends(get_ocr_languages),
):
    _guard_rate(project_id, user, "ingest")
    document = get_document(db, project_id, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    try:
        retry_ingest(db, document)
    except DocumentConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    _queue_ingest(
        background_tasks,
        document.id,
        project_id,
        session_factory,
        ocr_engine,
        embedding_provider,
        max_pages,
        languages,
    )
    return document_to_out(db, document, include_pages=True)


@router.post(
    "/projects/{project_id}/documents/{document_id}/effective",
    response_model=DocumentOut,
)
def confirm_effective_route(
    project_id: str,
    document_id: str,
    payload: EffectiveConfirmIn,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    _access=Depends(project_access),
):
    _guard_rate(project_id, user, "effective")
    _require_effective_manager(user)
    try:
        document = confirm_effective(
            db,
            project_id,
            document_id,
            payload.change_note,
            current_user_id(user),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DocumentValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return document_to_out(db, document, include_pages=True)


@router.get(
    "/projects/{project_id}/documents/{document_id}/versions",
    response_model=List[DocumentOut],
)
def list_versions_route(
    project_id: str,
    document_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    _access=Depends(project_access),
):
    try:
        versions = list_versions(db, project_id, document_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return [document_to_out(db, document) for document in versions]


@router.get(
    "/projects/{project_id}/documents/{document_id}/compare/{other_id}",
    response_model=VersionCompareOut,
)
def compare_versions_route(
    project_id: str,
    document_id: str,
    other_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    _access=Depends(project_access),
):
    try:
        return compare_versions(db, project_id, document_id, other_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DocumentValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/projects/{project_id}/documents/{document_id}/original")
def download_original_route(
    project_id: str,
    document_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    _access=Depends(project_access),
):
    document = get_document(db, project_id, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    path = _ensure_private_file(Path(document.original_path), project_id)
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=document.original_name,
    )


@router.get(
    "/projects/{project_id}/documents/{document_id}/pages/{page_number}",
    response_model=PageOut,
)
def get_page_route(
    project_id: str,
    document_id: str,
    page_number: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    _access=Depends(project_access),
):
    if page_number < 1:
        raise HTTPException(status_code=404, detail="Page not found")
    page = get_page(db, project_id, document_id, page_number)
    if page is None:
        raise HTTPException(status_code=404, detail="Page not found")
    return page_to_out(page)


@router.get("/projects/{project_id}/documents/{document_id}/pages/{page_number}/render")
def get_page_render_route(
    project_id: str,
    document_id: str,
    page_number: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    _access=Depends(project_access),
):
    if page_number < 1:
        raise HTTPException(status_code=404, detail="Page render not found")
    page = get_page(db, project_id, document_id, page_number)
    if page is None:
        raise HTTPException(status_code=404, detail="Page render not found")
    candidate = (
        Path(page.rendered_path)
        if page.rendered_path
        else storage.page_render_path(project_id, document_id, page_number)
    )
    path = _ensure_private_file(candidate, project_id)
    return FileResponse(path, media_type="image/png", filename=path.name)


@router.post(
    "/projects/{project_id}/documents/{document_id}/pages/{page_number}/extractions",
    response_model=PageExtractionOut,
)
def save_page_extraction_route(
    project_id: str,
    document_id: str,
    page_number: int,
    payload: PageExtractionIn,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    _access=Depends(project_editor_access),
):
    _guard_rate(project_id, user, "page_extraction")
    try:
        return save_page_extraction(
            db,
            project_id,
            document_id,
            page_number,
            payload,
            current_user_id(user),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PageExtractionConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except DocumentValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get(
    "/projects/{project_id}/documents/{document_id}/extractions",
    response_model=List[PageExtractionOut],
)
def list_page_extractions_route(
    project_id: str,
    document_id: str,
    page: Optional[int] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    _access=Depends(project_access),
):
    if status is not None and status not in {"proposed", "verified", "rejected"}:
        raise HTTPException(status_code=422, detail="Invalid extraction status")
    try:
        return list_page_extractions(
            db, project_id, document_id, page_number=page, status=status
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/projects/{project_id}/page-extractions/{extraction_id}",
    response_model=PageExtractionOut,
)
def get_page_extraction_route(
    project_id: str,
    extraction_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    _access=Depends(project_access),
):
    row = get_page_extraction(db, project_id, extraction_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Page extraction not found")
    return page_extraction_to_out(row)


@router.patch(
    "/projects/{project_id}/page-extractions/{extraction_id}",
    response_model=PageExtractionOut,
)
def verify_page_extraction_route(
    project_id: str,
    extraction_id: str,
    payload: PageExtractionVerifyIn,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    _access=Depends(project_editor_access),
):
    _guard_rate(project_id, user, "page_extraction_verify")
    try:
        return verify_page_extraction(
            db,
            project_id,
            extraction_id,
            payload.status,
            payload.note,
            current_user_id(user),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DocumentValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/projects/{project_id}/ai/search", response_model=SearchResponse)
def search_route(
    project_id: str,
    payload: SearchRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    _access=Depends(project_access),
    embedding_provider=Depends(get_embedding_provider),
):
    _guard_rate(project_id, user, "search")
    if not payload.query.strip():
        raise HTTPException(status_code=422, detail="Query is empty")
    return perform_search(
        db,
        project_id,
        payload.query.strip(),
        payload.top_k,
        embedding_provider,
        scope=payload.scope,
    )


@router.post("/projects/{project_id}/ai/chat", response_model=ChatResponse)
def chat_route(
    project_id: str,
    payload: ChatRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    _access=Depends(project_access),
    provider=Depends(get_answer_provider),
    embedding_provider=Depends(get_embedding_provider),
    vision_provider=Depends(get_vision_provider),
):
    _guard_rate(project_id, user, "chat")
    if not payload.message.strip():
        raise HTTPException(status_code=422, detail="Message is empty")
    try:
        return ask(
            db,
            project_id,
            payload.message.strip(),
            payload.conversation_id,
            payload.top_k,
            provider,
            embedding_provider,
            current_user_id(user),
            scope=payload.scope,
            vision_provider=vision_provider,
            use_vision=payload.vision,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/projects/{project_id}/ai/cross-references",
    response_model=CrossReferenceResponse,
)
def cross_reference_route(
    project_id: str,
    payload: CrossReferenceRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    _access=Depends(project_access),
):
    _guard_rate(project_id, user, "crossref")
    try:
        return cross_reference(
            db,
            project_id,
            payload.first.document_id,
            payload.first.page_number,
            payload.second.document_id,
            payload.second.page_number,
            topic=payload.topic,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DocumentValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post(
    "/projects/{project_id}/ai/daily-report-drafts",
    response_model=DailyReportDraftResponse,
)
def daily_report_draft_route(
    project_id: str,
    payload: DailyReportDraftRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    _access=Depends(project_access),
):
    _guard_rate(project_id, user, "report_draft")
    try:
        return daily_report_draft(db, project_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DocumentValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post(
    "/projects/{project_id}/ai/inspection-checklists",
    response_model=InspectionChecklistResponse,
)
def inspection_checklist_route(
    project_id: str,
    payload: InspectionChecklistRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    _access=Depends(project_access),
    embedding_provider=Depends(get_embedding_provider),
):
    _guard_rate(project_id, user, "inspection")
    try:
        return inspection_checklist(db, project_id, payload, embedding_provider)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DocumentValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/projects/{project_id}/ai/conversations", response_model=List[ConversationOut])
def list_conversations_route(
    project_id: str,
    q: Optional[str] = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    _access=Depends(project_access),
):
    return [
        conversation_to_out(item)
        for item in list_conversations(db, project_id, q=q)
    ]


@router.post(
    "/projects/{project_id}/ai/conversations",
    response_model=ConversationOut,
    status_code=201,
)
def create_conversation_route(
    project_id: str,
    payload: ConversationCreateIn,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    _access=Depends(project_access),
):
    _guard_rate(project_id, user, "conversation")
    conversation = create_conversation(
        db, project_id, payload.title, current_user_id(user)
    )
    return conversation_to_out(conversation)


@router.patch(
    "/projects/{project_id}/ai/conversations/{conversation_id}",
    response_model=ConversationOut,
)
def rename_conversation_route(
    project_id: str,
    conversation_id: str,
    payload: ConversationUpdateIn,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    _access=Depends(project_access),
):
    try:
        conversation = rename_conversation(
            db, project_id, conversation_id, payload.title
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return conversation_to_out(conversation)


@router.delete(
    "/projects/{project_id}/ai/conversations/{conversation_id}",
    status_code=204,
)
def delete_conversation_route(
    project_id: str,
    conversation_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    _access=Depends(project_access),
):
    try:
        delete_conversation(db, project_id, conversation_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(status_code=204)


@router.get(
    "/projects/{project_id}/ai/conversations/{conversation_id}",
    response_model=ConversationOut,
)
def get_conversation_route(
    project_id: str,
    conversation_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    _access=Depends(project_access),
):
    conversation = get_conversation(db, project_id, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation_to_out(conversation)


@router.post("/projects/{project_id}/ai/photo-suggestions", response_model=PhotoSuggestionOut)
async def photo_suggestion_route(
    project_id: str,
    file: UploadFile = File(...),
    user=Depends(get_current_user),
    _access=Depends(project_access),
    vision_provider=Depends(get_vision_provider),
):
    _guard_rate(project_id, user, "vision")
    data = await _read_bounded(file, storage.max_image_bytes(), "Ảnh")
    try:
        return suggest_photo(data, file.content_type, vision_provider)
    except DocumentValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
