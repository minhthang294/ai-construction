"""Pydantic schemas for Engineering AI API contracts.

Only metadata and text cross the API boundary.  Private file paths are never
returned; clients receive permission-checked URLs instead.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    type: str
    original_name: str
    document_key: str
    version: int
    is_current: bool
    is_effective: bool = True
    change_note: Optional[str] = None
    effective_at: Optional[datetime] = None
    effective_by: Optional[str] = None
    sha256: str
    status: str
    mime_type: Optional[str] = None
    size_bytes: int = 0
    page_count: int = 0
    drawing_number: Optional[str] = None
    revision: Optional[str] = None
    ocr_languages: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)
    error_message: Optional[str] = None
    created_by: Optional[str] = None
    ingest_started_at: Optional[datetime] = None
    ingest_finished_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    original_url: Optional[str] = None
    pages: List["PageSummaryOut"] = Field(default_factory=list)
    deduplicated: bool = False


class PageSummaryOut(BaseModel):
    id: str
    page_number: int
    extraction_method: str
    ocr_confidence: Optional[float] = None
    drawing_number: Optional[str] = None
    revision: Optional[str] = None
    needs_review: bool = False
    url: Optional[str] = None


class PageOut(BaseModel):
    id: str
    project_id: str
    document_id: str
    page_number: int
    extraction_method: str
    text: Optional[str] = None
    ocr_text: Optional[str] = None
    tables: List[dict] = Field(default_factory=list)
    ocr_confidence: Optional[float] = None
    drawing_number: Optional[str] = None
    revision: Optional[str] = None
    width: Optional[float] = None
    height: Optional[float] = None
    needs_review: bool = False
    warnings: List[str] = Field(default_factory=list)
    render_url: Optional[str] = None
    original_url: Optional[str] = None


class PageExtractionIn(BaseModel):
    model: str = Field(min_length=1, max_length=120)
    prompt_version: str = Field(min_length=1, max_length=40)
    mode: str = Field(min_length=1, max_length=20)
    extraction: dict[str, Any]
    confidence: Optional[float] = Field(default=None, ge=0, le=1)
    warnings: List[str] = Field(default_factory=list)


class PageExtractionOut(BaseModel):
    id: str
    project_id: str
    document_id: str
    page_id: str
    page_number: int
    page_sha256: Optional[str] = None
    model: str
    prompt_version: str
    mode: str
    status: str
    confidence: Optional[float] = None
    extraction: dict[str, Any]
    warnings: List[str] = Field(default_factory=list)
    created_by: Optional[str] = None
    verified_by: Optional[str] = None
    verified_at: Optional[datetime] = None
    verify_note: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class PageExtractionVerifyIn(BaseModel):
    status: Literal["verified", "rejected"]
    note: Optional[str] = Field(default=None, max_length=2000)


class CitationOut(BaseModel):
    """Citation contract from ``docs/API_CONTRACTS.md`` plus traceability ids."""

    document_id: str
    document_name: str
    version: int
    page_number: int
    drawing_number: Optional[str] = None
    revision: Optional[str] = None
    quote: str
    url: str
    ocr_confidence: Optional[float] = None
    chunk_id: Optional[str] = None
    page_id: Optional[str] = None
    extraction_method: Optional[str] = None
    score: Optional[float] = None
    section: Optional[str] = None
    # Structured-source traceability: page_extraction or database.  A database
    # citation carries the row id in record_id (document/page fields are blank).
    record_id: Optional[str] = None
    source: Optional[str] = None


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: Optional[str] = None
    top_k: int = Field(default=6, ge=1, le=20)
    scope: Literal["effective", "history"] = "effective"


class PageActionOut(BaseModel):
    document_id: str
    page_id: Optional[str] = None
    page_number: int
    label: str = ""


class ChatResponse(BaseModel):
    conversation_id: str
    message_index: int
    answer: str
    citations: List[CitationOut] = Field(default_factory=list)
    confidence: float = 0.0
    no_source: bool = False
    warnings: List[str] = Field(default_factory=list)
    page_action: Optional[PageActionOut] = None


class QuestionSuggestionOut(BaseModel):
    id: str
    label: str
    prompt: str
    mode: Literal["send", "fill"] = "send"
    badge: Optional[Literal["verified", "proposed", "navigation", "caution"]] = None


class ProgressParseRequest(BaseModel):
    text: str = Field(min_length=1, max_length=12000)
    default_date: Optional[date] = None
    batch_id: Optional[str] = None


class StageCandidateOut(BaseModel):
    stage_definition_id: str
    name: str
    component_type: str


class EarlierEventOut(BaseModel):
    event_id: str
    event_date: date
    status: str


class ProgressParseItemOut(BaseModel):
    raw: str
    code: str
    component_id: Optional[str] = None
    zone: Optional[str] = None
    segment: Optional[int] = None
    status_guess: Literal["COMPLETED", "IN_PROGRESS"] = "COMPLETED"
    stage_definition_id: Optional[str] = None
    stage_candidates: List[StageCandidateOut] = Field(default_factory=list)
    earlier_events: List[EarlierEventOut] = Field(default_factory=list)
    in_batch: bool = False


class ProgressParseLineOut(BaseModel):
    work_text: str
    stage_candidates: List[StageCandidateOut] = Field(default_factory=list)
    component_type: str
    items: List[ProgressParseItemOut] = Field(default_factory=list)


class ProgressParseQuestionOptionOut(BaseModel):
    label_vi: str
    value: str


class ProgressParseQuestionOut(BaseModel):
    id: str
    kind: str
    message_vi: str
    options: List[ProgressParseQuestionOptionOut] = Field(default_factory=list)
    codes: List[str] = Field(default_factory=list)
    apply: dict[str, Any] = Field(default_factory=dict)


class ProgressParseResponse(BaseModel):
    event_date: Optional[date] = None
    date_source: Optional[Literal["text", "default_date"]] = None
    batch_id: Optional[str] = None
    lines: List[ProgressParseLineOut] = Field(default_factory=list)
    questions: List[ProgressParseQuestionOut] = Field(default_factory=list)
    unknown_codes: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class ConversationMessageOut(BaseModel):
    role: str
    content: str
    citations: List[CitationOut] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    created_at: Optional[datetime] = None


class ConversationOut(BaseModel):
    id: str
    project_id: str
    title: Optional[str] = None
    messages: List[ConversationMessageOut] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ConversationCreateIn(BaseModel):
    title: Optional[str] = Field(default=None, max_length=255)


class ConversationUpdateIn(BaseModel):
    title: str = Field(min_length=1, max_length=255)


class EffectiveConfirmIn(BaseModel):
    change_note: str = Field(min_length=1, max_length=2000)


DocumentOut.model_rebuild()
