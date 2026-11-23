"""FastAPI router for the Engineering AI module (chat-first, read-only sources).

Mount under ``/api/v1`` when integrating with the shared application.  Every
route checks project access before touching metadata, files or model providers.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from . import storage
from .dependencies import (
    current_user_id,
    get_answer_provider,
    get_current_user,
    get_db,
    project_access,
    project_editor_access,
)
from .schemas import (
    ChatRequest,
    ChatResponse,
    ConversationCreateIn,
    ConversationOut,
    ConversationUpdateIn,
    DocumentOut,
    EffectiveConfirmIn,
    PageOut,
    PageExtractionIn,
    PageExtractionOut,
    PageExtractionVerifyIn,
    ProgressParseRequest,
    ProgressParseResponse,
    QuestionSuggestionOut,
)
from .rate_limit import RateLimitExceeded, check_rate_limit
from .progress_parse import progress_parse
from .service import (
    DocumentValidationError,
    PageExtractionConflict,
    ask,
    confirm_effective,
    conversation_to_out,
    create_conversation,
    delete_conversation,
    document_to_out,
    get_conversation,
    get_document,
    get_page,
    get_page_extraction,
    list_conversations,
    list_documents,
    list_page_extractions,
    list_versions,
    page_to_out,
    page_extraction_to_out,
    rename_conversation,
    save_page_extraction,
    verify_page_extraction,
)
from .suggestions import question_suggestions

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
    """Only a document manager may mark a revision effective."""

    role = getattr(user, "role", None)
    if role is not None and role not in {"admin", "project_manager"}:
        raise HTTPException(
            status_code=403,
            detail="Chỉ quản lý hồ sơ được xác nhận phiên bản hiệu lực.",
        )


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


@router.post(
    "/projects/{project_id}/ai/progress-parse",
    response_model=ProgressParseResponse,
)
def progress_parse_route(
    project_id: str,
    payload: ProgressParseRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    _access=Depends(project_access),
):
    _guard_rate(project_id, user, "progress_parse")
    return progress_parse(
        db, project_id, payload.text, payload.default_date, payload.batch_id
    )


@router.get(
    "/projects/{project_id}/ai/question-suggestions",
    response_model=List[QuestionSuggestionOut],
)
def question_suggestions_route(
    project_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    _access=Depends(project_access),
):
    return question_suggestions(db, project_id)


@router.post("/projects/{project_id}/ai/chat", response_model=ChatResponse)
def chat_route(
    project_id: str,
    payload: ChatRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    _access=Depends(project_access),
    provider=Depends(get_answer_provider),
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
            current_user_id(user),
            scope=payload.scope,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


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
    status_code=status.HTTP_201_CREATED,
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
    status_code=status.HTTP_204_NO_CONTENT,
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
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
