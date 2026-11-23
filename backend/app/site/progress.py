"""Component progress views, reviewed bulk updates and journal preview.

Progress events and construction stages are shared-core entities.  This module
adds site-facing aggregation, an exact preview/commit wrapper for bulk entry, an
atomic multi-line daily commit and a read-only reviewed journal preview.
Construction and acceptance status stay independent: nothing here writes
acceptance records or derives acceptance from progress.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .db import get_db
from .dependencies import (
    current_user_id,
    require_project_member,
    require_site_editor,
)
from .models import SitePhoto, SiteProgressBulkBatch
from .photo_components import photo_component_label
from app.core.batch_scope import batch_component_ids
from app.core.design_parameters import display_stage_name, load_t_values
from app.core.models import ProjectMember
from .progress_inference import apply_inferred_progress
from .schemas import LOCAL_TZ
from .service import (
    WORK_STATUS_LABELS,
    SiteError,
    _audit,
    format_report_date,
    list_photos,
    photo_evidence_ready,
    project_report_title,
    sha256_bytes,
    site_notes_from_report,
    work_item_names,
)

try:  # shared component inventory, stages and progress events
    from app.core.component_models import (
        ComponentAlias,
        ComponentStage,
        DesignGroup,
        ProgressEvent,
        RepairScope,
        Segment,
        StageDefinition,
        StructuralComponent,
        StructureZone,
    )
except Exception:  # pragma: no cover - isolated runs without shared core
    ComponentAlias = ComponentStage = DesignGroup = ProgressEvent = None  # type: ignore[assignment]
    RepairScope = Segment = StageDefinition = StructuralComponent = None  # type: ignore[assignment]
    StructureZone = None  # type: ignore[assignment]

try:  # shared project-scoped evidence validation
    from app.core.evidence import validate_evidence_refs
except Exception:  # pragma: no cover - isolated runs without shared core
    validate_evidence_refs = None  # type: ignore[assignment]

router = APIRouter(prefix="", tags=["site-progress"])

CONSTRUCTION_STATUSES = ("NOT_STARTED", "IN_PROGRESS", "COMPLETED", "BLOCKED")
JOURNAL_PROGRESS_STATUS_LABELS = {
    "not_started": "Chưa bắt đầu",
    "in_progress": "Đang thi công",
    "completed": "Hoàn thành",
    "blocked": "Tạm dừng",
}
ACCEPTANCE_STATUSES = (
    "NOT_LINKED",
    "PENDING",
    "APPROVED",
    "CONDITIONAL",
    "REJECTED",
    "CONFIRMED",
)
INPUT_STATUSES = ("IN_PROGRESS", "COMPLETED", "BLOCKED")
MAX_DAILY_LINES = 50
MAX_DAILY_COMPONENTS = 500


class ProgressSelectionConflict(SiteError):
    """The reviewed component/stage selection no longer matches the project."""


class StageSelectionIn(BaseModel):
    component_id: str = Field(min_length=1, max_length=36)
    stage_id: str = Field(min_length=1, max_length=36)


def _clean_component_ids(value: List[str]) -> List[str]:
    ids = [item.strip() for item in value]
    if any(not item for item in ids):
        raise ValueError("component_ids must not contain blanks")
    if len(ids) != len(set(ids)):
        raise ValueError("component_ids must be unique")
    return ids


def _clean_stage_selections(
    value: List[StageSelectionIn],
) -> List[StageSelectionIn]:
    selected: List[StageSelectionIn] = []
    seen: set[str] = set()
    for item in value:
        component_id = item.component_id.strip()
        stage_id = item.stage_id.strip()
        if not component_id or not stage_id:
            raise ValueError("stage selections must not contain blanks")
        if component_id in seen:
            raise ValueError("stage selections must have unique component_id")
        seen.add(component_id)
        selected.append(StageSelectionIn(component_id=component_id, stage_id=stage_id))
    return selected


def _require_selection_components(
    component_ids: List[str], selections: List[StageSelectionIn]
) -> None:
    requested = set(component_ids)
    if any(item.component_id not in requested for item in selections):
        raise ValueError("stage selection references a component outside component_ids")


class BulkProgressIn(BaseModel):
    stage_definition_id: str = Field(min_length=1, max_length=36)
    component_ids: List[str] = Field(min_length=1, max_length=500)
    stage_selections: List[StageSelectionIn] = Field(default_factory=list, max_length=500)
    event_date: date
    status: Literal["IN_PROGRESS", "COMPLETED", "BLOCKED"]
    quantity: Optional[float] = Field(default=None, ge=0, le=1_000_000_000_000)
    unit: Optional[str] = Field(default=None, max_length=30)
    note: Optional[str] = Field(default=None, max_length=2000)
    evidence_refs: List[str] = Field(default_factory=list, max_length=20)

    @field_validator("component_ids")
    @classmethod
    def _exact_component_ids(cls, value: List[str]) -> List[str]:
        return _clean_component_ids(value)

    @field_validator("stage_selections")
    @classmethod
    def _exact_stage_selections(cls, value: List[StageSelectionIn]) -> List[StageSelectionIn]:
        return _clean_stage_selections(value)

    @model_validator(mode="after")
    def _selections_belong_to_requested_components(self):
        _require_selection_components(self.component_ids, self.stage_selections)
        return self

    @field_validator("evidence_refs")
    @classmethod
    def _valid_evidence(cls, value: List[str]) -> List[str]:
        refs = [item.strip() for item in value]
        if any(not item or len(item) > 120 for item in refs):
            raise ValueError("each evidence ref must be 1-120 characters")
        return refs

    @field_validator("unit", "note")
    @classmethod
    def _blank_to_none(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        return value or None


class BulkProgressPreviewIn(BulkProgressIn):
    pass


class BulkProgressCommitIn(BulkProgressIn):
    reviewed: Literal[True]
    idempotency_key: str = Field(min_length=1, max_length=120)


class DailyProgressLineIn(BaseModel):
    """One work item in a daily entry.

    ``group_quantity``/``group_unit`` describe the work group as a whole.  They
    are kept in the batch result and audit log, never copied onto each component
    event.
    """

    stage_definition_id: str = Field(min_length=1, max_length=36)
    component_ids: List[str] = Field(min_length=1, max_length=MAX_DAILY_COMPONENTS)
    stage_selections: List[StageSelectionIn] = Field(default_factory=list, max_length=MAX_DAILY_COMPONENTS)
    status: Literal["IN_PROGRESS", "COMPLETED", "BLOCKED"]
    group_quantity: Optional[float] = Field(default=None, ge=0, le=1_000_000_000_000)
    group_unit: Optional[str] = Field(default=None, max_length=30)

    @field_validator("component_ids")
    @classmethod
    def _exact_component_ids(cls, value: List[str]) -> List[str]:
        return _clean_component_ids(value)

    @field_validator("stage_selections")
    @classmethod
    def _exact_stage_selections(cls, value: List[StageSelectionIn]) -> List[StageSelectionIn]:
        return _clean_stage_selections(value)

    @field_validator("group_unit")
    @classmethod
    def _blank_to_none(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @model_validator(mode="after")
    def _selections_belong_to_requested_components(self):
        _require_selection_components(self.component_ids, self.stage_selections)
        return self


class DailyProgressIn(BaseModel):
    event_date: date
    lines: List[DailyProgressLineIn] = Field(min_length=1, max_length=MAX_DAILY_LINES)

    @field_validator("event_date")
    @classmethod
    def _strict_event_date(cls, value: date) -> date:
        if value > datetime.now(LOCAL_TZ).date():
            raise ValueError("event_date must not be in the future")
        return value

    @model_validator(mode="after")
    def _bounded_workload(self):
        total = sum(len(line.component_ids) for line in self.lines)
        if total > MAX_DAILY_COMPONENTS:
            raise ValueError(
                f"a daily entry supports at most {MAX_DAILY_COMPONENTS} components"
            )
        return self


class DailyProgressCommitIn(DailyProgressIn):
    reviewed: Literal[True]
    idempotency_key: str = Field(min_length=1, max_length=120)


class ProgressBatchUndoIn(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)


class ProgressEventCorrectIn(BaseModel):
    status: Literal["IN_PROGRESS", "COMPLETED", "BLOCKED"]
    reason: str = Field(min_length=1, max_length=1000)


class DesignQuantityIn(BaseModel):
    component_ids: List[str] = Field(min_length=1, max_length=500)

    @field_validator("component_ids")
    @classmethod
    def _exact_component_ids(cls, value: List[str]) -> List[str]:
        ids = [item.strip() for item in value]
        if any(not item for item in ids):
            raise ValueError("component_ids must not contain blanks")
        if len(ids) != len(set(ids)):
            raise ValueError("component_ids must be unique")
        return ids


class DesignQuantityOut(BaseModel):
    quantity: Optional[float] = None
    unit: Optional[str] = None
    scope: Literal["COMPONENT", "SHARED", "SUBGROUP"]
    scope_label: Optional[str] = None
    drawing: Optional[str] = None
    page: Optional[str] = None
    note: Optional[str] = None


class ProgressStageOut(BaseModel):
    id: str
    stage_definition_id: str
    code: str
    name: str
    position: int
    repair_scope_id: Optional[str] = None
    scope_kind: Optional[str] = None
    status: str
    latest_event_at: Optional[datetime] = None
    inferred_from_stage_id: Optional[str] = None
    inference_conflict: bool = False


class ProgressLatestOut(BaseModel):
    id: str
    stage_id: str
    stage_code: Optional[str] = None
    stage_name: Optional[str] = None
    event_date: date
    status: str
    quantity: Optional[float] = None
    unit: Optional[str] = None
    note: Optional[str] = None
    created_at: datetime


class ProgressRowOut(BaseModel):
    id: str
    canonical_code: str
    raw_code: str
    type: str
    zone: str
    segment_id: str
    segment_number: int
    design_group: Optional[str] = None
    verification: str
    record_origin: str
    scopes: List[str] = Field(default_factory=list)
    stages: List[ProgressStageOut] = Field(default_factory=list)
    construction_status: str
    construction_event: Optional[ProgressLatestOut] = None
    acceptance_status: str
    acceptance_count: int = 0
    acceptance_note: str
    stage_id: Optional[str] = None
    stage_available: bool = False
    stage_ambiguous: bool = False
    stage_options: List[ProgressStageOut] = Field(default_factory=list)


class ProgressPreviewOut(BaseModel):
    stage_definition_id: str
    components: List[ProgressRowOut]
    missing_component_ids: List[str]
    missing_stage_component_ids: List[str]
    ambiguous_stage_component_ids: List[str] = Field(default_factory=list)
    invalid_stage_component_ids: List[str] = Field(default_factory=list)
    warnings: List[str]
    can_commit: bool
    count: int
    ready_count: int


class ProgressEventOut(BaseModel):
    id: str
    component_id: str
    stage_id: str
    event_date: date
    status: str
    quantity: Optional[float] = None
    unit: Optional[str] = None
    note: Optional[str] = None
    evidence_refs: List[str] = Field(default_factory=list)
    batch_id: Optional[str] = None
    created_at: datetime


class ProgressCommitOut(BaseModel):
    created: int
    batch_id: str
    events: List[ProgressEventOut]
    missing_component_ids: List[str] = Field(default_factory=list)
    missing_stage_component_ids: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class DailyProgressLinePreview(ProgressPreviewOut):
    line_index: int
    stage_display_name: Optional[str] = None
    group_quantity: Optional[float] = None
    group_unit: Optional[str] = None


class DailyProgressPreviewOut(BaseModel):
    can_commit: bool
    lines: List[DailyProgressLinePreview]
    warnings: List[str] = Field(default_factory=list)


class DailyProgressLineResult(ProgressCommitOut):
    line_index: int
    stage_definition_id: str
    group_quantity: Optional[float] = None
    group_unit: Optional[str] = None


class DailyProgressCommitOut(BaseModel):
    created: int
    lines: List[DailyProgressLineResult]


def _empty_acceptance() -> dict[str, Any]:
    return {
        "acceptance_status": "NOT_LINKED",
        "acceptance_count": 0,
        # Acceptance links are owned by the acceptance module.  Without an
        # explicit component link this stays NOT_LINKED instead of being
        # inferred from construction progress.
        "acceptance_note": "Chưa có liên kết PYC/BBNT theo cấu kiện",
    }


def _acceptance_map(
    db: Session, project_id: str, ids: List[str]
) -> dict[str, dict[str, Any]]:
    out = {item: _empty_acceptance() for item in ids}
    if not ids:
        return out
    try:
        from app.acceptance.models import (
            AcceptanceRecord,
            AcceptanceRequest,
            ComponentAcceptanceLink,
        )

        links = list(
            db.scalars(
                select(ComponentAcceptanceLink).where(
                    ComponentAcceptanceLink.project_id == project_id,
                    ComponentAcceptanceLink.component_id.in_(ids),
                )
            )
        )
        if not links:
            return out
        record_ids = {link.record_id for link in links if link.record_id}
        records = {
            record.id: record
            for record in db.scalars(
                select(AcceptanceRecord).where(
                    AcceptanceRecord.project_id == project_id,
                    AcceptanceRecord.id.in_(record_ids),
                )
            )
        } if record_ids else {}
        request_ids = {link.request_id for link in links if link.request_id}
        requests = {
            request.id: request
            for request in db.scalars(
                select(AcceptanceRequest).where(
                    AcceptanceRequest.project_id == project_id,
                    AcceptanceRequest.id.in_(request_ids),
                )
            )
        } if request_ids else {}
    except Exception:  # pragma: no cover - acceptance module unavailable
        return out

    grouped: dict[str, list[Any]] = {}
    for link in links:
        grouped.setdefault(link.component_id, []).append(link)
    for component_id, component_links in grouped.items():
        confirmed = {
            records[link.record_id]
            for link in component_links
            if link.record_id
            and link.record_id in records
            and records[link.record_id].status == "confirmed"
        }
        if confirmed:
            latest = max(
                confirmed,
                key=lambda record: (str(record.confirmed_at or ""), record.id),
            )
            result = (latest.result or "").upper()
            status = result if result in ACCEPTANCE_STATUSES else "CONFIRMED"
            out[component_id] = {
                "acceptance_status": status,
                "acceptance_count": len(confirmed),
                "acceptance_note": (
                    f"{len(confirmed)} BBNT đã xác nhận"
                    if len(confirmed) > 1
                    else "BBNT đã xác nhận"
                ),
            }
            continue
        has_target = any(
            (link.record_id in records) or (link.request_id in requests)
            for link in component_links
        )
        if has_target:
            out[component_id] = {
                "acceptance_status": "PENDING",
                "acceptance_count": 0,
                "acceptance_note": "Đã liên kết PYC/BBNT, chưa xác nhận",
            }
    return out


def _zone_key(value: str) -> str:
    import unicodedata

    return unicodedata.normalize("NFKC", value).strip().casefold()


def _stage_status(
    stages: List[dict[str, Any]], events: List[ProgressEvent]
) -> tuple[List[dict[str, Any]], Optional[ProgressEvent], Optional[dict[str, Any]]]:
    latest_by_stage: dict[str, ProgressEvent] = {}
    for event in events:
        current = latest_by_stage.get(event.component_stage_id)
        if current is None or (event.created_at, event.id) > (current.created_at, current.id):
            latest_by_stage[event.component_stage_id] = event
    out = []
    for stage in stages:
        event = latest_by_stage.get(stage["id"])
        out.append(
            {
                **stage,
                "status": event.status if event else "NOT_STARTED",
                "latest_event_at": event.created_at if event else None,
            }
        )
    latest = max(
        latest_by_stage.values(),
        key=lambda event: (event.created_at, event.id),
        default=None,
    )
    latest_stage = None
    if latest is not None:
        latest_stage = next(
            (stage for stage in out if stage["id"] == latest.component_stage_id), None
        )
    return out, latest, latest_stage


def _load_rows(
    db: Session,
    project_id: str,
    *,
    component_ids: Optional[List[str]] = None,
    q: Optional[str] = None,
    zone: Optional[str] = None,
    segment_id: Optional[str] = None,
    component_type: Optional[str] = None,
    group_id: Optional[str] = None,
    scope: Optional[str] = None,
    origin: Optional[str] = None,
    batch_id: Optional[str] = None,
) -> List[dict[str, Any]]:
    if StructuralComponent is None:
        return []
    query = (
        select(StructuralComponent, Segment, StructureZone, DesignGroup)
        .join(Segment, StructuralComponent.segment_id == Segment.id)
        .join(StructureZone, Segment.zone_id == StructureZone.id)
        .outerjoin(DesignGroup, StructuralComponent.design_group_id == DesignGroup.id)
        .where(
            StructuralComponent.project_id == project_id,
            StructureZone.project_id == project_id,
        )
    )
    if component_ids is not None:
        query = query.where(StructuralComponent.id.in_(component_ids))
    if zone:
        query = query.where(StructureZone.name_key == _zone_key(zone))
    if segment_id:
        query = query.where(StructuralComponent.segment_id == segment_id)
    if component_type:
        query = query.where(StructuralComponent.type == component_type)
    if group_id:
        query = query.where(StructuralComponent.design_group_id == group_id)
    if origin:
        query = query.where(StructuralComponent.record_origin == origin)
    if scope:
        query = query.where(
            StructuralComponent.id.in_(
                select(RepairScope.component_id).where(RepairScope.kind == scope)
            )
        )
    if batch_id:
        query = query.where(
            StructuralComponent.id.in_(batch_component_ids(project_id, batch_id))
        )
    if q:
        code = q.strip().upper()
        query = query.where(
            or_(
                StructuralComponent.canonical_code == code,
                StructuralComponent.raw_code == code,
                StructuralComponent.id.in_(
                    select(ComponentAlias.component_id).where(
                        ComponentAlias.alias == code
                    )
                ),
            )
        )

    records = db.execute(
        query.order_by(
            StructureZone.name,
            Segment.number,
            StructuralComponent.canonical_code,
            StructuralComponent.id,
        )
    ).all()
    ids = [component.id for component, _, _, _ in records]
    t_values = load_t_values(db, ids) if ids else {}
    scopes: dict[str, List[str]] = {}
    if ids:
        for component_id, kind in db.execute(
            select(RepairScope.component_id, RepairScope.kind).where(
                RepairScope.component_id.in_(ids)
            )
        ):
            scopes.setdefault(component_id, []).append(kind)

    stages_by_component: dict[str, List[dict[str, Any]]] = {}
    stage_ids: List[str] = []
    scope_kinds: dict[str, str] = {}
    if ids:
        stage_rows = db.execute(
            select(ComponentStage, StageDefinition)
            .join(
                StageDefinition,
                ComponentStage.stage_definition_id == StageDefinition.id,
            )
            .where(ComponentStage.component_id.in_(ids))
            .order_by(StageDefinition.position, StageDefinition.code)
        ).all()
        scope_ids = {stage.repair_scope_id for stage, _ in stage_rows}
        if scope_ids:
            scope_kinds = dict(
                db.execute(
                    select(RepairScope.id, RepairScope.kind).where(
                        RepairScope.id.in_(scope_ids)
                    )
                ).all()
            )
        for stage, definition in stage_rows:
            stage_ids.append(stage.id)
            stages_by_component.setdefault(stage.component_id, []).append(
                {
                    "id": stage.id,
                    "stage_definition_id": definition.id,
                    "code": definition.code,
                    "name": display_stage_name(
                        definition.name, [t_values.get(stage.component_id)]
                    ),
                    "position": definition.position,
                    "repair_scope_id": stage.repair_scope_id,
                    "scope_kind": scope_kinds.get(stage.repair_scope_id),
                }
            )
    events_by_stage: dict[str, List[ProgressEvent]] = {}
    if stage_ids:
        for event in db.scalars(
            select(ProgressEvent)
            .where(
                ProgressEvent.component_stage_id.in_(stage_ids),
                ProgressEvent.voided_at.is_(None),
            )
            .order_by(ProgressEvent.created_at, ProgressEvent.id)
        ):
            events_by_stage.setdefault(event.component_stage_id, []).append(event)

    rows: List[dict[str, Any]] = []
    for component, segment, area, group in records:
        stages = stages_by_component.get(component.id, [])
        events = [
            event
            for stage in stages
            for event in events_by_stage.get(stage["id"], [])
        ]
        stages_out, latest, latest_stage = _stage_status(stages, events)
        apply_inferred_progress(component.type, stages_out)
        rows.append(
            {
                "id": component.id,
                "canonical_code": component.canonical_code,
                "raw_code": component.raw_code,
                "type": component.type,
                "zone": area.name,
                "segment_id": component.segment_id,
                "segment_number": segment.number,
                "design_group": group.name if group else None,
                "verification": component.verification,
                "record_origin": component.record_origin,
                "scopes": sorted(scopes.get(component.id, [])),
                "stages": stages_out,
                "construction_status": latest.status if latest else "NOT_STARTED",
                "construction_event": (
                    {
                        "id": latest.id,
                        "stage_id": latest.component_stage_id,
                        "stage_code": latest_stage["code"] if latest_stage else None,
                        "stage_name": latest_stage["name"] if latest_stage else None,
                        "event_date": latest.event_date,
                        "status": latest.status,
                        "quantity": latest.quantity,
                        "unit": latest.unit,
                        "note": latest.note,
                        "created_at": latest.created_at,
                    }
                    if latest
                    else None
                ),
                **_empty_acceptance(),
                "stage_id": None,
                "stage_available": False,
                "stage_ambiguous": False,
                "stage_options": [],
            }
        )
    acceptance = _acceptance_map(db, project_id, ids)
    for row in rows:
        row.update(acceptance.get(row["id"], _empty_acceptance()))
    return rows


def list_progress(
    db: Session,
    project_id: str,
    *,
    q: Optional[str] = None,
    zone: Optional[str] = None,
    segment_id: Optional[str] = None,
    component_type: Optional[str] = None,
    group_id: Optional[str] = None,
    scope: Optional[str] = None,
    origin: Optional[str] = None,
    construction_status: Optional[str] = None,
    acceptance_status: Optional[str] = None,
    stage_definition_id: Optional[str] = None,
    batch_id: Optional[str] = None,
) -> List[dict[str, Any]]:
    rows = _load_rows(
        db,
        project_id,
        q=q,
        zone=zone,
        segment_id=segment_id,
        component_type=component_type,
        group_id=group_id,
        scope=scope,
        origin=origin,
        batch_id=batch_id,
    )
    if construction_status:
        rows = [row for row in rows if row["construction_status"] == construction_status]
    if acceptance_status:
        rows = [row for row in rows if row["acceptance_status"] == acceptance_status]
    if stage_definition_id:
        rows = [
            row
            for row in rows
            if any(
                stage["stage_definition_id"] == stage_definition_id
                for stage in row["stages"]
            )
        ]
    return rows


def _selection_map(payload: BulkProgressIn) -> dict[str, str]:
    return {item.component_id: item.stage_id for item in payload.stage_selections}


def _apply_stage(
    rows: List[dict[str, Any]], stage_definition_id: str, selections: dict[str, str]
) -> tuple[List[dict[str, Any]], List[str], List[str], List[str]]:
    missing_stage: List[str] = []
    ambiguous_stage: List[str] = []
    invalid_stage: List[str] = []
    for row in rows:
        options = [
            item
            for item in row["stages"]
            if item["stage_definition_id"] == stage_definition_id
        ]
        row["stage_options"] = options
        row["stage_ambiguous"] = len(options) > 1
        row["stage_id"] = None
        row["stage_available"] = False
        selected = selections.get(row["id"])
        if selected is not None:
            stage = next((item for item in options if item["id"] == selected), None)
            if stage is None:
                invalid_stage.append(row["id"])
            else:
                row["stage_id"] = stage["id"]
                row["stage_available"] = True
        elif len(options) == 1:
            row["stage_id"] = options[0]["id"]
            row["stage_available"] = True
        elif not options:
            missing_stage.append(row["id"])
        else:
            # Never pick the first of several scopes; require an explicit choice.
            ambiguous_stage.append(row["id"])
    return rows, missing_stage, ambiguous_stage, invalid_stage


def preview_bulk(
    db: Session, project_id: str, payload: BulkProgressPreviewIn
) -> dict[str, Any]:
    if validate_evidence_refs is not None:
        validate_evidence_refs(db, project_id, payload.evidence_refs)
    rows = _load_rows(db, project_id, component_ids=payload.component_ids)
    found = {row["id"] for row in rows}
    missing = [item for item in payload.component_ids if item not in found]
    definition = db.scalar(
        select(StageDefinition).where(
            StageDefinition.id == payload.stage_definition_id,
            StageDefinition.project_id == project_id,
        )
    )
    rows, missing_stage, ambiguous_stage, invalid_stage = _apply_stage(
        rows, payload.stage_definition_id, _selection_map(payload)
    )
    warnings: List[str] = []
    if definition is None:
        warnings.append("Bước thi công không thuộc công trình này.")
    if missing:
        warnings.append(
            f"{len(missing)} cấu kiện không thuộc công trình hoặc đã bị xóa."
        )
    if missing_stage:
        warnings.append(
            f"{len(missing_stage)} cấu kiện chưa gắn bước thi công đã chọn."
        )
    if ambiguous_stage:
        warnings.append(
            f"{len(ambiguous_stage)} cấu kiện có nhiều bước cùng định nghĩa; chọn đúng stage_id cho từng cấu kiện."
        )
    if invalid_stage:
        warnings.append(
            f"{len(invalid_stage)} lựa chọn bước không khớp cấu kiện hoặc định nghĩa đã chọn."
        )
    return {
        "stage_definition_id": payload.stage_definition_id,
        "components": rows,
        "missing_component_ids": missing,
        "missing_stage_component_ids": missing_stage,
        "ambiguous_stage_component_ids": ambiguous_stage,
        "invalid_stage_component_ids": invalid_stage,
        "warnings": warnings,
        "can_commit": bool(rows)
        and definition is not None
        and not missing
        and not missing_stage
        and not ambiguous_stage
        and not invalid_stage,
        "count": len(rows),
        "ready_count": sum(1 for row in rows if row["stage_available"]),
    }


def _payload_hash(payload: BulkProgressCommitIn) -> str:
    data = payload.model_dump(mode="json", exclude={"reviewed", "idempotency_key"})
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def _previous_result(
    db: Session, project_id: str, key: str, digest: str
) -> Optional[dict[str, Any]]:
    previous = db.scalar(
        select(SiteProgressBulkBatch).where(
            SiteProgressBulkBatch.project_id == project_id,
            SiteProgressBulkBatch.idempotency_key == key,
        )
    )
    if previous is None:
        return None
    if previous.payload_hash != digest:
        raise ProgressSelectionConflict(
            "Idempotency key already used for different progress data"
        )
    return json.loads(previous.result_json or "{}")


def _event_out(event: ProgressEvent, component_id: str) -> dict[str, Any]:
    created_at = event.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return {
        "id": event.id,
        "component_id": component_id,
        "stage_id": event.component_stage_id,
        "event_date": event.event_date,
        "status": event.status,
        "quantity": event.quantity,
        "unit": event.unit,
        "note": event.note,
        "evidence_refs": json.loads(event.evidence_refs or "[]"),
        "batch_id": event.batch_id,
        "created_at": created_at,
    }


def _line_preview_payload(
    line: DailyProgressLineIn, event_date: date
) -> BulkProgressPreviewIn:
    return BulkProgressPreviewIn(
        stage_definition_id=line.stage_definition_id,
        component_ids=line.component_ids,
        stage_selections=line.stage_selections,
        event_date=event_date,
        status=line.status,
        quantity=None,
        unit=None,
        note=None,
        evidence_refs=[],
    )


def _line_commit_payload(
    line: DailyProgressLineIn, event_date: date, key: str, index: int
) -> BulkProgressCommitIn:
    # A per-line key keeps the existing bulk batch rows unique while the daily
    # wrapper owns the caller's idempotency key.
    digest = hashlib.sha256(key.encode()).hexdigest()[:32]
    return BulkProgressCommitIn(
        stage_definition_id=line.stage_definition_id,
        component_ids=line.component_ids,
        stage_selections=line.stage_selections,
        event_date=event_date,
        status=line.status,
        quantity=None,
        unit=None,
        note=None,
        evidence_refs=[],
        reviewed=True,
        idempotency_key=f"daily-{digest}-{index}",
    )


def _duplicate_stage_ids(previews: List[dict[str, Any]]) -> List[str]:
    seen: set[str] = set()
    duplicates: List[str] = []
    for preview in previews:
        for row in preview["components"]:
            stage_id = row.get("stage_id")
            if not stage_id:
                continue
            if stage_id in seen and stage_id not in duplicates:
                duplicates.append(stage_id)
            seen.add(stage_id)
    return duplicates


def _daily_payload_hash(payload: DailyProgressCommitIn) -> str:
    data = payload.model_dump(mode="json", exclude={"reviewed", "idempotency_key"})
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def preview_daily(
    db: Session, project_id: str, payload: DailyProgressIn
) -> dict[str, Any]:
    lines: List[dict[str, Any]] = []
    warnings: List[str] = []
    definition_names = {
        definition.id: definition.name
        for definition in db.scalars(
            select(StageDefinition).where(
                StageDefinition.id.in_(
                    [line.stage_definition_id for line in payload.lines]
                )
            )
        )
    }
    all_component_ids = [
        component_id for line in payload.lines for component_id in line.component_ids
    ]
    t_values = load_t_values(db, all_component_ids)
    for index, line in enumerate(payload.lines):
        preview = preview_bulk(
            db, project_id, _line_preview_payload(line, payload.event_date)
        )
        lines.append(
            {
                **preview,
                "line_index": index,
                "stage_display_name": display_stage_name(
                    definition_names.get(line.stage_definition_id, ""),
                    [t_values.get(component_id) for component_id in line.component_ids],
                ),
                "group_quantity": line.group_quantity,
                "group_unit": line.group_unit,
            }
        )
        warnings.extend(f"Dòng {index + 1}: {item}" for item in preview["warnings"])
    duplicates = _duplicate_stage_ids(lines)
    if duplicates:
        warnings.append(
            f"{len(duplicates)} bước thi công bị trùng giữa các dòng; "
            "mỗi bước chỉ được ghi một lần."
        )
    return {
        "can_commit": all(item["can_commit"] for item in lines) and not duplicates,
        "lines": lines,
        "warnings": warnings,
    }


def commit_daily(
    db: Session,
    project_id: str,
    payload: DailyProgressCommitIn,
    actor_id: Optional[str],
) -> dict[str, Any]:
    digest = _daily_payload_hash(payload)
    previous = _previous_result(db, project_id, payload.idempotency_key, digest)
    if previous is not None:
        return previous

    # Validate every line before the first write, then revalidate each line
    # inside the same transaction through commit_bulk.
    previews: List[dict[str, Any]] = []
    for index, line in enumerate(payload.lines):
        previews.append(
            preview_bulk(db, project_id, _line_preview_payload(line, payload.event_date))
        )
        if not previews[-1]["can_commit"]:
            raise ProgressSelectionConflict(
                f"Daily progress line {index + 1} no longer matches; preview again"
            )
    duplicates = _duplicate_stage_ids(previews)
    if duplicates:
        raise ProgressSelectionConflict(
            "Duplicate stage IDs resolved across daily lines; preview again"
        )

    try:
        batch = SiteProgressBulkBatch(
            project_id=project_id,
            idempotency_key=payload.idempotency_key,
            payload_hash=digest,
            created_by=actor_id,
        )
        db.add(batch)
        db.flush()

        line_results: List[dict[str, Any]] = []
        resolved: dict[str, int] = {}
        for index, line in enumerate(payload.lines):
            result = commit_bulk(
                db,
                project_id,
                _line_commit_payload(
                    line, payload.event_date, payload.idempotency_key, index
                ),
                actor_id,
                commit=False,
                batch_id=batch.id,
            )
            for event in result["events"]:
                stage_id = event["stage_id"]
                if stage_id in resolved:
                    raise ProgressSelectionConflict(
                        "Duplicate stage IDs resolved across daily lines; preview again"
                    )
                resolved[stage_id] = index
            line_results.append(
                {
                    **result,
                    "line_index": index,
                    "stage_definition_id": line.stage_definition_id,
                    "group_quantity": line.group_quantity,
                    "group_unit": line.group_unit,
                }
            )

        daily_result = {
            "created": sum(item["created"] for item in line_results),
            "lines": line_results,
        }
        # Stored verbatim for idempotent retries; group quantities live here and
        # in the audit log, not on individual component events.
        batch.result_json = json.dumps(daily_result, default=str)
        _audit(
            db,
            project_id=project_id,
            actor_id=actor_id,
            action="component_progress_daily_recorded",
            entity="SiteProgressBulkBatch",
            entity_id=batch.id,
            detail=json.dumps(
                {
                    "event_date": payload.event_date.isoformat(),
                    "reviewed": True,
                    "idempotency_key": payload.idempotency_key,
                    "lines": [
                        {
                            "line_index": index,
                            "stage_definition_id": line.stage_definition_id,
                            "component_ids": line.component_ids,
                            "stage_ids": {
                                event["component_id"]: event["stage_id"]
                                for event in line_results[index]["events"]
                            },
                            "status": line.status,
                            "group_quantity": line.group_quantity,
                            "group_unit": line.group_unit,
                        }
                        for index, line in enumerate(payload.lines)
                    ],
                }
            ),
        )
        db.commit()
        return daily_result
    except IntegrityError as exc:
        db.rollback()
        previous = _previous_result(db, project_id, payload.idempotency_key, digest)
        if previous is not None:
            return previous
        raise ProgressSelectionConflict(
            "Concurrent daily progress update conflict; preview again"
        ) from exc
    except Exception:
        db.rollback()
        raise


def commit_bulk(
    db: Session,
    project_id: str,
    payload: BulkProgressCommitIn,
    actor_id: Optional[str],
    *,
    commit: bool = True,
    batch_id: Optional[str] = None,
) -> dict[str, Any]:
    digest = _payload_hash(payload)
    previous = _previous_result(db, project_id, payload.idempotency_key, digest)
    if previous is not None:
        return previous
    if validate_evidence_refs is not None:
        validate_evidence_refs(db, project_id, payload.evidence_refs)

    rows = _load_rows(db, project_id, component_ids=payload.component_ids)
    found = {row["id"] for row in rows}
    missing = [item for item in payload.component_ids if item not in found]
    definition = db.scalar(
        select(StageDefinition).where(
            StageDefinition.id == payload.stage_definition_id,
            StageDefinition.project_id == project_id,
        )
    )
    rows, missing_stage, ambiguous_stage, invalid_stage = _apply_stage(
        rows, payload.stage_definition_id, _selection_map(payload)
    )
    if definition is None or missing or missing_stage:
        raise ProgressSelectionConflict(
            "Reviewed component/stage selection no longer matches; preview again"
        )
    if ambiguous_stage:
        raise ProgressSelectionConflict(
            "Several stages match the selected definition; provide stage_id for each component and preview again"
        )
    if invalid_stage:
        raise ProgressSelectionConflict(
            "Stage selection does not match the component/definition; preview again"
        )

    try:
        batch = SiteProgressBulkBatch(
            project_id=project_id,
            idempotency_key=payload.idempotency_key,
            payload_hash=digest,
            created_by=actor_id,
        )
        db.add(batch)
        db.flush()
        events: List[tuple[ProgressEvent, str]] = []
        for row in rows:
            event = ProgressEvent(
                component_id=row["id"],
                component_stage_id=row["stage_id"],
                event_date=payload.event_date,
                status=payload.status,
                quantity=payload.quantity,
                unit=payload.unit,
                note=payload.note,
                evidence_refs=json.dumps(payload.evidence_refs),
                batch_id=batch_id or batch.id,
                created_by=actor_id,
            )
            db.add(event)
            events.append((event, row["id"]))
        db.flush()
        result = {
            "created": len(events),
            "batch_id": batch.id,
            "events": [_event_out(event, component_id) for event, component_id in events],
            "missing_component_ids": [],
            "missing_stage_component_ids": [],
            "warnings": [],
        }
        # The stored copy is replayed verbatim on idempotent retries.
        batch.result_json = json.dumps(result, default=str)
        _audit(
            db,
            project_id=project_id,
            actor_id=actor_id,
            action="component_progress_bulk_recorded",
            entity="SiteProgressBulkBatch",
            entity_id=batch.id,
            detail=json.dumps(
                {
                    "component_ids": payload.component_ids,
                    "stage_definition_id": payload.stage_definition_id,
                    "stage_ids": {row["id"]: row["stage_id"] for row in rows},
                    "event_date": payload.event_date.isoformat(),
                    "status": payload.status,
                    "reviewed": True,
                }
            ),
        )
        if commit:
            db.commit()
        return result
    except IntegrityError as exc:
        db.rollback()
        previous = _previous_result(db, project_id, payload.idempotency_key, digest)
        if previous is not None:
            return previous
        raise ProgressSelectionConflict(
            "Concurrent progress update conflict; preview again"
        ) from exc


def _local_date(value: Optional[datetime]) -> Optional[date]:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(LOCAL_TZ).date()


def _can_manage_progress(
    db: Session, project_id: str, user: Any, owner_id: Optional[str]
) -> bool:
    """Creator, project_manager or global admin may void/correct."""
    if getattr(user, "role", None) == "admin":
        return True
    if owner_id and getattr(user, "id", None) == owner_id:
        return True
    member = db.scalar(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == getattr(user, "id", None),
        )
    )
    return member is not None and member.role == "project_manager"


def _acceptance_events(
    db: Session, project_id: str, journal_date: date
) -> List[dict[str, Any]]:
    try:
        from app.acceptance.models import AcceptanceRecord, AcceptanceRequest

        rows = db.execute(
            select(AcceptanceRecord, AcceptanceRequest.number)
            .join(AcceptanceRequest, AcceptanceRecord.request_id == AcceptanceRequest.id)
            .where(
                AcceptanceRecord.project_id == project_id,
                AcceptanceRecord.status == "confirmed",
            )
        ).all()
    except Exception:  # pragma: no cover - acceptance module not available
        return []
    events = []
    for record, request_number in rows:
        if _local_date(record.confirmed_at) != journal_date:
            continue
        events.append(
            {
                "id": record.id,
                "number": record.number,
                "request_number": request_number,
                "result": record.result,
                "confirmed_at": (
                    record.confirmed_at.isoformat() if record.confirmed_at else None
                ),
                "record_date": (
                    record.record_date.isoformat() if record.record_date else None
                ),
            }
        )
    return events


def _photo_ref_id(ref: Any) -> Optional[str]:
    value = str(ref or "").strip()
    if value.lower().startswith("photo:"):
        value = value.split(":", 1)[1].strip()
    if not value or ":" in value:
        return None
    return value


def _journal_evidence(
    db: Session,
    project_id: str,
    report: Any,
    construction_events: List[dict[str, Any]],
) -> tuple[List[dict[str, Any]], List[dict[str, Any]]]:
    """Resolve confirmed photo evidence only; never trust a bare reference."""
    report_photos = list_photos(db, project_id, report_id=report.id) if report else []
    omitted: List[dict[str, Any]] = []
    wanted: dict[str, dict[str, Any]] = {}
    for photo in report_photos:
        if photo_evidence_ready(photo):
            wanted[photo.id] = {
                "photo": photo,
                "sources": ["daily_report"],
            }
        else:
            omitted.append(
                {
                    "ref": f"report_photo:{photo.id}",
                    "reason": "unconfirmed_photo",
                }
            )
    refs_by_event: List[tuple[str, str]] = []
    for event in construction_events:
        for ref in event.get("evidence_refs") or []:
            photo_id = _photo_ref_id(ref)
            if photo_id:
                refs_by_event.append((photo_id, event["event_id"]))
            else:
                omitted.append(
                    {
                        "ref": str(ref),
                        "reason": "not_a_photo_reference",
                        "event_id": event["event_id"],
                    }
                )
    ids = {photo_id for photo_id, _ in refs_by_event}
    photos = {
        photo.id: photo
        for photo in db.scalars(
            select(SitePhoto).where(
                SitePhoto.project_id == project_id,
                SitePhoto.id.in_(ids),
            )
        )
    } if ids else {}
    for photo_id, event_id in refs_by_event:
        photo = photos.get(photo_id)
        if photo is None:
            omitted.append(
                {
                    "ref": f"photo:{photo_id}",
                    "reason": "photo_not_found",
                    "event_id": event_id,
                }
            )
            continue
        if not photo_evidence_ready(photo):
            omitted.append(
                {
                    "ref": f"photo:{photo_id}",
                    "reason": "unconfirmed_photo",
                    "event_id": event_id,
                }
            )
            continue
        item = wanted.get(photo.id)
        if item is None:
            wanted[photo.id] = {"photo": photo, "sources": []}
            item = wanted[photo.id]
        source = f"progress_event:{event_id}"
        if source not in item["sources"]:
            item["sources"].append(source)

    evidence = []
    for photo_id, item in wanted.items():
        photo = item["photo"]
        evidence.append(
            {
                "photo_id": photo.id,
                "sha256": photo.sha256,
                "filename": photo.filename,
                "mime_type": photo.mime_type,
                "caption": photo.confirmed_caption or photo.category,
                "category": photo.category,
                "confirmed_caption": photo.confirmed_caption,
                "location": photo.location,
                "component": photo_component_label(db, photo),
                "stage": photo.stage,
                "sources": item["sources"],
            }
        )
    return evidence, omitted


def _journal_hash(preview: dict[str, Any]) -> str:
    core = {
        key: value
        for key, value in preview.items()
        if key not in {"preview_sha256", "preview_text"}
    }
    return sha256_bytes(
        json.dumps(
            core, ensure_ascii=False, sort_keys=True, default=str
        ).encode("utf-8")
    )


def render_journal_text(
    preview: dict[str, Any], hash_value: Optional[str] = None
) -> str:
    report = preview.get("daily_report")
    report_status = (
        "Đã duyệt"
        if report and report.get("status") == "reviewed"
        else "Nháp" if report else "Chưa có báo cáo ngày"
    )
    journal = preview.get("journal") or {}
    lines = [
        preview.get("project_title") or "NHẬT KÝ THI CÔNG",
        f"Ngày: {preview.get('date_display') or preview.get('date')}",
        f"Báo cáo ngày: {report_status}",
        "",
        "1. Thời tiết",
        f"- {journal.get('weather') or 'Chưa ghi nhận'}",
        "",
        "2. Thiết bị",
        f"- {journal.get('equipment') or 'Chưa ghi nhận'}",
        "",
        "3. Nhân lực",
    ]
    manpower = journal.get("manpower") or []
    if manpower:
        for item in manpower:
            count = "chưa rõ" if item.get("count") is None else str(item["count"])
            person = f" - {item['person_name']}" if item.get("person_name") else ""
            lines.append(f"- {item.get('group_name')}{person}: {count}")
    else:
        lines.append("- Chưa ghi nhận")
    lines.extend(["", "4. Công việc trong ngày"])
    work = journal.get("work") or []
    if work:
        for item in work:
            if item.get("source") == "progress_event":
                label = f"{item.get('canonical_code')} · {item.get('stage') or 'Chưa rõ bước'}"
                status = JOURNAL_PROGRESS_STATUS_LABELS.get(
                    str(item.get("status") or "").lower(), item.get("status")
                )
            else:
                label = item.get("work_name") or item.get("work_item_id") or "Công việc"
                status = WORK_STATUS_LABELS.get(
                    str(item.get("status") or "").lower(), item.get("status")
                )
            line = f"- {label}"
            if item.get("location"):
                line += f" tại {item['location']}"
            if item.get("quantity") is not None:
                line += (
                    f": {item['quantity']} {item.get('unit') or ''}".rstrip()
                )
            if status:
                line += f" ({status})"
            if item.get("notes"):
                line += f" - {item['notes']}"
            lines.append(line)
    else:
        lines.append("- Chưa ghi nhận")
    lines.extend(["", "5. Nghiệm thu trong ngày"])
    acceptance = journal.get("acceptance") or []
    if acceptance:
        result_labels = {
            "approved": "Đạt",
            "conditional": "Đạt có điều kiện",
            "rejected": "Không đạt",
        }
        for item in acceptance:
            label = result_labels.get(str(item.get("result") or ""), item.get("result") or "Chưa có kết luận")
            pieces = [f"BBNT {item.get('number') or '—'}"]
            if item.get("request_number"):
                pieces.append(f"PYC {item['request_number']}")
            pieces.append(str(label))
            lines.append(f"- {' · '.join(pieces)}")
    else:
        lines.append("- Chưa có BBNT đã xác nhận trong ngày")
    lines.extend(
        [
            "",
            "6. Vướng mắc",
            f"- {journal.get('issues') or 'Chưa ghi nhận'}",
            "",
            "7. Thay đổi thiết kế",
            "- Chưa có dữ liệu; không tự điền",
            "",
            "8. An toàn lao động",
            f"- {journal.get('safety') or 'Chưa ghi nhận'}",
            "",
            "9. Môi trường",
            "- Chưa có dữ liệu; không tự điền",
            "",
            "10. Hình ảnh / chứng cứ",
        ]
    )
    evidence = preview.get("evidence") or []
    if evidence:
        for item in evidence:
            label = (
                item.get("caption")
                or item.get("filename")
                or item.get("photo_id")
            )
            if item.get("sha256"):
                label += f" · sha256 {str(item['sha256'])[:12]}…"
            lines.append(f"- {label}")
    else:
        lines.append("- Chưa có ảnh đã xác nhận")
    summary = preview.get("evidence_summary") or {}
    if summary.get("omitted_evidence_count"):
        lines.append(
            f"({summary['omitted_evidence_count']} tham chiếu chứng cứ chưa xác nhận hoặc không phân giải được đã bỏ qua)"
        )
    if preview.get("warnings"):
        lines.extend(["", "Cảnh báo:"])
        for warning in preview["warnings"]:
            lines.append(f"- {warning}")
    lines.extend(
        [
            "",
            f"SHA-256: {hash_value or preview.get('preview_sha256') or ''}",
            "Không tự động gửi.",
        ]
    )
    return "\n".join(lines)


def journal_preview(db: Session, project_id: str, journal_date: date) -> dict[str, Any]:
    from .service import get_report

    report = get_report(db, project_id, journal_date)
    warnings: List[str] = []
    blockers: List[str] = []
    notes: dict[str, Any] = {}
    manpower: List[dict[str, Any]] = []
    work: List[dict[str, Any]] = []
    report_out = None
    if report is None:
        warnings.append(
            "Chưa có báo cáo ngày; mục nhân lực và công việc từ báo cáo để trống."
        )
    else:
        notes = site_notes_from_report(report)
        if report.status != "reviewed":
            warnings.append(
                "Báo cáo ngày chưa được duyệt; chỉ xem trước, không dùng để xuất."
            )
            blockers.append("DAILY_REPORT_NOT_REVIEWED")
        names = work_item_names(
            db, project_id, [log.work_item_id for log in report.work_logs]
        )
        manpower = [
            {
                "group_name": entry.group_name,
                "person_name": entry.person_name,
                "count": entry.count,
                "organization_id": entry.organization_id,
            }
            for entry in report.manpower_entries
        ]
        for log in report.work_logs:
            work.append(
                {
                    "source": "daily_report",
                    "id": log.id,
                    "work_item_id": log.work_item_id,
                    "work_name": names.get(log.work_item_id or "")
                    or log.work_name,
                    "location": log.location,
                    "component": log.component,
                    "quantity": log.quantity,
                    "unit": log.unit,
                    "status": log.status,
                    "notes": log.notes,
                }
            )
        report_out = {
            "id": report.id,
            "status": report.status,
            "site_notes": notes,
            "manpower": manpower,
            "work_logs": list(work),
        }

    construction_events: List[dict[str, Any]] = []
    if ProgressEvent is not None:
        records = db.execute(
            select(
                ProgressEvent,
                ComponentStage,
                StageDefinition,
                StructuralComponent,
                Segment,
                StructureZone,
            )
            .join(
                ComponentStage,
                ProgressEvent.component_stage_id == ComponentStage.id,
            )
            .join(
                StageDefinition,
                ComponentStage.stage_definition_id == StageDefinition.id,
            )
            .join(
                StructuralComponent,
                ComponentStage.component_id == StructuralComponent.id,
            )
            .join(Segment, StructuralComponent.segment_id == Segment.id)
            .join(StructureZone, Segment.zone_id == StructureZone.id)
            .where(
                StructuralComponent.project_id == project_id,
                ProgressEvent.event_date == journal_date,
                ProgressEvent.voided_at.is_(None),
                StageDefinition.project_id == project_id,
            )
            .order_by(
                ProgressEvent.created_at,
                StructuralComponent.canonical_code,
            )
        ).all()
        journal_t_values = load_t_values(
            db, [component.id for _, _, _, component, _, _ in records]
        )
        for event, stage, definition, component, segment, area in records:
            stage_name = display_stage_name(
                definition.name, [journal_t_values.get(component.id)]
            )
            construction_events.append(
                {
                    "event_id": event.id,
                    "component_id": component.id,
                    "canonical_code": component.canonical_code,
                    "zone": area.name,
                    "segment_number": segment.number,
                    "stage_id": stage.id,
                    "stage_code": definition.code,
                    "stage_name": stage_name,
                    "status": event.status,
                    "quantity": event.quantity,
                    "unit": event.unit,
                    "note": event.note,
                    "evidence_refs": json.loads(event.evidence_refs or "[]"),
                }
            )
            work.append(
                {
                    "source": "progress_event",
                    "id": event.id,
                    "component_id": component.id,
                    "canonical_code": component.canonical_code,
                    "location": f"{area.name} · PĐ {segment.number}",
                    "stage": stage_name,
                    "status": event.status,
                    "quantity": event.quantity,
                    "unit": event.unit,
                    "notes": event.note,
                }
            )
    if not construction_events:
        warnings.append("Chưa có sự kiện thi công trong ngày; mục thi công để trống.")

    acceptance_events = _acceptance_events(db, project_id, journal_date)
    if not acceptance_events:
        warnings.append(
            "Chưa có BBNT đã xác nhận trong ngày; mục nghiệm thu để trống."
        )
    warnings.append(
        "Không tự điền thay đổi thiết kế hoặc môi trường khi chưa có dữ liệu."
    )

    sections = {
        "weather": notes.get("weather"),
        "equipment": notes.get("equipment"),
        "manpower": manpower,
        "work": work,
        "acceptance": acceptance_events,
        "issues": notes.get("difficulties"),
        "design_changes": None,
        "safety": notes.get("safety"),
        "environment": None,
    }
    blank_sections = [
        key for key, value in sections.items() if value is None or value == [] or value == ""
    ]
    evidence, omitted_evidence = _journal_evidence(
        db, project_id, report, construction_events
    )
    preview: dict[str, Any] = {
        "project_id": project_id,
        "project_title": project_report_title(db, project_id),
        "date": journal_date.isoformat(),
        "date_display": format_report_date(journal_date),
        "reviewed_only": True,
        "snapshot_eligible": not blockers,
        "blockers": blockers,
        "daily_report": report_out,
        "construction_events": construction_events,
        "acceptance_events": acceptance_events,
        "acceptance_count": len(acceptance_events),
        "journal": sections,
        "blank_sections": blank_sections,
        "warnings": warnings,
        "evidence": evidence,
        "omitted_evidence_refs": omitted_evidence,
        "evidence_summary": {
            "evidence_count": len(evidence),
            "omitted_evidence_count": len(omitted_evidence),
        },
    }
    preview["preview_sha256"] = _journal_hash(preview)
    preview["preview_text"] = render_journal_text(preview)
    return preview


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/projects/{project_id}/progress", response_model=List[ProgressRowOut])
def get_progress(
    project_id: str,
    q: Optional[str] = None,
    zone: Optional[str] = None,
    segment_id: Optional[str] = None,
    type: Optional[Literal["pile", "beam"]] = None,
    group_id: Optional[str] = None,
    scope: Optional[Literal["DESIGN_SCOPE", "ADDITIONAL_SCOPE"]] = None,
    origin: Optional[Literal["SEED_IMPORT", "MANUAL_ENTRY"]] = None,
    stage_definition_id: Optional[str] = None,
    batch_id: Optional[str] = None,
    construction_status: Optional[
        Literal["NOT_STARTED", "IN_PROGRESS", "COMPLETED", "BLOCKED"]
    ] = None,
    acceptance_status: Optional[
        Literal[
            "NOT_LINKED",
            "PENDING",
            "APPROVED",
            "CONDITIONAL",
            "REJECTED",
            "CONFIRMED",
        ]
    ] = None,
    db: Session = Depends(get_db),
    user=Depends(require_project_member),
):
    return list_progress(
        db,
        project_id,
        q=q,
        zone=zone,
        segment_id=segment_id,
        component_type=type,
        group_id=group_id,
        scope=scope,
        origin=origin,
        stage_definition_id=stage_definition_id,
        construction_status=construction_status,
        acceptance_status=acceptance_status,
        batch_id=batch_id,
    )


@router.post(
    "/projects/{project_id}/progress/design-quantities",
    response_model=dict[str, DesignQuantityOut],
)
def get_design_quantities(
    project_id: str,
    payload: DesignQuantityIn,
    db: Session = Depends(get_db),
    user=Depends(require_project_member),
):
    if ComponentStage is None:
        return {}
    rows = db.execute(
        select(ComponentStage.id, ComponentStage.design_quantity)
        .join(StructuralComponent, StructuralComponent.id == ComponentStage.component_id)
        .where(
            StructuralComponent.project_id == project_id,
            StructuralComponent.id.in_(payload.component_ids),
            ComponentStage.design_quantity.is_not(None),
        )
    )
    return {stage_id: quantity for stage_id, quantity in rows if quantity is not None}


@router.post(
    "/projects/{project_id}/progress/bulk-preview",
    response_model=ProgressPreviewOut,
)
def preview_progress_bulk(
    project_id: str,
    payload: BulkProgressPreviewIn,
    db: Session = Depends(get_db),
    user=Depends(require_site_editor),
):
    return preview_bulk(db, project_id, payload)


@router.post(
    "/projects/{project_id}/progress/bulk",
    response_model=ProgressCommitOut,
    status_code=201,
)
def commit_progress_bulk(
    project_id: str,
    payload: BulkProgressCommitIn,
    db: Session = Depends(get_db),
    user=Depends(require_site_editor),
):
    try:
        return commit_bulk(db, project_id, payload, current_user_id(user))
    except ProgressSelectionConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/projects/{project_id}/progress/daily-preview",
    response_model=DailyProgressPreviewOut,
)
def preview_progress_daily(
    project_id: str,
    payload: DailyProgressIn,
    db: Session = Depends(get_db),
    user=Depends(require_site_editor),
):
    return preview_daily(db, project_id, payload)


@router.post(
    "/projects/{project_id}/progress/daily",
    response_model=DailyProgressCommitOut,
    status_code=201,
)
def commit_progress_daily(
    project_id: str,
    payload: DailyProgressCommitIn,
    db: Session = Depends(get_db),
    user=Depends(require_site_editor),
):
    try:
        return commit_daily(db, project_id, payload, current_user_id(user))
    except ProgressSelectionConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/projects/{project_id}/progress/batches/{batch_id}/undo")
def undo_progress_batch(
    project_id: str,
    batch_id: str,
    payload: ProgressBatchUndoIn,
    db: Session = Depends(get_db),
    user=Depends(require_site_editor),
):
    batch = db.scalar(
        select(SiteProgressBulkBatch).where(
            SiteProgressBulkBatch.id == batch_id,
            SiteProgressBulkBatch.project_id == project_id,
        )
    )
    if batch is None:
        raise HTTPException(status_code=404, detail="Progress batch not found")
    if _local_date(batch.created_at) != datetime.now(LOCAL_TZ).date():
        raise HTTPException(
            status_code=409,
            detail="Chỉ hoàn tác được đợt ghi trong cùng ngày.",
        )
    if not _can_manage_progress(db, project_id, user, batch.created_by):
        raise HTTPException(
            status_code=403,
            detail="Chỉ người tạo đợt hoặc quản lý công trình được hoàn tác.",
        )
    events = list(
        db.scalars(
            select(ProgressEvent).where(
                ProgressEvent.batch_id == batch.id,
                ProgressEvent.voided_at.is_(None),
            )
        )
    )
    if not events:
        raise HTTPException(
            status_code=409,
            detail="Đợt này không còn sự kiện tiến độ nào để hoàn tác.",
        )
    voided_at = datetime.now(timezone.utc)
    for event in events:
        event.voided_at = voided_at
        event.voided_by = current_user_id(user)
        event.void_reason = payload.reason.strip()
    _audit(
        db,
        project_id=project_id,
        actor_id=current_user_id(user),
        action="component_progress_batch_voided",
        entity="SiteProgressBulkBatch",
        entity_id=batch.id,
        detail=json.dumps(
            {
                "voided": len(events),
                "event_ids": [event.id for event in events],
                "reason": payload.reason.strip(),
            }
        ),
    )
    db.commit()
    return {"batch_id": batch.id, "voided": len(events)}


@router.post("/projects/{project_id}/progress/events/{event_id}/correct")
def correct_progress_event(
    project_id: str,
    event_id: str,
    payload: ProgressEventCorrectIn,
    db: Session = Depends(get_db),
    user=Depends(require_site_editor),
):
    row = db.execute(
        select(ProgressEvent, StructuralComponent)
        .join(StructuralComponent, ProgressEvent.component_id == StructuralComponent.id)
        .where(
            ProgressEvent.id == event_id,
            StructuralComponent.project_id == project_id,
            ProgressEvent.voided_at.is_(None),
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Progress event not found")
    event, component = row
    if event.status == payload.status:
        raise HTTPException(
            status_code=409, detail="Trạng thái mới trùng trạng thái hiện tại."
        )
    if not _can_manage_progress(db, project_id, user, event.created_by):
        raise HTTPException(
            status_code=403,
            detail="Chỉ người ghi sự kiện hoặc quản lý công trình được sửa.",
        )
    reason = payload.reason.strip()
    voided_at = datetime.now(timezone.utc)
    event.voided_at = voided_at
    event.voided_by = current_user_id(user)
    event.void_reason = reason
    replacement = ProgressEvent(
        component_id=event.component_id,
        component_stage_id=event.component_stage_id,
        event_date=event.event_date,
        status=payload.status,
        quantity=event.quantity,
        unit=event.unit,
        note=event.note,
        evidence_refs=event.evidence_refs,
        batch_id=None,
        created_by=current_user_id(user),
    )
    db.add(replacement)
    db.flush()
    _audit(
        db,
        project_id=project_id,
        actor_id=current_user_id(user),
        action="component_progress_event_voided",
        entity="ProgressEvent",
        entity_id=event.id,
        detail=json.dumps(
            {
                "reason": reason,
                "from_status": event.status,
                "replacement_event_id": replacement.id,
            }
        ),
    )
    _audit(
        db,
        project_id=project_id,
        actor_id=current_user_id(user),
        action="component_progress_event_corrected",
        entity="ProgressEvent",
        entity_id=replacement.id,
        detail=json.dumps(
            {
                "old_event_id": event.id,
                "component_id": component.id,
                "from_status": event.status,
                "to_status": replacement.status,
                "reason": reason,
            }
        ),
    )
    db.commit()
    return _event_out(replacement, component.id)


@router.get("/projects/{project_id}/journals/{journal_date}/preview")
def generate_journal_preview(
    project_id: str,
    journal_date: date,
    db: Session = Depends(get_db),
    user=Depends(require_project_member),
):
    return journal_preview(db, project_id, journal_date)
