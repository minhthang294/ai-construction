"""Business logic for the Site Report module.

Safety rules implemented here:
- original photo bytes are written unchanged; the DB keeps only metadata;
- ``0`` and ``None`` manpower counts stay distinct end-to-end;
- only confirmed photos (a user-confirmed caption or a user-selected category)
  enter the export snapshot and ZIP evidence bundle;
- EXIF GPS is stored as unconfirmed metadata and labelled as such in exports;
- exports are produced only from a ``reviewed`` report and are never sent to
  Zalo automatically.
"""

from __future__ import annotations

import hashlib
import io
import json
import mimetypes
import os
import re
import uuid
import zipfile
from datetime import date, datetime, time as dt_time, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import (
    DailyReport,
    DailyWorkLog,
    GeneratedDocument,
    ManpowerEntry,
    ManpowerPreset,
    NextDayPlan,
    PhotoWorkItemLink,
    SitePhoto,
)
from .schemas import (
    DailyReportUpsertIn,
    LOCAL_TZ,
    ManpowerPresetIn,
    PhotoPatchIn,
)

STORAGE_ROOT = Path(
    os.getenv("SITE_REPORT_STORAGE", "/tmp/opencode/site-report-storage")
).expanduser()
MAX_PHOTO_BYTES = int(os.getenv("SITE_PHOTO_MAX_BYTES", str(50 * 1024 * 1024)))
GENERIC_REPORT_TITLE = "BÁO CÁO NGÀY"
WORK_STATUS_LABELS = {
    "done": "Hoàn thành",
    "in_progress": "Đang làm",
    "planned": "Kế hoạch",
    "blocked": "Vướng mắc",
}
SITE_NOTE_FIELDS = (
    "weather",
    "materials",
    "equipment",
    "incidents",
    "difficulties",
    "safety",
    "recommendations",
    "other",
)
SITE_NOTE_LABELS = {
    "weather": "Thời tiết",
    "materials": "Vật tư",
    "equipment": "Thiết bị",
    "incidents": "Sự cố",
    "difficulties": "Khó khăn",
    "safety": "An toàn",
    "recommendations": "Kiến nghị",
    "other": "Khác",
}
# Raster-only allow-list: SVG/XML can execute script when served inline.
SAFE_IMAGE_MIMES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/avif",
    "image/gif",
    "image/bmp",
    "image/tiff",
    "image/heic",
    "image/heif",
}
PDF_FONT_CANDIDATES = (
    os.getenv("SITE_REPORT_PDF_FONT", ""),
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/noto/NotoSans-Regular.ttf",
)


class SiteError(Exception):
    """Base class for business errors mapped to HTTP by the router."""


class ProjectResourceNotFound(SiteError):
    """A referenced resource does not exist inside the requested project."""


class PhotoUploadConflict(SiteError):
    """The same client upload id was reused with different bytes."""


class EmptyPhoto(SiteError):
    """An uploaded photo has no bytes."""


class PhotoTooLarge(SiteError):
    """An uploaded photo exceeds the configured size limit."""


class UnsupportedPhotoType(SiteError):
    """Only image uploads are accepted; the original is never served as HTML."""


class ReportNotReviewed(SiteError):
    """Exports require a reviewed report snapshot."""


def ensure_storage() -> Path:
    STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
    return STORAGE_ROOT


def _project_dir(project_id: str) -> Path:
    path = ensure_storage() / "projects" / project_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _within_storage(path: Path) -> bool:
    try:
        path.resolve().relative_to(STORAGE_ROOT.resolve())
        return True
    except ValueError:
        return False


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_utc(value: Optional[datetime]) -> Optional[str]:
    """Serialise a DB datetime as ISO-8601 UTC (SQLite drops the offset)."""

    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def resolve_project_title(project: Any) -> str:
    """Resolve the configured report title, falling back to the project name.

    ``Project.report_title`` is owned by shared core.  It may not exist in an
    older schema yet, so it is read with ``getattr``; the fallback keeps exports
    working without inventing a title.
    """

    if project is not None:
        title = getattr(project, "report_title", None)
        if isinstance(title, str) and title.strip():
            return title.strip()
        name = getattr(project, "name", None)
        if isinstance(name, str) and name.strip():
            return name.strip()
    return GENERIC_REPORT_TITLE


def project_report_title(db: Session, project_id: str) -> str:
    """Load the project's configured title from the shared Project table."""

    try:
        from app.core.models import Project  # type: ignore
    except Exception:  # pragma: no cover - isolated run
        return GENERIC_REPORT_TITLE
    try:
        project = db.get(Project, project_id)
    except Exception:  # pragma: no cover - isolated run without core tables
        return GENERIC_REPORT_TITLE
    return resolve_project_title(project)


def format_report_date(value: date) -> str:
    """Human date used by the Zalo/PDF/DOCX report (DD/MM/YYYY)."""

    return value.strftime("%d/%m/%Y")


def work_item_names(db: Session, project_id: str, ids: Iterable[Optional[str]]) -> Dict[str, str]:
    """Resolve work-item names strictly inside ``project_id``.

    Missing/deleted work items are omitted instead of producing a guessed name.
    """

    unique = {value for value in ids if value}
    if not unique:
        return {}
    try:
        from app.core.models import WorkItem  # type: ignore
    except Exception:  # pragma: no cover - isolated run
        return {}
    try:
        rows = db.execute(
            select(WorkItem.id, WorkItem.name).where(
                WorkItem.project_id == project_id, WorkItem.id.in_(unique)
            )
        ).all()
    except Exception:  # pragma: no cover - isolated run without core tables
        return {}
    return {
        work_item_id: name.strip()
        for work_item_id, name in rows
        if isinstance(name, str) and name.strip()
    }


