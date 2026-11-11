"""Pydantic v1 API contracts for the Acceptance module."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

RequestStatus = Literal["draft", "submitted"]
RecordStatus = Literal["draft", "confirmed"]
ResultState = Literal["approved", "conditional", "rejected"]
TriState = Literal["yes", "no", "unconfirmed"]
ParticipantRole = Literal["investor", "supervisor", "contractor", "requester", "other"]
ProfileRole = Literal["investor", "supervisor", "contractor", "requester", "other"]
FieldKind = Literal["construction", "electric", "mechanical"]
Urgency = Literal["normal", "urgent", "very_urgent"]
YesNo = Literal["yes", "no"]
NumberingKind = Literal["pyc", "bbnt"]
ResetPolicy = Literal["never", "yearly", "monthly"]


class OrmBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ParticipantIn(BaseModel):
    role: ParticipantRole
    person_name: str = Field(min_length=1, max_length=255)
    organization: Optional[str] = Field(default=None, max_length=500)
    position: Optional[str] = Field(default=None, max_length=255)
    sort_order: int = 0

    @field_validator("person_name")
    @classmethod
    def _person_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("person_name must not be blank")
        return value


class ParticipantOut(OrmBase):
    id: str
    role: str
    person_name: str
    organization: Optional[str] = None
    position: Optional[str] = None
    sort_order: int


class ChecklistIn(BaseModel):
    item: str = Field(min_length=1, max_length=500)
    state: TriState = "unconfirmed"
    evidence_refs: List[str] = Field(
        default_factory=list,
        description=(
            "Validated refs: bare/<photo:> SitePhoto id, "
            "<document:> Engineering AI document id, "
            "<page:> page id or <page:document_id:page_number>."
        ),
    )
    note: Optional[str] = None
    sort_order: int = 0

    @field_validator("item")
    @classmethod
    def _item_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("item must not be blank")
        return value


class ChecklistOut(OrmBase):
    id: str
    item: str
    state: str
    evidence_refs: List[str] = Field(default_factory=list)
    note: Optional[str] = None
    sort_order: int


class RequestIn(BaseModel):
    number: Optional[str] = Field(default=None, max_length=40)
    work_item_id: Optional[str] = None
    daily_report_id: Optional[str] = None
    requested_by_profile_id: Optional[str] = None
    supervisor_profile_id: Optional[str] = None
    investor_profile_id: Optional[str] = None
    status: RequestStatus = "draft"
    project_name: Optional[str] = Field(default=None, max_length=500)
    client: Optional[str] = Field(default=None, max_length=500)
    project_location: Optional[str] = Field(default=None, max_length=500)
    location: Optional[str] = Field(default=None, max_length=500)
    request_date: Optional[date] = None
    inspection_time: Optional[str] = Field(default=None, max_length=40)
    content: Optional[str] = None
    subject: Optional[str] = None
    field: Optional[FieldKind] = None
    urgency: Optional[Urgency] = None
    requested_by_name: Optional[str] = Field(default=None, max_length=255)
    supervisor_name: Optional[str] = Field(default=None, max_length=255)
    investor_name: Optional[str] = Field(default=None, max_length=255)
    contractor_org: Optional[str] = Field(default=None, max_length=500)
    supervisor_org: Optional[str] = Field(default=None, max_length=500)
    investor_org: Optional[str] = Field(default=None, max_length=500)
    notes: Optional[str] = None

    @field_validator("number")
    @classmethod
    def _number_optional_trim(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        return value or None


class RequestUpdate(BaseModel):
    number: Optional[str] = Field(default=None, min_length=1, max_length=40)
    work_item_id: Optional[str] = None
    daily_report_id: Optional[str] = None
    requested_by_profile_id: Optional[str] = None
    supervisor_profile_id: Optional[str] = None
    investor_profile_id: Optional[str] = None
    status: Optional[RequestStatus] = None
    project_name: Optional[str] = Field(default=None, max_length=500)
    client: Optional[str] = Field(default=None, max_length=500)
    project_location: Optional[str] = Field(default=None, max_length=500)
    location: Optional[str] = Field(default=None, max_length=500)
    request_date: Optional[date] = None
    inspection_time: Optional[str] = Field(default=None, max_length=40)
    content: Optional[str] = None
    subject: Optional[str] = None
    field: Optional[FieldKind] = None
    urgency: Optional[Urgency] = None
    requested_by_name: Optional[str] = Field(default=None, max_length=255)
    supervisor_name: Optional[str] = Field(default=None, max_length=255)
    investor_name: Optional[str] = Field(default=None, max_length=255)
    contractor_org: Optional[str] = Field(default=None, max_length=500)
    supervisor_org: Optional[str] = Field(default=None, max_length=500)
    investor_org: Optional[str] = Field(default=None, max_length=500)
    notes: Optional[str] = None


class RequestOut(OrmBase):
    id: str
    project_id: str
    work_item_id: Optional[str] = None
    daily_report_id: Optional[str] = None
    number: str
    status: str
    requested_at: datetime
    revision: int = 1
    requested_by_profile_id: Optional[str] = None
    supervisor_profile_id: Optional[str] = None
    investor_profile_id: Optional[str] = None
    project_name: Optional[str] = None
    client: Optional[str] = None
    project_location: Optional[str] = None
    location: Optional[str] = None
    request_date: Optional[date] = None
    inspection_time: Optional[str] = None
    content: Optional[str] = None
    subject: Optional[str] = None
    field: Optional[str] = None
    urgency: Optional[str] = None
    requested_by_name: Optional[str] = None
    supervisor_name: Optional[str] = None
    investor_name: Optional[str] = None
    contractor_org: Optional[str] = None
    supervisor_org: Optional[str] = None
    investor_org: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class RecordIn(BaseModel):
    request_id: str
    number: Optional[str] = Field(default=None, max_length=40)
    record_date: Optional[date] = None
    start_time: Optional[str] = Field(default=None, max_length=40)
    end_time: Optional[str] = Field(default=None, max_length=40)
    design_compliance: Optional[YesNo] = None
    technical_compliance: Optional[YesNo] = None
    other_notes: Optional[str] = None
    conclusion_note: Optional[str] = None
    participants: Optional[List[ParticipantIn]] = Field(default=None, max_length=6)
    checklist: Optional[List[ChecklistIn]] = Field(default=None, max_length=7)


class RecordUpdate(BaseModel):
    record_date: Optional[date] = None
    start_time: Optional[str] = Field(default=None, max_length=40)
    end_time: Optional[str] = Field(default=None, max_length=40)
    design_compliance: Optional[YesNo] = None
    technical_compliance: Optional[YesNo] = None
    other_notes: Optional[str] = None
    conclusion_note: Optional[str] = None
    participants: Optional[List[ParticipantIn]] = Field(default=None, max_length=6)
    checklist: Optional[List[ChecklistIn]] = Field(default=None, max_length=7)


class RecordOut(OrmBase):
    id: str
    project_id: str
    request_id: str
    number: Optional[str] = None
    status: str
    result: Optional[str] = None
    revision: int = 1
    supersedes_id: Optional[str] = None
    request_updated_at: Optional[datetime] = None
    stale: bool = False
    stale_warning: Optional[str] = None
    reused: Dict[str, Any] = Field(default_factory=dict)
    confirmer_id: Optional[str] = None
    confirmed_at: Optional[datetime] = None
    record_date: Optional[date] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    design_compliance: Optional[str] = None
    technical_compliance: Optional[str] = None
    other_notes: Optional[str] = None
    conclusion_note: Optional[str] = None
    participants: List[ParticipantOut] = Field(default_factory=list)
    checklist: List[ChecklistOut] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ConfirmIn(BaseModel):
    result: ResultState
    conclusion_note: Optional[str] = None


class ExportIn(BaseModel):
    kind: Literal["pyc", "bbnt"]
    format: Literal["xlsx", "pdf"] = "xlsx"


class ExportOut(BaseModel):
    id: str
    project_id: str
    kind: str
    source_id: str
    format: str
    sha256: str
    template_sha256: Optional[str] = None
    download_url: Optional[str] = None
    generated_at: datetime


class DailyReportLinkOut(OrmBase):
    """Read-only summary of a linked site daily report."""

    id: str
    project_id: str
    report_date: date
    status: str
    notes: Optional[str] = None


class NumberingIn(BaseModel):
    prefix: str = Field(default="PYC-", max_length=20)
    start_number: int = Field(default=1, ge=1)
    width: int = Field(default=3, ge=1, le=10)
    reset_policy: ResetPolicy = "never"
    date_format: str = Field(default="%Y", max_length=20)

    @field_validator("prefix")
    @classmethod
    def _prefix_trim(cls, value: str) -> str:
        return value.strip()


class NumberingOut(OrmBase):
    project_id: str
    kind: str
    prefix: str
    start_number: int
    next_number: int
    width: int
    reset_policy: str
    period_key: Optional[str] = None
    date_format: str
    updated_at: Optional[datetime] = None


class ParticipantProfileIn(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    organization: Optional[str] = Field(default=None, max_length=500)
    position: Optional[str] = Field(default=None, max_length=255)
    role: ProfileRole
    active: bool = True

    @field_validator("full_name")
    @classmethod
    def _full_name_trim(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("full_name must not be blank")
        return value


class ParticipantProfileUpdate(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    organization: Optional[str] = Field(default=None, max_length=500)
    position: Optional[str] = Field(default=None, max_length=255)
    role: Optional[ProfileRole] = None
    active: Optional[bool] = None


class ParticipantProfileOut(OrmBase):
    id: str
    project_id: str
    full_name: str
    organization: Optional[str] = None
    position: Optional[str] = None
    role: str
    active: bool
    created_at: datetime
    updated_at: datetime


class PreviewOut(BaseModel):
    kind: Literal["pyc", "bbnt"]
    source_id: str
    cells: Dict[str, Dict[str, Any]]
    warnings: List[str] = Field(default_factory=list)
    stale: bool = False


class AcceptanceHistoryItemOut(BaseModel):
    kind: Literal["pyc", "bbnt"]
    id: str
    number: str
    status: str
    revision: int = 1
    request_id: Optional[str] = None
    result: Optional[str] = None
    updated_at: datetime


class WorkItemAcceptanceHistoryOut(BaseModel):
    work_item_id: str
    items: List[AcceptanceHistoryItemOut] = Field(default_factory=list)
