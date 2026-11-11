"""Pydantic schemas for Engineering AI API contracts.

Only metadata and text cross the API boundary.  Private file paths are never
returned; clients receive permission-checked URLs instead.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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



class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=6, ge=1, le=20)
    scope: Literal["effective", "history"] = "effective"


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


class SearchResponse(BaseModel):
    query: str
    citations: List[CitationOut] = Field(default_factory=list)
    results: List[CitationOut] = Field(default_factory=list)
    has_sources: bool = False
    message: Optional[str] = None


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: Optional[str] = None
    top_k: int = Field(default=6, ge=1, le=20)
    scope: Literal["effective", "history"] = "effective"
    vision: bool = False


class ChatResponse(BaseModel):
    conversation_id: str
    message_index: int
    answer: str
    citations: List[CitationOut] = Field(default_factory=list)
    confidence: float = 0.0
    no_source: bool = False
    warnings: List[str] = Field(default_factory=list)
    vision_used: bool = False
    vision_note: Optional[str] = None


class ConversationMessageOut(BaseModel):
    role: str
    content: str
    citations: List[CitationOut] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    vision_used: bool = False
    vision_note: Optional[str] = None


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


class VersionSummaryOut(BaseModel):
    id: str
    version: int
    is_current: bool
    is_effective: bool
    status: str
    original_name: str
    sha256: str
    page_count: int
    chunk_count: int
    total_chars: int
    effective_at: Optional[datetime] = None
    effective_by: Optional[str] = None


class PageVersionChangeOut(BaseModel):
    page_number: int
    left_chars: int
    right_chars: int
    changed: bool


class VersionCompareOut(BaseModel):
    project_id: str
    same_document_key: bool
    left: VersionSummaryOut
    right: VersionSummaryOut
    page_count_delta: int
    chunk_count_delta: int
    total_chars_delta: int
    left_table_count: int
    right_table_count: int
    page_changes: List[PageVersionChangeOut] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    disclaimer: str


class VisionRegionOut(BaseModel):
    left: float = Field(ge=0, le=1)
    top: float = Field(ge=0, le=1)
    width: float = Field(ge=0, le=1)
    height: float = Field(ge=0, le=1)


class PhotoSuggestionOut(BaseModel):
    suggested_category: Optional[str] = None
    suggested_caption: Optional[str] = None
    regions: List[VisionRegionOut] = Field(default_factory=list)
    confidence: float = 0.0
    requires_confirmation: bool = True
    disclaimer: str
    warnings: List[str] = Field(default_factory=list)


class CrossReferencePageIn(BaseModel):
    document_id: str = Field(min_length=1, max_length=36)
    page_number: int = Field(ge=1)


class CrossReferenceRequest(BaseModel):
    first: CrossReferencePageIn
    second: CrossReferencePageIn
    topic: Optional[str] = Field(default=None, max_length=500)


class CrossReferenceSuggestionOut(BaseModel):
    topic: str
    first_citation: CitationOut
    second_citation: CitationOut
    observation: str
    confidence: float = 0.0
    requires_engineer_review: bool = True
    warnings: List[str] = Field(default_factory=list)


class CrossReferenceResponse(BaseModel):
    project_id: str
    status: str = "needs_engineer_review"
    citations: List[CitationOut] = Field(default_factory=list)
    suggestions: List[CrossReferenceSuggestionOut] = Field(default_factory=list)
    message: str
    disclaimer: str
    warnings: List[str] = Field(default_factory=list)


class ReportDraftManpower(BaseModel):
    entry_id: Optional[str] = None
    group_name: str = Field(min_length=1, max_length=120)
    person_name: Optional[str] = Field(default=None, max_length=120)
    count: Optional[int] = Field(default=None, ge=0)
    organization_id: Optional[str] = None

    @field_validator("count", mode="before")
    @classmethod
    def _reject_bool_count(cls, value):
        if isinstance(value, bool):
            raise ValueError("count must be an integer or null")
        return value


class ReportDraftWorkLog(BaseModel):
    entry_id: Optional[str] = None
    work_item_id: Optional[str] = None
    location: Optional[str] = Field(default=None, max_length=255)
    component: Optional[str] = Field(default=None, max_length=255)
    quantity: Optional[float] = None
    unit: Optional[str] = Field(default=None, max_length=60)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    status: Optional[str] = Field(default=None, max_length=60)
    notes: Optional[str] = None


class ReportDraftPlan(BaseModel):
    entry_id: Optional[str] = None
    plan_date: date
    work_item_id: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = Field(default=None, max_length=255)
    manpower: Optional[str] = Field(default=None, max_length=255)
    equipment: Optional[str] = Field(default=None, max_length=255)
    dependency: Optional[str] = None


class ReportDraftSource(BaseModel):
    status: Literal["draft", "reviewed"] = "draft"
    report_date: date
    notes: Optional[str] = None
    manpower: List[ReportDraftManpower] = Field(default_factory=list)
    work_logs: List[ReportDraftWorkLog] = Field(default_factory=list)
    next_day_plans: List[ReportDraftPlan] = Field(default_factory=list)


class DailyReportDraftRequest(BaseModel):
    report_id: Optional[str] = Field(default=None, max_length=36)
    report_date: Optional[date] = None
    report: Optional[ReportDraftSource] = None

    @model_validator(mode="after")
    def _exactly_one_source(self) -> "DailyReportDraftRequest":
        if sum(value is not None for value in (self.report_id, self.report_date, self.report)) != 1:
            raise ValueError("Provide exactly one of report_id, report_date or report")
        return self


class DailyReportDraftContent(BaseModel):
    report_date: date
    status: str
    notes: Optional[str] = None
    manpower: List[ReportDraftManpower] = Field(default_factory=list)
    work_logs: List[ReportDraftWorkLog] = Field(default_factory=list)
    next_day_plans: List[ReportDraftPlan] = Field(default_factory=list)
    summary_lines: List[str] = Field(default_factory=list)


class MissingFieldOut(BaseModel):
    section: str
    index: Optional[int] = None
    field: str
    message: str


class DailyReportDraftResponse(BaseModel):
    project_id: str
    source: Literal["linked", "provided"]
    source_report_id: Optional[str] = None
    source_status: str
    draft: DailyReportDraftContent
    missing_fields: List[MissingFieldOut] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    disclaimer: str
    no_invented_quantities: bool = True


class InspectionWorkItemIn(BaseModel):
    code: Optional[str] = Field(default=None, max_length=120)
    name: Optional[str] = Field(default=None, max_length=500)
    location: Optional[str] = Field(default=None, max_length=255)
    component: Optional[str] = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def _requires_code_or_name(self) -> "InspectionWorkItemIn":
        if not (self.code or self.name):
            raise ValueError("work_item requires code or name")
        return self


class InspectionChecklistRequest(BaseModel):
    work_item_id: Optional[str] = Field(default=None, max_length=36)
    work_item: Optional[InspectionWorkItemIn] = None
    focus: Optional[str] = Field(default=None, max_length=500)
    top_k: int = Field(default=8, ge=1, le=20)

    @model_validator(mode="after")
    def _exactly_one_work_item(self) -> "InspectionChecklistRequest":
        if sum(value is not None for value in (self.work_item_id, self.work_item)) != 1:
            raise ValueError("Provide exactly one of work_item_id or work_item")
        return self


class InspectionWorkItemOut(BaseModel):
    id: Optional[str] = None
    code: Optional[str] = None
    name: Optional[str] = None
    location: Optional[str] = None
    component: Optional[str] = None


class InspectionChecklistSuggestionOut(BaseModel):
    item: str
    criterion: str
    citation: CitationOut
    status: Literal["unconfirmed"] = "unconfirmed"
    requires_engineer_review: bool = True
    auto_approved: bool = False
    relevance_score: float = 0.0
    warnings: List[str] = Field(default_factory=list)


class InspectionChecklistResponse(BaseModel):
    project_id: str
    work_item: InspectionWorkItemOut
    suggestions: List[InspectionChecklistSuggestionOut] = Field(default_factory=list)
    has_sources: bool = False
    no_source: bool = False
    message: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)
    disclaimer: str


DocumentOut.model_rebuild()