def _join_distinct(parts: Iterable[Optional[str]], separator: str = " - ") -> str:
    seen: set[str] = set()
    values: List[str] = []
    for part in parts:
        if part is None:
            continue
        text = str(part).strip()
        key = text.casefold()
        if not text or any(key in existing for existing in seen):
            continue
        # Drop an earlier shorter value contained in this more specific one.
        values = [value for value in values if value.casefold() not in key]
        seen = {value.casefold() for value in values}
        seen.add(key)
        values.append(text)
    return separator.join(values)


def empty_site_notes() -> Dict[str, Optional[str]]:
    return {field: None for field in SITE_NOTE_FIELDS}


def parse_site_notes(raw: Optional[str]) -> Dict[str, Optional[str]]:
    """Parse the stored JSON text into the eight optional note fields."""

    notes = empty_site_notes()
    if not raw:
        return notes
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return notes
    if not isinstance(data, dict):
        return notes
    for field in SITE_NOTE_FIELDS:
        value = data.get(field)
        if isinstance(value, str):
            value = value.strip()
            notes[field] = value or None
        else:
            notes[field] = None
    return notes


def dump_site_notes(payload: Any) -> Optional[str]:
    """Serialise only when at least one structured note is present."""

    if payload is None:
        return None
    data = payload.model_dump() if hasattr(payload, "model_dump") else dict(payload)
    cleaned = {
        field: (str(data.get(field)).strip() or None)
        if data.get(field) is not None
        else None
        for field in SITE_NOTE_FIELDS
    }
    if not any(cleaned.values()):
        return None
    return json.dumps(cleaned, ensure_ascii=False, sort_keys=True)


def site_notes_from_report(report: DailyReport) -> Dict[str, Optional[str]]:
    return parse_site_notes(report.site_notes_json)


# ---------------------------------------------------------------------------
# Project-scoped reference validation
# ---------------------------------------------------------------------------


def _work_item_ids_exist(db: Session, project_id: str, ids: Iterable[Optional[str]]) -> set[str]:
    """Return the subset of ``ids`` that belong to ``project_id``.

    ``work_items`` is a shared core table.  If the shared model is unavailable
    (isolated module run) the ids cannot be checked and are accepted, but in a
    real deployment the table exists and every foreign reference is validated.
    """

    unique = {value for value in ids if value}
    if not unique:
        return set()
    try:
        from app.core.models import WorkItem  # type: ignore
    except Exception:  # pragma: no cover - isolated run
        return unique
    rows = db.execute(
        select(WorkItem.id).where(
            WorkItem.project_id == project_id, WorkItem.id.in_(unique)
        )
    ).scalars()
    return set(rows.all())


def validate_work_item_refs(
    db: Session, project_id: str, ids: Iterable[Optional[str]]
) -> None:
    unique = {value for value in ids if value}
    existing = _work_item_ids_exist(db, project_id, unique)
    if unique - existing:
        raise ProjectResourceNotFound("Work item not found in project")


def _organization_ids_exist(
    db: Session, project_id: str, ids: Iterable[Optional[str]]
) -> set[str]:
    unique = {value for value in ids if value}
    if not unique:
        return set()
    try:
        from app.core.models import Organization  # type: ignore
    except Exception:  # pragma: no cover - isolated run
        return unique
    rows = db.execute(
        select(Organization.id).where(
            Organization.project_id == project_id, Organization.id.in_(unique)
        )
    ).scalars()
    return set(rows.all())


def validate_organization_refs(
    db: Session, project_id: str, ids: Iterable[Optional[str]]
) -> None:
    unique = {value for value in ids if value}
    existing = _organization_ids_exist(db, project_id, unique)
    if unique - existing:
        raise ProjectResourceNotFound("Organization not found in project")


def get_owned_report(db: Session, project_id: str, report_id: str) -> DailyReport:
    report = db.execute(
        select(DailyReport).where(
            DailyReport.project_id == project_id, DailyReport.id == report_id
        )
    ).scalar_one_or_none()
    if report is None:
        raise ProjectResourceNotFound("Daily report not found in project")
    return report


def _validate_report_id(db: Session, project_id: str, report_id: Optional[str]) -> None:
    if report_id:
        get_owned_report(db, project_id, report_id)


# ---------------------------------------------------------------------------
# Daily report
# ---------------------------------------------------------------------------


def _report_query(db: Session, project_id: str, report_date: date) -> Optional[DailyReport]:
    stmt = select(DailyReport).where(
        DailyReport.project_id == project_id, DailyReport.report_date == report_date
    )
    return db.execute(stmt).scalar_one_or_none()


def get_report(db: Session, project_id: str, report_date: date) -> Optional[DailyReport]:
    return _report_query(db, project_id, report_date)


