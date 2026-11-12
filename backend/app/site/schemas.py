"""Pydantic schemas for the Site Report API.

Contract notes:
- ``ManpowerEntry.count`` uses ``None`` for "unknown" and keeps integer ``0``
  as an explicit zero.  Negative counts are rejected.
- Naive datetimes coming from a mobile client are interpreted as
  Asia/Ho_Chi_Minh local time and stored as UTC, matching the shared time
  policy.
- ``DailyReport.status`` is limited to ``draft|reviewed``.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import List, Literal, Optional
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

LOCAL_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


class OrmBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UtcOutBase(OrmBase):
    """ORM output base that re-attaches UTC to SQLite's naive datetimes.

    SQLite does not preserve timezone information.  The application always
    stores UTC, so a naive value read from the database is UTC, not local time.
    """

    @field_validator("*", mode="before")
    @classmethod
    def _coerce_utc(cls, value):
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc)
        return value


def to_utc(value: Optional[datetime]) -> Optional[datetime]:
    """Normalise a datetime to UTC.

    Naive values are treated as Asia/Ho_Chi_Minh wall-clock time because the
    report date and mobile capture times are local.  Aware values are converted
    without guessing an offset.
    """

    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=LOCAL_TZ)
    return value.astimezone(timezone.utc)


class ManpowerValues(BaseModel):
    group_name: str = Field(..., min_length=1, max_length=120)
    person_name: Optional[str] = Field(default=None, max_length=120)
    # None means "unknown"; 0 is an explicit zero count and must survive.
    count: Optional[int] = Field(default=None, ge=0)
    organization_id: Optional[str] = None

    @field_validator("group_name")
    @classmethod
    def _strip_group_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("group_name must not be blank")
        return value

    @field_validator("count", mode="before")
    @classmethod
    def _reject_boolean_count(cls, value):
        if isinstance(value, bool):
            raise ValueError("count must be an integer, not a boolean")
        return value

    @field_validator("person_name")
    @classmethod
    def _strip_person_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @model_validator(mode="after")
    def _keep_zero(self) -> "ManpowerValues":
        # Explicitly preserve integer zero (do not coerce to None).
        if self.count is not None and not isinstance(self.count, int):
            raise ValueError("count must be integer or null")
        return self


class ManpowerEntryIn(ManpowerValues):
    pass


class ManpowerPresetIn(ManpowerValues):
    pass


class ManpowerTeamIn(BaseModel):
    """Structured daily manpower team.

    ``chi_huy_truong`` is a single named person, ``ky_thuat`` holds multiple
    named people, and the remaining roles are numeric counts.  The service
    stores these as ordinary ``ManpowerEntry`` rows so old reports and exports
    remain compatible.
    """

    chi_huy_truong: Optional[str] = Field(default=None, max_length=120)
    ky_thuat: List[str] = Field(default_factory=list, max_length=50)
    lai_xe: int = Field(default=0, ge=0)
    bao_ve: int = Field(default=0, ge=0)
    cong_nhan: int = Field(default=0, ge=0)

    @field_validator("chi_huy_truong")
    @classmethod
    def _strip_chief(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("ky_thuat")
    @classmethod
    def _clean_engineers(cls, value: List[str]) -> List[str]:
        cleaned: List[str] = []
        seen: set[str] = set()
        for item in value:
            name = " ".join(str(item).split())
            if not name:
                continue
            key = name.casefold()
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(name)
        return cleaned

    @field_validator("lai_xe", "bao_ve", "cong_nhan", mode="before")
    @classmethod
    def _reject_boolean_count(cls, value):
        if isinstance(value, bool):
            raise ValueError("manpower count must be an integer, not a boolean")
        return value


class ManpowerTeamOut(BaseModel):
    chi_huy_truong: Optional[str] = None
    ky_thuat: List[str] = Field(default_factory=list)
    lai_xe: int = 0
    bao_ve: int = 0
    cong_nhan: int = 0


class ManpowerEntryOut(UtcOutBase):
    id: str
    group_name: str
    person_name: Optional[str] = None
    count: Optional[int] = None
    organization_id: Optional[str] = None


class ManpowerPresetOut(ManpowerEntryOut):
    project_id: str
    created_at: datetime
    updated_at: datetime


class DailyWorkLogIn(BaseModel):
    work_item_id: Optional[str] = None
    # Name chosen from the catalog.  Kept separately because one name can map
    # to several catalog rows; the client clears work_item_id in that case.
    work_name: Optional[str] = Field(default=None, max_length=500)
    location: Optional[str] = Field(default=None, max_length=255)
    component: Optional[str] = Field(default=None, max_length=255)
    quantity: Optional[float] = None
    unit: Optional[str] = Field(default=None, max_length=60)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    status: Optional[str] = Field(default=None, max_length=60)
    notes: Optional[str] = None

    @field_validator("work_name")
    @classmethod
    def _strip_work_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("start_time", "end_time")
    @classmethod
    def _normalise_time(cls, value: Optional[datetime]) -> Optional[datetime]:
        return to_utc(value)

    @model_validator(mode="after")
    def _check_time_order(self) -> "DailyWorkLogIn":
        if self.start_time and self.end_time and self.end_time < self.start_time:
            raise ValueError("end_time must not be before start_time")
        return self


class DailyWorkLogOut(UtcOutBase):
    id: str
    work_item_id: Optional[str] = None
    work_name: Optional[str] = None
    location: Optional[str] = None
    component: Optional[str] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class NextDayPlanIn(BaseModel):
    plan_date: date
    work_item_id: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = Field(default=None, max_length=255)
    manpower: Optional[str] = Field(default=None, max_length=255)
    equipment: Optional[str] = Field(default=None, max_length=255)
    dependency: Optional[str] = None


class NextDayPlanOut(OrmBase):
    id: str
    plan_date: date
    work_item_id: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    manpower: Optional[str] = None
    equipment: Optional[str] = None
    dependency: Optional[str] = None


class SiteNotesIn(BaseModel):
    weather: Optional[str] = Field(default=None, max_length=4000)
    materials: Optional[str] = Field(default=None, max_length=4000)
    equipment: Optional[str] = Field(default=None, max_length=4000)
    incidents: Optional[str] = Field(default=None, max_length=4000)
    difficulties: Optional[str] = Field(default=None, max_length=4000)
    safety: Optional[str] = Field(default=None, max_length=4000)
    recommendations: Optional[str] = Field(default=None, max_length=4000)
    other: Optional[str] = Field(default=None, max_length=4000)

    @field_validator("*")
    @classmethod
    def _empty_to_none(cls, value):
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value


class SiteNotesOut(SiteNotesIn):
    pass


class DailyReportUpsertIn(BaseModel):
    status: Literal["draft", "reviewed"] = "draft"
    notes: Optional[str] = None
    site_notes: SiteNotesIn = Field(default_factory=SiteNotesIn)
    manpower: List[ManpowerEntryIn] = Field(default_factory=list)
    # Optional structured team.  When present, managed role rows in
    # ``manpower`` are replaced by this team while free-form rows are kept.
    manpower_team: Optional[ManpowerTeamIn] = None
    work_logs: List[DailyWorkLogIn] = Field(default_factory=list)
    next_day_plans: List[NextDayPlanIn] = Field(default_factory=list)


class DailyReportOut(UtcOutBase):
    id: str
    project_id: str
    report_date: date
    status: str
    notes: Optional[str] = None
    site_notes: SiteNotesOut = Field(default_factory=SiteNotesOut)
    manpower: List[ManpowerEntryOut] = Field(default_factory=list)
    # Derived from ``manpower`` so old reports need no migration.
    manpower_team: ManpowerTeamOut = Field(default_factory=ManpowerTeamOut)
    work_logs: List[DailyWorkLogOut] = Field(default_factory=list)
    next_day_plans: List[NextDayPlanOut] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class PhotoOut(UtcOutBase):
    id: str
    project_id: str
    report_id: Optional[str] = None
    sha256: str
    capture_time: Optional[datetime] = None
    upload_time: datetime
    gps_lat: Optional[float] = None
    gps_lon: Optional[float] = None
    # GPS is copied from EXIF when present and is never auto-confirmed.
    gps_source: Optional[str] = None
    gps_confirmed: bool = False
    device: Optional[str] = None
    category: Optional[str] = None
    location: Optional[str] = None
    component: Optional[str] = None
    stage: Optional[str] = None
    suggested_caption: Optional[str] = None
    confirmed_caption: Optional[str] = None
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None
    filename: Optional[str] = None
    client_upload_id: Optional[str] = None
    # Uploads are written synchronously; the echoed id lets offline clients
    # reconcile a retry with the original upload.
    sync_status: str = "synced"
    work_item_ids: List[str] = Field(default_factory=list)


class PhotoPatchIn(BaseModel):
    """Partial photo update.

    ``model_dump(exclude_unset=True)`` is used by the service so an explicit
    JSON ``null`` clears a field while an omitted field is left unchanged.
    """

    report_id: Optional[str] = None
    category: Optional[str] = Field(default=None, max_length=80)
    location: Optional[str] = Field(default=None, max_length=255)
    component: Optional[str] = Field(default=None, max_length=255)
    stage: Optional[str] = Field(default=None, max_length=80)
    suggested_caption: Optional[str] = None
    confirmed_caption: Optional[str] = None
    work_item_ids: Optional[List[str]] = None


class ExportRequestIn(BaseModel):
    format: Literal["zalo", "pdf", "docx", "zip"]


class ExportOut(UtcOutBase):
    id: str
    project_id: str
    report_id: Optional[str] = None
    report_date: Optional[date] = None
    format: str
    sha256: str
    snapshot_sha256: Optional[str] = None
    download_url: Optional[str] = None
    preview_text: Optional[str] = None
    # Exports are always downloaded/copied manually; Zalo is never sent.
    auto_send: bool = False
    generated_at: datetime


def parse_uuid(value: str) -> str:
    # Keep as string; validate shape lightly.
    try:
        UUID(value)
    except ValueError as exc:
        raise ValueError("invalid uuid") from exc
    return value
