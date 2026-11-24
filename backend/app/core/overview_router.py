"""Read-only project overview: latest recorded day and per-segment progress.

All numbers come from stored component progress, daily reports, photos and
confirmed acceptance records.  Acceptance is never inferred from progress and
missing values stay null/empty rather than becoming zero.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .access import require_project_member
from .batch_scope import batch_component_ids
from .design_parameters import display_stage_name, format_parameter_value, load_t_values
from .component_models import (
    ComponentStage,
    ProgressEvent,
    Segment,
    StageDefinition,
    StructuralComponent,
    StructureZone,
)
from .database import get_db

try:  # acceptance-owned records and links
    from app.acceptance.models import (
        AcceptanceRecord,
        AcceptanceRequest,
        ComponentAcceptanceLink,
    )
except Exception:  # pragma: no cover - isolated core deployments
    AcceptanceRecord = AcceptanceRequest = ComponentAcceptanceLink = None  # type: ignore[assignment]

LOCAL_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
STATUS_ORDER = ("NOT_STARTED", "IN_PROGRESS", "COMPLETED", "BLOCKED")

router = APIRouter(tags=["components"])


def _local_date(value: datetime | None) -> date | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(LOCAL_TZ).date()


def _ratio(count: int, total: int) -> float:
    return round(count / total, 4) if total else 0.0


def _components(db: Session, project_id: str, batch_id: str | None = None):
    query = (
        select(StructuralComponent, Segment, StructureZone)
        .join(Segment, StructuralComponent.segment_id == Segment.id)
        .join(StructureZone, Segment.zone_id == StructureZone.id)
        .where(
            StructuralComponent.project_id == project_id,
            StructureZone.project_id == project_id,
        )
    )
    if batch_id:
        query = query.where(
            StructuralComponent.id.in_(batch_component_ids(project_id, batch_id))
        )
    return db.execute(query).all()


def _latest_events(db: Session, project_id: str) -> dict[str, ProgressEvent]:
    latest: dict[str, ProgressEvent] = {}
    for event in db.scalars(
        select(ProgressEvent)
        .join(
            StructuralComponent,
            ProgressEvent.component_id == StructuralComponent.id,
        )
        .where(
            StructuralComponent.project_id == project_id,
            ProgressEvent.voided_at.is_(None),
        )
        .order_by(ProgressEvent.created_at, ProgressEvent.id)
    ):
        latest[event.component_id] = event
    return latest


def _confirmed_components(db: Session, project_id: str) -> set[str]:
    if AcceptanceRecord is None or ComponentAcceptanceLink is None:
        return set()
    return set(
        db.scalars(
            select(ComponentAcceptanceLink.component_id)
            .join(
                AcceptanceRecord,
                ComponentAcceptanceLink.record_id == AcceptanceRecord.id,
            )
            .where(
                ComponentAcceptanceLink.project_id == project_id,
                AcceptanceRecord.project_id == project_id,
                AcceptanceRecord.status == "confirmed",
            )
        )
    )


def _empty_latest_day() -> dict:
    return {
        "date": None,
        "works": [],
        "manpower_total": None,
        "photo_count": 0,
        "daily_report_exists": False,
        "acceptance_today": [],
    }


def _manpower_total(db: Session, report_id: str) -> int | None:
    from app.site.models import ManpowerEntry

    counts = list(
        db.scalars(
            select(ManpowerEntry.count).where(ManpowerEntry.report_id == report_id)
        )
    )
    known = [count for count in counts if count is not None]
    if not known:
        return None
    return sum(known)


def _photo_count(db: Session, project_id: str, day: date) -> int:
    from app.site.models import SitePhoto

    # shortcut: scans upload times in Python; switch to a date-range filter if a
    # project's photo history grows large.
    uploads = db.scalars(
        select(SitePhoto.upload_time).where(SitePhoto.project_id == project_id)
    )
    return sum(1 for value in uploads if _local_date(value) == day)


def _acceptance_today(db: Session, project_id: str, day: date) -> list[dict]:
    if (
        AcceptanceRecord is None
        or AcceptanceRequest is None
        or ComponentAcceptanceLink is None
    ):
        return []
    rows = db.execute(
        select(AcceptanceRecord, AcceptanceRequest.number)
        .join(AcceptanceRequest, AcceptanceRecord.request_id == AcceptanceRequest.id)
        .where(
            AcceptanceRecord.project_id == project_id,
            AcceptanceRecord.status == "confirmed",
        )
    ).all()
    records = [
        (record, request_number)
        for record, request_number in rows
        if _local_date(record.confirmed_at) == day
    ]
    if not records:
        return []
    codes: dict[str, set[str]] = defaultdict(set)
    for component_id, code in db.execute(
        select(ComponentAcceptanceLink.record_id, StructuralComponent.canonical_code)
        .join(
            StructuralComponent,
            ComponentAcceptanceLink.component_id == StructuralComponent.id,
        )
        .where(
            ComponentAcceptanceLink.project_id == project_id,
            ComponentAcceptanceLink.record_id.in_([record.id for record, _ in records]),
        )
    ):
        codes[component_id].add(code)
    return [
        {
            "id": record.id,
            "number": record.number,
            "request_number": request_number,
            "result": record.result,
            "record_date": record.record_date.isoformat() if record.record_date else None,
            "confirmed_at": record.confirmed_at.isoformat() if record.confirmed_at else None,
            "component_codes": sorted(codes.get(record.id, ())),
        }
        for record, request_number in records
    ]


def _works_for_day(db: Session, project_id: str, day: date, batch_id: str | None = None) -> list[dict]:
    """Group the latest progress event per component+stage on ``day``."""
    query = (
        select(
            ProgressEvent,
            StructuralComponent,
            Segment,
            StructureZone,
            StageDefinition,
        )
        .join(StructuralComponent, ProgressEvent.component_id == StructuralComponent.id)
        .join(Segment, StructuralComponent.segment_id == Segment.id)
        .join(StructureZone, Segment.zone_id == StructureZone.id)
        .join(ComponentStage, ProgressEvent.component_stage_id == ComponentStage.id)
        .join(StageDefinition, ComponentStage.stage_definition_id == StageDefinition.id)
        .where(
            StructuralComponent.project_id == project_id,
            StructureZone.project_id == project_id,
            ProgressEvent.event_date == day,
            ProgressEvent.voided_at.is_(None),
        )
        .order_by(ProgressEvent.created_at, ProgressEvent.id)
    )
    if batch_id:
        query = query.where(
            StructuralComponent.id.in_(batch_component_ids(project_id, batch_id))
        )
    rows = db.execute(query).all()

    latest: dict[tuple[str, str], tuple] = {}
    for row in rows:
        _, component, _, _, definition = row
        latest[(component.id, definition.id)] = row

    t_by_component = load_t_values(
        db, [component.id for _, component, _, _, _ in latest.values()]
    )
    grouped: dict[tuple, dict[str, float | None]] = defaultdict(dict)
    for event, component, segment, zone, definition in latest.values():
        grouped[
            (
                definition.name,
                zone.name,
                segment.number,
                component.type,
                event.status,
            )
        ][component.canonical_code] = t_by_component.get(component.id)

    works = []
    for (raw_stage_name, zone, segment, component_type, status), code_values in grouped.items():
        ordered_codes = sorted(code_values)
        numeric_values = sorted(
            {round(value, 4) for value in code_values.values() if value is not None}
        )
        has_missing = any(value is None for value in code_values.values())
        stage_name = display_stage_name(
            raw_stage_name, [code_values[code] for code in ordered_codes]
        )
        mixed = len(numeric_values) > 1 or (has_missing and bool(numeric_values))
        codes = [
            (
                f"{code} (t = {format_parameter_value(code_values[code])} cm)"
                if code_values[code] is not None
                else f"{code} (chưa có số liệu)"
            )
            if mixed
            else code
            for code in ordered_codes
        ]
        works.append(
            {
                "stage_name": stage_name,
                "zone": zone,
                "segment": segment,
                "component_type": component_type,
                "status": status,
                "count": len(codes),
                "codes": codes,
            }
        )
    works.sort(key=lambda item: (
        item["zone"], item["segment"], item["stage_name"], item["status"]
    ))
    return works


@router.get("/projects/{project_id}/overview/latest-day")
def overview_latest_day(project_id: str, batch_id: str | None = None,
                        db: Session = Depends(get_db)):
    require_project_member(project_id)
    from app.site.models import DailyReport

    progress_query = (
        select(func.max(ProgressEvent.event_date))
        .join(
            StructuralComponent,
            ProgressEvent.component_id == StructuralComponent.id,
        )
        .where(
            StructuralComponent.project_id == project_id,
            ProgressEvent.voided_at.is_(None),
        )
    )
    if batch_id:
        progress_query = progress_query.where(
            StructuralComponent.id.in_(batch_component_ids(project_id, batch_id))
        )
    progress_day = db.scalar(progress_query)

    report_day = db.scalar(
        select(func.max(DailyReport.report_date)).where(
            DailyReport.project_id == project_id
        )
    )
    candidates = [day for day in (progress_day, report_day) if day is not None]
    if not candidates:
        return _empty_latest_day()
    day = max(candidates)

    report = db.scalar(
        select(DailyReport).where(
            DailyReport.project_id == project_id,
            DailyReport.report_date == day,
        )
    )
    return {
        "date": day.isoformat(),
        "works": _works_for_day(db, project_id, day, batch_id),
        "manpower_total": _manpower_total(db, report.id) if report else None,
        "photo_count": _photo_count(db, project_id, day),
        "daily_report_exists": report is not None,
        "acceptance_today": _acceptance_today(db, project_id, day),
    }


@router.get("/projects/{project_id}/overview/in-progress")
def overview_in_progress(project_id: str, batch_id: str | None = None,
                         db: Session = Depends(get_db)):
    """Components whose latest non-voided event is still open or blocked."""
    require_project_member(project_id)
    today = datetime.now(LOCAL_TZ).date()

    query = (
        select(
            ProgressEvent,
            StructuralComponent,
            Segment,
            StructureZone,
            StageDefinition,
        )
        .join(StructuralComponent, ProgressEvent.component_id == StructuralComponent.id)
        .join(Segment, StructuralComponent.segment_id == Segment.id)
        .join(StructureZone, Segment.zone_id == StructureZone.id)
        .join(ComponentStage, ProgressEvent.component_stage_id == ComponentStage.id)
        .join(StageDefinition, ComponentStage.stage_definition_id == StageDefinition.id)
        .where(
            StructuralComponent.project_id == project_id,
            StructureZone.project_id == project_id,
            ProgressEvent.voided_at.is_(None),
        )
        .order_by(ProgressEvent.created_at, ProgressEvent.id)
    )
    if batch_id:
        query = query.where(
            StructuralComponent.id.in_(batch_component_ids(project_id, batch_id))
        )
    latest: dict[str, tuple] = {}
    for row in db.execute(query).all():
        latest[row[1].id] = row

    open_rows = [
        row for row in latest.values()
        if row[0].status in ("IN_PROGRESS", "BLOCKED")
    ]
    t_by_component = load_t_values(db, [row[1].id for row in open_rows])
    grouped: dict[tuple, dict] = {}
    for event, component, segment, zone, definition in open_rows:
        key = (definition.id, zone.id, segment.number, component.type)
        group = grouped.setdefault(
            key,
            {
                "stage_name": "",
                "stage_definition_id": definition.id,
                "zone": zone.name,
                "segment": segment.number,
                "component_type": component.type,
                "component_count": 0,
                "days_since_update": 0,
                "components": [],
                "_name": definition.name,
                "_t_values": [],
            },
        )
        days = max(0, (today - event.event_date).days)
        group["component_count"] += 1
        group["days_since_update"] = max(group["days_since_update"], days)
        group["_t_values"].append(t_by_component.get(component.id))
        group["components"].append(
            {
                "id": component.id,
                "code": component.canonical_code,
                "type": component.type,
                "status": event.status,
                "last_event_date": event.event_date.isoformat(),
                "days_since_update": days,
            }
        )

    groups = []
    for group in grouped.values():
        group["stage_name"] = display_stage_name(
            group.pop("_name"), group.pop("_t_values")
        )
        group["components"].sort(key=lambda item: item["code"])
        groups.append(group)
    groups.sort(key=lambda item: (
        item["zone"], item["segment"], item["stage_name"]
    ))
    return {
        "project_id": project_id,
        "today": today.isoformat(),
        "total_components": sum(group["component_count"] for group in groups),
        "groups": groups,
    }


@router.get("/projects/{project_id}/overview/segments")
def overview_segments(project_id: str, batch_id: str | None = None,
                      db: Session = Depends(get_db)):
    require_project_member(project_id)

    rows = _components(db, project_id, batch_id)
    verified = {
        component.id for component, _, _ in rows if component.verification == "VERIFIED"
    }
    latest = _latest_events(db, project_id)
    confirmed = _confirmed_components(db, project_id) & verified

    buckets: dict[tuple[str, int], dict] = {}
    for component, segment, zone in rows:
        key = (zone.name, segment.number)
        bucket = buckets.setdefault(
            key,
            {
                "segment_id": segment.id,
                "zone": zone.name,
                "segment": segment.number,
                "component_count": 0,
                "verified_components": 0,
                "construction": {
                    "not_started": 0,
                    "in_progress": 0,
                    "completed": 0,
                    "blocked": 0,
                },
                "acceptance": {"confirmed": 0},
            },
        )
        bucket["component_count"] += 1
        if component.id not in verified:
            continue
        bucket["verified_components"] += 1
        event = latest.get(component.id)
        status = event.status if event else "NOT_STARTED"
        if status not in STATUS_ORDER:
            status = "NOT_STARTED"
        bucket["construction"][status.lower()] += 1
        if component.id in confirmed:
            bucket["acceptance"]["confirmed"] += 1

    segments = []
    for key in sorted(buckets, key=lambda item: (item[0], item[1])):
        bucket = buckets[key]
        total = bucket["verified_components"]
        segments.append(
            {
                **bucket,
                "construction": {
                    **bucket["construction"],
                    "completion_ratio": _ratio(
                        bucket["construction"]["completed"], total
                    ),
                },
                "acceptance": {
                    **bucket["acceptance"],
                    "completion_ratio": _ratio(
                        bucket["acceptance"]["confirmed"], total
                    ),
                },
            }
        )
    return {"project_id": project_id, "segments": segments}