def upsert_report(
    db: Session,
    project_id: str,
    report_date: date,
    payload: DailyReportUpsertIn,
    actor_id: Optional[str] = None,
) -> DailyReport:
    """Idempotently replace one report's child collections.

    Validation happens before any delete so an invalid work-item reference
    cannot destroy the previous draft.
    """

    validate_work_item_refs(
        db,
        project_id,
        [
            *(item.work_item_id for item in payload.work_logs),
            *(item.work_item_id for item in payload.next_day_plans),
        ],
    )
    validate_organization_refs(
        db, project_id, [item.organization_id for item in payload.manpower]
    )

    report = _report_query(db, project_id, report_date)
    if report is None:
        report = DailyReport(project_id=project_id, report_date=report_date)
        db.add(report)
        db.flush()

    previous_status = report.status
    report.status = payload.status
    report.notes = payload.notes
    report.site_notes_json = dump_site_notes(payload.site_notes)
    report.updated_at = _now()

    # Idempotent replacement of child collections keeps zero/null counts intact.
    for entry in list(report.manpower_entries):
        db.delete(entry)
    for entry in list(report.work_logs):
        db.delete(entry)
    for entry in list(report.next_day_plans):
        db.delete(entry)
    db.flush()

    for item in payload.manpower:
        db.add(
            ManpowerEntry(
                report_id=report.id,
                project_id=project_id,
                group_name=item.group_name,
                person_name=item.person_name,
                count=item.count,  # preserves 0 vs None
                organization_id=item.organization_id,
            )
        )
    for item in payload.work_logs:
        db.add(
            DailyWorkLog(
                report_id=report.id,
                project_id=project_id,
                work_item_id=item.work_item_id,
                location=item.location,
                component=item.component,
                quantity=item.quantity,
                unit=item.unit,
                start_time=item.start_time,
                end_time=item.end_time,
                status=item.status,
                notes=item.notes,
            )
        )
    for item in payload.next_day_plans:
        db.add(
            NextDayPlan(
                report_id=report.id,
                project_id=project_id,
                plan_date=item.plan_date,
                work_item_id=item.work_item_id,
                description=item.description,
                location=item.location,
                manpower=item.manpower,
                equipment=item.equipment,
                dependency=item.dependency,
            )
        )

    _audit(
        db,
        project_id=project_id,
        actor_id=actor_id,
        action="upsert_daily_report",
        entity="DailyReport",
        entity_id=report.id,
        detail=json.dumps(
            {
                "report_date": report_date.isoformat(),
                "status": report.status,
                "previous_status": previous_status,
            },
            ensure_ascii=False,
        ),
    )
    db.commit()
    db.refresh(report)
    return report


# ---------------------------------------------------------------------------
# Manpower presets
# ---------------------------------------------------------------------------


def list_manpower_presets(db: Session, project_id: str) -> List[ManpowerPreset]:
    stmt = (
        select(ManpowerPreset)
        .where(ManpowerPreset.project_id == project_id)
        .order_by(
            ManpowerPreset.group_name,
            ManpowerPreset.person_name,
            ManpowerPreset.id,
        )
    )
    return list(db.execute(stmt).scalars().all())


def get_manpower_preset(
    db: Session, project_id: str, preset_id: str
) -> Optional[ManpowerPreset]:
    return db.execute(
        select(ManpowerPreset).where(
            ManpowerPreset.project_id == project_id,
            ManpowerPreset.id == preset_id,
        )
    ).scalar_one_or_none()


def create_manpower_preset(
    db: Session,
    project_id: str,
    payload: ManpowerPresetIn,
    actor_id: Optional[str] = None,
) -> ManpowerPreset:
    validate_organization_refs(db, project_id, [payload.organization_id])
    preset = ManpowerPreset(
        project_id=project_id,
        group_name=payload.group_name,
        person_name=payload.person_name,
        count=payload.count,  # preserves 0 vs None
        organization_id=payload.organization_id,
    )
    db.add(preset)
    db.flush()
    _audit(
        db,
        project_id=project_id,
        actor_id=actor_id,
        action="create_manpower_preset",
        entity="ManpowerPreset",
        entity_id=preset.id,
        detail=json.dumps(
            {
                "group_name": preset.group_name,
                "count": preset.count,
                "organization_id": preset.organization_id,
            },
            ensure_ascii=False,
        ),
    )
    db.commit()
    db.refresh(preset)
    return preset


def update_manpower_preset(
    db: Session,
    project_id: str,
    preset_id: str,
    payload: ManpowerPresetIn,
    actor_id: Optional[str] = None,
) -> Optional[ManpowerPreset]:
    preset = get_manpower_preset(db, project_id, preset_id)
    if preset is None:
        return None
    validate_organization_refs(db, project_id, [payload.organization_id])
    preset.group_name = payload.group_name
    preset.person_name = payload.person_name
    preset.count = payload.count  # preserves 0 vs None
    preset.organization_id = payload.organization_id
    preset.updated_at = _now()
    _audit(
        db,
        project_id=project_id,
        actor_id=actor_id,
        action="update_manpower_preset",
        entity="ManpowerPreset",
        entity_id=preset.id,
        detail=json.dumps(
            {
                "group_name": preset.group_name,
                "count": preset.count,
                "organization_id": preset.organization_id,
            },
            ensure_ascii=False,
        ),
    )
    db.commit()
    db.refresh(preset)
    return preset


def delete_manpower_preset(
    db: Session,
    project_id: str,
    preset_id: str,
    actor_id: Optional[str] = None,
) -> bool:
    preset = get_manpower_preset(db, project_id, preset_id)
    if preset is None:
        return False
    _audit(
        db,
        project_id=project_id,
        actor_id=actor_id,
        action="delete_manpower_preset",
        entity="ManpowerPreset",
        entity_id=preset.id,
        detail=json.dumps({"group_name": preset.group_name}, ensure_ascii=False),
    )
    db.delete(preset)
    db.commit()
    return True


# ---------------------------------------------------------------------------
# Photos
# ---------------------------------------------------------------------------


def _sanitize_filename(filename: Optional[str]) -> str:
    base = os.path.basename(filename or "photo")
    base = re.sub(r"[\x00-\x1f\\/:*?\"<>|]+", "_", base).strip(" .")
    return (base or "photo")[:180]


def _clean_optional(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _safe_image_mime(mime_type: Optional[str], filename: Optional[str]) -> str:
    """Resolve a raster image MIME type, rejecting active content.

    SVG and other markup-capable types are rejected because the original route
    serves photos inline.  The uploaded declaration is trusted only when it is
    an allow-listed raster type; a generic ``application/octet-stream`` is
    accepted only when the filename/extension resolves to one.
    """

    declared = (mime_type or "").split(";", 1)[0].strip().lower()
    guessed = (mimetypes.guess_type(filename or "")[0] or "").lower()
    for candidate in (declared, guessed):
        if candidate in ("image/jpg", "image/pjpeg"):
            candidate = "image/jpeg"
        if candidate in SAFE_IMAGE_MIMES:
            return candidate
    raise UnsupportedPhotoType("Only raster image uploads are accepted")


def served_image_mime(mime_type: Optional[str]) -> Optional[str]:
    """Return the stored MIME only when it is safe to serve inline."""

    declared = (mime_type or "").split(";", 1)[0].strip().lower()
    if declared in ("image/jpg", "image/pjpeg"):
        return "image/jpeg"
    return declared if declared in SAFE_IMAGE_MIMES else None


def _exif_datetime_to_utc(raw: Any) -> Optional[datetime]:
    """Convert EXIF ``YYYY:MM:DD HH:MM:SS`` local time to UTC.

    EXIF datetimes have no offset.  The application treats them as
    Asia/Ho_Chi_Minh wall-clock time rather than pretending they are UTC.
    """

    if not raw:
        return None
    text = str(raw).strip().replace("\x00", "")
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            parsed = datetime.strptime(text, fmt)
        except ValueError:
            continue
        return parsed.replace(tzinfo=LOCAL_TZ).astimezone(timezone.utc)
    return None


def _dms_to_deg(values: Any, ref: Any) -> Optional[float]:
    try:
        degrees, minutes, seconds = values
        result = float(degrees) + float(minutes) / 60.0 + float(seconds) / 3600.0
        if str(ref).upper() in ("S", "W"):
            result = -result
        return result
    except Exception:
        return None


def _exif_metadata(data: bytes) -> Tuple[Optional[datetime], Optional[float], Optional[float], Optional[str]]:
    capture_time = None
    lat = None
    lon = None
    device = None
    try:
        from PIL import Image, ExifTags  # noqa: F401  (ExifTags kept for clarity)

        image = Image.open(io.BytesIO(data))
        exif = image.getexif() if hasattr(image, "getexif") else None
        if exif:
            make = exif.get(271)
            model = exif.get(272)
            parts = [str(part).strip() for part in (make, model) if part]
            if parts:
                device = " ".join(parts)
            capture_time = _exif_datetime_to_utc(exif.get(36867) or exif.get(306))
            gps_ifd = exif.get_ifd(34853) if hasattr(exif, "get_ifd") else None
            if gps_ifd:
                lat = _dms_to_deg(gps_ifd.get(2), gps_ifd.get(1))
                lon = _dms_to_deg(gps_ifd.get(4), gps_ifd.get(3))
    except Exception:
        # Metadata is best-effort; missing/unreadable EXIF stays null.
        pass
    return capture_time, lat, lon, device


def _attach_links(db: Session, photos: List[SitePhoto]) -> None:
    if not photos:
        return
    ids = [photo.id for photo in photos]
    links = db.execute(
        select(PhotoWorkItemLink).where(PhotoWorkItemLink.photo_id.in_(ids))
    ).scalars().all()
    by_photo: Dict[str, List[str]] = {photo_id: [] for photo_id in ids}
    for link in links:
        by_photo.setdefault(link.photo_id, []).append(link.work_item_id)
    for photo in photos:
        photo._work_item_ids = sorted(by_photo.get(photo.id, []))  # type: ignore[attr-defined]


def list_photos(
    db: Session,
    project_id: str,
    report_id: Optional[str] = None,
    category: Optional[str] = None,
    photo_date: Optional[date] = None,
    location: Optional[str] = None,
    component: Optional[str] = None,
    stage: Optional[str] = None,
    work_item_id: Optional[str] = None,
) -> List[SitePhoto]:
    stmt = select(SitePhoto).where(SitePhoto.project_id == project_id)
    if report_id is not None:
        stmt = stmt.where(SitePhoto.report_id == report_id)
    if category is not None:
        stmt = stmt.where(SitePhoto.category == category)
    if work_item_id:
        stmt = stmt.where(
            SitePhoto.id.in_(
                select(PhotoWorkItemLink.photo_id).where(
                    PhotoWorkItemLink.work_item_id == work_item_id
                )
            )
        )
    cleaned_location = _clean_optional(location)
    cleaned_component = _clean_optional(component)
    cleaned_stage = _clean_optional(stage)
    if cleaned_location:
        stmt = stmt.where(SitePhoto.location == cleaned_location)
    if cleaned_component:
        stmt = stmt.where(SitePhoto.component == cleaned_component)
    if cleaned_stage:
        stmt = stmt.where(SitePhoto.stage == cleaned_stage)
    if photo_date is not None:
        start_local = datetime.combine(photo_date, dt_time.min, tzinfo=LOCAL_TZ)
        end_local = start_local + timedelta(days=1)
        # SQLite stores naive UTC values; compare in the same representation.
        start_utc = start_local.astimezone(timezone.utc).replace(tzinfo=None)
        end_utc = end_local.astimezone(timezone.utc).replace(tzinfo=None)
        effective_time = func.coalesce(SitePhoto.capture_time, SitePhoto.upload_time)
        stmt = stmt.where(effective_time >= start_utc, effective_time < end_utc)
    stmt = stmt.order_by(SitePhoto.upload_time.desc(), SitePhoto.id)
    photos = list(db.execute(stmt).scalars().all())
    _attach_links(db, photos)
    return photos


def get_photo(db: Session, project_id: str, photo_id: str) -> Optional[SitePhoto]:
    stmt = select(SitePhoto).where(
        SitePhoto.project_id == project_id, SitePhoto.id == photo_id
    )
    photo = db.execute(stmt).scalar_one_or_none()
    if photo is not None:
        _attach_links(db, [photo])
    return photo


def photo_work_item_ids(photo: SitePhoto, db: Optional[Session] = None) -> List[str]:
    value = getattr(photo, "_work_item_ids", None)
    if value is not None:
        return list(value)
    if db is not None:
        return sorted(
            db.execute(
                select(PhotoWorkItemLink.work_item_id).where(
                    PhotoWorkItemLink.photo_id == photo.id
                )
            ).scalars().all()
        )
    return []


def resolve_photo_path(photo: SitePhoto) -> Path:
    path = Path(photo.original_path)
    if not path.exists():
        raise ProjectResourceNotFound("Original photo file missing")
    if not _within_storage(path):
        raise ProjectResourceNotFound("Original photo file is outside project storage")
    return path


def create_photo(
    db: Session,
    project_id: str,
    data: bytes,
    filename: Optional[str],
    mime_type: Optional[str],
    report_id: Optional[str] = None,
    category: Optional[str] = None,
    location: Optional[str] = None,
    component: Optional[str] = None,
    stage: Optional[str] = None,
    confirmed_caption: Optional[str] = None,
    suggested_caption: Optional[str] = None,
    client_upload_id: Optional[str] = None,
    work_item_ids: Optional[List[str]] = None,
    actor_id: Optional[str] = None,
) -> SitePhoto:
    if not data:
        raise EmptyPhoto("Photo file is empty")
    if len(data) > MAX_PHOTO_BYTES:
        raise PhotoTooLarge("Photo exceeds the configured size limit")
    safe_mime = _safe_image_mime(mime_type, filename)

    digest = sha256_bytes(data)
    if client_upload_id:
        existing = db.execute(
            select(SitePhoto).where(
                SitePhoto.project_id == project_id,
                SitePhoto.client_upload_id == client_upload_id,
            )
        ).scalar_one_or_none()
        if existing is not None:
            if existing.sha256 != digest:
                raise PhotoUploadConflict(
                    "client_upload_id was already used with different photo bytes"
                )
            _attach_links(db, [existing])
            return existing

    _validate_report_id(db, project_id, report_id)
    validate_work_item_refs(db, project_id, work_item_ids or [])

    project_dir = _project_dir(project_id) / "photos"
    project_dir.mkdir(parents=True, exist_ok=True)
    safe_name = _sanitize_filename(filename)
    stored_path = project_dir / f"{uuid.uuid4().hex}_{safe_name}"
    stored_path.write_bytes(data)

    capture_time, lat, lon, device = _exif_metadata(data)
    photo = SitePhoto(
        project_id=project_id,
        report_id=report_id,
        original_path=str(stored_path),
        sha256=digest,
        capture_time=capture_time,
        upload_time=_now(),
        gps_lat=lat,
        gps_lon=lon,
        device=device,
        category=_clean_optional(category),
        location=_clean_optional(location),
        component=_clean_optional(component),
        stage=_clean_optional(stage),
        suggested_caption=suggested_caption,
        confirmed_caption=(
            confirmed_caption.strip() if confirmed_caption and confirmed_caption.strip() else None
        ),
        mime_type=safe_mime,
        size_bytes=len(data),
        filename=filename,
        client_upload_id=client_upload_id,
    )
    db.add(photo)
    try:
        db.flush()
        for work_item_id in work_item_ids or []:
            db.add(PhotoWorkItemLink(photo_id=photo.id, work_item_id=work_item_id))
        _audit(
            db,
            project_id=project_id,
            actor_id=actor_id,
            action="upload_photo",
            entity="SitePhoto",
            entity_id=photo.id,
            detail=json.dumps(
                {
                    "sha256": digest,
                    "report_id": report_id,
                    "category": photo.category,
                    "client_upload_id": client_upload_id,
                },
                ensure_ascii=False,
            ),
        )
        db.commit()
    except Exception:
        db.rollback()
        stored_path.unlink(missing_ok=True)
        raise
    db.refresh(photo)
    _attach_links(db, [photo])
    return photo


def patch_photo(
    db: Session,
    project_id: str,
    photo_id: str,
    payload: PhotoPatchIn,
    actor_id: Optional[str] = None,
) -> Optional[SitePhoto]:
    photo = get_photo(db, project_id, photo_id)
    if photo is None:
        return None

    changes = payload.model_dump(exclude_unset=True)

    if "report_id" in changes:
        _validate_report_id(db, project_id, changes["report_id"])
    for field in (
        "report_id",
        "category",
        "location",
        "component",
        "stage",
        "suggested_caption",
        "confirmed_caption",
    ):
        if field in changes:
            setattr(photo, field, _clean_optional(changes[field]))
    if "report_id" not in changes and photo.report_id:
        # Re-validate the existing link so a photo moved by another path cannot
        # keep a cross-project report reference.
        _validate_report_id(db, project_id, photo.report_id)
    if "work_item_ids" in changes:
        if changes["work_item_ids"] is None:
            db.execute(
                PhotoWorkItemLink.__table__.delete().where(
                    PhotoWorkItemLink.photo_id == photo.id
                )
            )
        else:
            validate_work_item_refs(db, project_id, changes["work_item_ids"])
            db.execute(
                PhotoWorkItemLink.__table__.delete().where(
                    PhotoWorkItemLink.photo_id == photo.id
                )
            )
            for work_item_id in changes["work_item_ids"]:
                db.add(PhotoWorkItemLink(photo_id=photo.id, work_item_id=work_item_id))

    photo.updated_at = _now()
    _audit(
        db,
        project_id=project_id,
        actor_id=actor_id,
        action="patch_photo",
        entity="SitePhoto",
        entity_id=photo.id,
        detail=json.dumps({"changed": sorted(changes)}, ensure_ascii=False),
    )
    db.commit()
    db.refresh(photo)
    _attach_links(db, [photo])
    return photo


# ---------------------------------------------------------------------------
# Snapshot + exports
# ---------------------------------------------------------------------------


def manpower_zero_null_summary(entries: Iterable[ManpowerEntry]) -> Dict[str, Any]:
    entries = list(entries)
    known = [entry for entry in entries if entry.count is not None]
    unknown = [entry for entry in entries if entry.count is None]
    return {
        "known_total": sum(entry.count or 0 for entry in known),
        "unknown_groups": [entry.group_name for entry in unknown],
        "zero_groups": [entry.group_name for entry in known if entry.count == 0],
    }


def photo_evidence_ready(photo: SitePhoto) -> bool:
    """A photo is export evidence only after a user confirmation.

    A user-typed confirmed caption or a user-selected category qualifies.
    ``suggested_caption`` never qualifies on its own.
    """

    return bool(
        (photo.confirmed_caption or "").strip() or (photo.category or "").strip()
    )


def build_report_snapshot(db: Session, report: DailyReport) -> Dict[str, Any]:
    all_photos = list_photos(db, report.project_id, report_id=report.id)
    evidence_photos = [photo for photo in all_photos if photo_evidence_ready(photo)]

    manpower_entries = sorted(
        report.manpower_entries, key=lambda item: (item.group_name.lower(), item.id)
    )
    work_logs = sorted(report.work_logs, key=lambda item: item.id)
    plans = sorted(
        report.next_day_plans,
        key=lambda item: (item.plan_date or date.min, item.id),
    )
    resolved_names = work_item_names(
        db,
        report.project_id,
        [
            *(item.work_item_id for item in work_logs),
            *(item.work_item_id for item in plans),
        ],
    )
    title = project_report_title(db, report.project_id)
    report_date_display = format_report_date(report.report_date)
    site_notes = site_notes_from_report(report)

    manpower = [
        {
            "id": entry.id,
            "group_name": entry.group_name,
            "person_name": entry.person_name,
            "count": entry.count,  # preserve None vs 0
            "organization_id": entry.organization_id,
        }
        for entry in manpower_entries
    ]
    work_log_items = [
        {
            "id": item.id,
            "work_item_id": item.work_item_id,
            "work_item_name": resolved_names.get(item.work_item_id) if item.work_item_id else None,
            "location": item.location,
            "component": item.component,
            "quantity": item.quantity,
            "unit": item.unit,
            "start_time": _iso_utc(item.start_time),
            "end_time": _iso_utc(item.end_time),
            "status": item.status,
            "notes": item.notes,
        }
        for item in work_logs
    ]
    plan_items = [
        {
            "id": item.id,
            "plan_date": item.plan_date.isoformat() if item.plan_date else None,
            "plan_date_display": format_report_date(item.plan_date) if item.plan_date else None,
            "work_item_id": item.work_item_id,
            "work_item_name": resolved_names.get(item.work_item_id) if item.work_item_id else None,
            "description": item.description,
            "location": item.location,
            "manpower": item.manpower,
            "equipment": item.equipment,
            "dependency": item.dependency,
        }
        for item in plans
    ]
    photo_items = [
        {
            "id": photo.id,
            "sha256": photo.sha256,
            "filename": photo.filename,
            "category": photo.category,
            "location": photo.location,
            "component": photo.component,
            "stage": photo.stage,
            "confirmed_caption": photo.confirmed_caption,
            "capture_time": _iso_utc(photo.capture_time),
            "gps": (
                None
                if photo.gps_lat is None or photo.gps_lon is None
                else [photo.gps_lat, photo.gps_lon]
            ),
            "gps_source": "exif" if photo.gps_lat is not None or photo.gps_lon is not None else None,
            # EXIF GPS is metadata until a person confirms it; never implied.
            "gps_confirmed": False,
            "work_item_ids": photo_work_item_ids(photo, db),
        }
        for photo in evidence_photos
    ]

    return {
        "report_id": report.id,
        "project_id": report.project_id,
        "title": title,
        "report_date": report.report_date.isoformat(),
        "report_date_display": report_date_display,
        "status": report.status,
        "notes": report.notes,
        "site_notes": site_notes,
        "report_updated_at": _iso_utc(report.updated_at),
        "manpower": manpower,
        "manpower_summary": manpower_zero_null_summary(manpower_entries),
        "work_logs": work_log_items,
        "next_day_plans": plan_items,
        "photos": photo_items,
        "photo_summary": {
            "evidence_count": len(evidence_photos),
            "omitted_unconfirmed_count": len(all_photos) - len(evidence_photos),
        },
        "evidence_policy": "confirmed_caption_or_user_selected_category",
        "auto_send": False,
        "exported_at": _now().isoformat(),
    }


def render_zalo_text(snapshot: Dict[str, Any]) -> str:
    lines: List[str] = []
    status_label = "Đã duyệt" if snapshot["status"] == "reviewed" else "Nháp"
    title = snapshot.get("title") or GENERIC_REPORT_TITLE
    report_date = snapshot.get("report_date_display") or snapshot["report_date"]
    lines.append(title)
    lines.append(f"Ngày: {report_date}")
    lines.append(f"Trạng thái: {status_label}")
    if snapshot.get("notes"):
        lines.append(f"Ghi chú: {snapshot['notes']}")
    site_notes = snapshot.get("site_notes") or {}
    note_rows = [
        (SITE_NOTE_LABELS[field], site_notes.get(field))
        for field in SITE_NOTE_FIELDS
        if site_notes.get(field)
    ]
    if note_rows:
        lines.append("Ghi chú hiện trường:")
        for label, value in note_rows:
            lines.append(f"- {label}: {value}")
    lines.append("")

    lines.append("1. Nhân lực")
    if snapshot["manpower"]:
        for item in snapshot["manpower"]:
            count_text = "chưa rõ" if item["count"] is None else str(item["count"])
            person = f" - {item['person_name']}" if item.get("person_name") else ""
            lines.append(f"- {item['group_name']}{person}: {count_text}")
    else:
        lines.append("- Chưa ghi nhận")
    summary = snapshot["manpower_summary"]
    lines.append(f"Tổng nhân lực đã biết: {summary['known_total']}")
    if summary["unknown_groups"]:
        lines.append("Nhóm chưa rõ số lượng: " + ", ".join(summary["unknown_groups"]))
    if summary["zero_groups"]:
        lines.append("Nhóm có 0 người: " + ", ".join(summary["zero_groups"]))
    lines.append("")

    lines.append("2. Công việc thực hiện")
    if snapshot["work_logs"]:
        for item in snapshot["work_logs"]:
            label = _join_distinct(
                [
                    item.get("work_item_name"),
                    item.get("location"),
                    item.get("component"),
                ]
            )
            line = f"- {label or 'Chưa ghi nhận'}"
            if item["quantity"] is not None:
                quantity = f"{item['quantity']} {item.get('unit') or ''}".strip()
                line += f": {quantity}"
            status = WORK_STATUS_LABELS.get(
                str(item.get("status") or "").lower(), item.get("status")
            )
            if status:
                line += f" ({status})"
            if item.get("notes"):
                line += f" - {item['notes']}"
            lines.append(line)
    else:
        lines.append("- Chưa ghi nhận")
    lines.append("")

    plans = snapshot["next_day_plans"]
    plan_dates = sorted(
        {
            item.get("plan_date_display")
            for item in plans
            if item.get("plan_date_display")
        }
    )
    shared_plan_date = plan_dates[0] if len(plan_dates) == 1 else None
    if shared_plan_date:
        lines.append(f"3. Dự kiến công việc ngày {shared_plan_date}")
    else:
        lines.append("3. Dự kiến công việc ngày kế tiếp")
    if plans:
        for item in plans:
            label = _join_distinct(
                [item.get("work_item_name"), item.get("description")]
            )
            date_prefix = ""
            if not shared_plan_date and item.get("plan_date_display"):
                date_prefix = f"{item['plan_date_display']}: "
            line = f"- {date_prefix}{label or 'Chưa ghi nhận'}"
            details = []
            if item.get("location") and item.get("location") not in label:
                details.append(f"Vị trí: {item['location']}")
            if item.get("manpower"):
                details.append(f"Nhân lực: {item['manpower']}")
            if item.get("equipment"):
                details.append(f"Thiết bị: {item['equipment']}")
            if item.get("dependency"):
                details.append(f"Phụ thuộc: {item['dependency']}")
            if details:
                line += " | " + " | ".join(details)
            lines.append(line)
    else:
        lines.append("- Chưa ghi nhận")
    lines.append("")

    lines.append("4. Hình ảnh")
    if snapshot["photos"]:
        for photo in snapshot["photos"]:
            caption = photo.get("confirmed_caption") or photo.get("category") or photo["id"]
            lines.append(f"- {caption}")
    else:
        lines.append("- Chưa có ảnh được xác nhận")
    if snapshot["photo_summary"]["omitted_unconfirmed_count"]:
        lines.append(
            f"({snapshot['photo_summary']['omitted_unconfirmed_count']} ảnh chưa xác nhận không đưa vào báo cáo)"
        )
    lines.append("")
    lines.append("Nội dung được tạo từ báo cáo ngày đã duyệt. Không tự động gửi Zalo.")
    return "\n".join(lines)


def _pdf_font_path() -> Optional[Path]:
    for candidate in PDF_FONT_CANDIDATES:
        if candidate and Path(candidate).exists():
            return Path(candidate)
    return None


def _wrap_line(line: str, width: int = 105) -> List[str]:
    if len(line) <= width:
        return [line]
    return [line[i : i + width] for i in range(0, len(line), width)] or [""]


def render_pdf(snapshot: Dict[str, Any], zalo_text: str, out_path: Path) -> Path:
    try:
        import fitz
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("PyMuPDF required for PDF export") from exc

    font_path = _pdf_font_path()
    doc = fitz.open()
    page = doc.new_page()
    font_name = "helv"
    if font_path is not None:
        page.insert_font(fontname="sitefont", fontfile=str(font_path))
        font_name = "sitefont"
    y = 40.0
    for raw_line in zalo_text.splitlines() or [""]:
        for line in _wrap_line(raw_line):
            if y > page.rect.height - 40:
                page = doc.new_page()
                if font_path is not None:
                    page.insert_font(fontname="sitefont", fontfile=str(font_path))
                y = 40.0
            page.insert_text((40, y), line, fontsize=9, fontname=font_name)
            y += 12
    doc.save(str(out_path))
    doc.close()
    return out_path


def render_docx(snapshot: Dict[str, Any], zalo_text: str, out_path: Path) -> Path:
    try:
        from docx import Document

        document = Document()
        for line in zalo_text.splitlines() or [""]:
            document.add_paragraph(line)
        document.save(str(out_path))
        return out_path
    except Exception:
        pass

    # Minimal valid OOXML fallback (no third-party import).
    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""
    rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""
    body_paragraphs = []
    for line in zalo_text.splitlines():
        escaped = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        body_paragraphs.append(
            f'<w:p><w:r><w:t xml:space="preserve">{escaped}</w:t></w:r></w:p>'
        )
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body>" + "".join(body_paragraphs) + "<w:sectPr/></w:body></w:document>"
    )
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", rels)
        archive.writestr("word/document.xml", document_xml)
    return out_path


def _add_evidence_photos(archive: zipfile.ZipFile, db: Session, report: DailyReport) -> None:
    photos = [
        photo
        for photo in list_photos(db, report.project_id, report_id=report.id)
        if photo_evidence_ready(photo)
    ]
    for index, photo in enumerate(photos, start=1):
        try:
            path = resolve_photo_path(photo)
        except ProjectResourceNotFound:
            continue
        archive.write(
            path,
            arcname=f"photos/{index:02d}_{_sanitize_filename(photo.filename)}",
        )


def create_export(
    db: Session,
    project_id: str,
    report: DailyReport,
    export_format: str,
    created_by: Optional[str] = None,
) -> GeneratedDocument:
    if report.status != "reviewed":
        raise ReportNotReviewed("Daily report must be reviewed before export")

    snapshot = build_report_snapshot(db, report)
    snapshot_json = json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True)
    snapshot_bytes = snapshot_json.encode("utf-8")
    snapshot_hash = sha256_bytes(snapshot_bytes)
    zalo_text = render_zalo_text(snapshot)

    export_dir = _project_dir(project_id) / "exports" / report.id
    export_dir.mkdir(parents=True, exist_ok=True)
    timestamp = _now().strftime("%Y%m%dT%H%M%SZ")
    base = export_dir / f"{timestamp}_{export_format}_{uuid.uuid4().hex[:8]}"

    preview_text: Optional[str] = None
    if export_format == "zalo":
        out_path = base.with_suffix(".txt")
        out_path.write_text(zalo_text, encoding="utf-8")
        preview_text = zalo_text
    elif export_format == "pdf":
        out_path = base.with_suffix(".pdf")
        render_pdf(snapshot, zalo_text, out_path)
    elif export_format == "docx":
        out_path = base.with_suffix(".docx")
        render_docx(snapshot, zalo_text, out_path)
    elif export_format == "zip":
        out_path = base.with_suffix(".zip")
        pdf_path = base.with_name(base.name + "_report.pdf")
        docx_path = base.with_name(base.name + "_report.docx")
        try:
            render_pdf(snapshot, zalo_text, pdf_path)
            render_docx(snapshot, zalo_text, docx_path)
            with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("snapshot.json", snapshot_bytes)
                archive.writestr("zalo.txt", zalo_text)
                archive.write(pdf_path, arcname="report.pdf")
                archive.write(docx_path, arcname="report.docx")
                _add_evidence_photos(archive, db, report)
        finally:
            pdf_path.unlink(missing_ok=True)
            docx_path.unlink(missing_ok=True)
    else:  # pragma: no cover - Pydantic Literal already rejects this
        raise ValueError(f"Unsupported export format: {export_format}")

    out_bytes = out_path.read_bytes()
    doc = GeneratedDocument(
        project_id=project_id,
        kind="daily_report_export",
        source_id=report.id,
        path=str(out_path),
        sha256=sha256_bytes(out_bytes),
        created_by=created_by,
        format=export_format,
        report_date=report.report_date,
        metadata_json=json.dumps(
            {
                "snapshot_sha256": snapshot_hash,
                "auto_send": False,
                "evidence_count": snapshot["photo_summary"]["evidence_count"],
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
    )
    db.add(doc)
    db.flush()
    _audit(
        db,
        project_id=project_id,
        actor_id=created_by,
        action="create_daily_report_export",
        entity="GeneratedDocument",
        entity_id=doc.id,
        detail=json.dumps(
            {
                "format": export_format,
                "report_id": report.id,
                "snapshot_sha256": snapshot_hash,
            },
            ensure_ascii=False,
        ),
    )
    db.commit()
    db.refresh(doc)
    doc._preview_text = preview_text  # type: ignore[attr-defined]
    doc._snapshot_sha256 = snapshot_hash  # type: ignore[attr-defined]
    return doc


def list_exports(
    db: Session, project_id: str, report_id: Optional[str] = None
) -> List[GeneratedDocument]:
    stmt = select(GeneratedDocument).where(GeneratedDocument.project_id == project_id)
    if report_id is not None:
        stmt = stmt.where(GeneratedDocument.source_id == report_id)
    stmt = stmt.order_by(GeneratedDocument.generated_at.desc(), GeneratedDocument.id)
    return list(db.execute(stmt).scalars().all())


def export_metadata(doc: GeneratedDocument) -> Dict[str, Any]:
    if not doc.metadata_json:
        return {}
    try:
        value = json.loads(doc.metadata_json)
        return value if isinstance(value, dict) else {}
    except (TypeError, ValueError):
        return {}


def get_generated_document(
    db: Session, project_id: str, doc_id: str
) -> Optional[GeneratedDocument]:
    return db.execute(
        select(GeneratedDocument).where(
            GeneratedDocument.project_id == project_id,
            GeneratedDocument.id == doc_id,
        )
    ).scalar_one_or_none()


def resolve_generated_path(doc: GeneratedDocument) -> Path:
    path = Path(doc.path)
    if not path.exists():
        raise ProjectResourceNotFound("Generated document file missing")
    if not _within_storage(path):
        raise ProjectResourceNotFound("Generated document is outside project storage")
    return path


# ---------------------------------------------------------------------------
# Audit (shared table, used only when available)
# ---------------------------------------------------------------------------


def _audit(
    db: Session,
    *,
    project_id: Optional[str],
    actor_id: Optional[str],
    action: str,
    entity: str,
    entity_id: str,
    detail: Optional[str] = None,
) -> None:
    if not actor_id:
        return
    try:
        from app.core.models import AuditLog  # type: ignore
    except Exception:  # pragma: no cover - isolated run
        return
    db.add(
        AuditLog(
            project_id=project_id,
            actor_id=actor_id,
            action=action,
            entity=entity,
            entity_id=entity_id,
            detail=detail,
        )
    )
