import hashlib
import json
import base64
import re
import unicodedata
from datetime import date
from io import BytesIO
from typing import Literal
from zipfile import ZipFile, is_zipfile

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .access import require_project_member, require_project_role
from .batch_scope import batch_component_ids
from .component_models import (ComponentAlias, ComponentImportBatch, ComponentStage, ComponentWorkLink, DesignGroup,
                               ProgressEvent, RepairScope, Segment, StageDefinition, StructuralComponent, StructureZone)
from .component_seed import preview_seed
from .database import get_db
from .design_parameters import display_stage_name, load_parameters, load_t_values
from .evidence import validate_evidence_refs
from .models import AuditLog, now

router = APIRouter(tags=["components"])


def zone_key(value: str) -> str:
    return unicodedata.normalize("NFKC", value).strip().casefold()


class Candidate(BaseModel):
    source_id: str = Field(min_length=1, max_length=160)
    source_row: int = Field(ge=5)
    zone: str = Field(min_length=1, max_length=255)
    type: Literal["pile", "beam"]
    segment: int = Field(ge=1)
    design_group: str | None = Field(max_length=120)
    canonical_code: str = Field(min_length=1, max_length=120)
    raw_code: str = Field(min_length=1, max_length=120)
    scope: Literal["DESIGN_SCOPE", "ADDITIONAL_SCOPE"]
    drawing: str = Field(max_length=120)
    source: str
    verification: Literal["NEEDS_REVIEW"]
    aliases: list[str] = Field(default_factory=list, max_length=20)


class Link(BaseModel):
    source_id: str
    code: str
    dm_row: int = Field(ge=1)
    seed_row: int = Field(ge=5)
    work: str
    raw_location: str


class SegmentCandidate(BaseModel):
    source_id: str = Field(min_length=1, max_length=120)
    zone: str = Field(min_length=1, max_length=255)
    number: int = Field(ge=1)


class Preview(BaseModel):
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    components: list[Candidate] = Field(max_length=5000)
    work_links: list[Link] = Field(max_length=50000)
    segments: list[SegmentCandidate] = Field(max_length=1000)
    conflicts: list[str] = []


class Commit(BaseModel):
    reviewed: Literal[True]
    idempotency_key: str = Field(min_length=1, max_length=120)
    preview: Preview
    source_file_base64: str = Field(max_length=14 * 1024 * 1024)


class ComponentCreate(BaseModel):
    segment_id: str = Field(min_length=1, max_length=36)
    type: Literal["pile", "beam"]
    raw_code: str = Field(min_length=1, max_length=120)
    canonical_code: str = Field(min_length=1, max_length=120)
    scope: Literal["DESIGN_SCOPE", "ADDITIONAL_SCOPE"]
    design_group_id: str | None = Field(default=None, max_length=36)
    approval_reference: str | None = Field(default=None, max_length=1000)
    aliases: list[str] = Field(default_factory=list, max_length=20)


class StageDefinitionCreate(BaseModel):
    type: Literal["pile", "beam"]
    code: str = Field(min_length=1, max_length=60)
    name: str = Field(min_length=1, max_length=255)
    position: int = Field(default=0, ge=0, le=10000)


class RepairScopeCreate(BaseModel):
    kind: Literal["DESIGN_SCOPE", "ADDITIONAL_SCOPE"]
    approval_reference: str | None = Field(default=None, max_length=1000)


class RepairScopeReview(BaseModel):
    decision: Literal["VERIFIED", "REJECTED"]
    approval_reference: str | None = Field(default=None, max_length=1000)
    note: str | None = Field(default=None, max_length=1000)


class ComponentStageCreate(BaseModel):
    stage_definition_id: str = Field(min_length=1, max_length=36)
    repair_scope_id: str = Field(min_length=1, max_length=36)


class ProgressEventCreate(BaseModel):
    stage_id: str = Field(min_length=1, max_length=36)
    event_date: date
    status: Literal["IN_PROGRESS", "COMPLETED", "BLOCKED"]
    quantity: float | None = Field(default=None, ge=0, le=1_000_000_000_000)
    unit: str | None = Field(default=None, max_length=30)
    note: str | None = Field(default=None, max_length=2000)
    evidence_refs: list[str] = Field(default_factory=list, max_length=20)


def conflicts(preview: Preview) -> list[str]:
    errors = []
    if not preview.components or not preview.segments:
        errors.append("Empty inventory")
    segments = [(zone_key(s.zone), s.number) for s in preview.segments]
    ids = [c.source_id for c in preview.components]
    keys = [(zone_key(c.zone), c.segment, c.type, c.canonical_code.strip().upper()) for c in preview.components]
    links = [(l.source_id, l.dm_row) for l in preview.work_links]
    aliases = [(zone_key(c.zone), c.segment, c.type, alias.strip().upper()) for c in preview.components for alias in c.aliases]
    if len(segments) != len(set(segments)) or len(ids) != len(set(ids)) or len(keys) != len(set(keys)) or len(links) != len(set(links)):
        errors.append("Duplicate segment, component, source ID or work link")
    if len(aliases) != len(set(aliases)) or any(alias in keys for alias in aliases):
        errors.append("Ambiguous component alias")
    if any((zone_key(c.zone), c.segment) not in segments for c in preview.components) or any(l.source_id not in ids for l in preview.work_links):
        errors.append("Unknown segment or component reference")
    codes = {c.source_id: c.canonical_code for c in preview.components}
    if any(l.source_id in codes and l.code != codes[l.source_id] for l in preview.work_links):
        errors.append("Work link code does not match component")
    if any(c.design_group and (c.type != "pile" or c.scope == "ADDITIONAL_SCOPE") for c in preview.components):
        errors.append("Unconfirmed group on additional scope or non-pile")
    return errors


def parse_uploaded_seed(content: bytes) -> Preview:
    if len(content) > 10 * 1024 * 1024 or not is_zipfile(BytesIO(content)):
        raise HTTPException(422, "Expected an XLSX file up to 10 MB")
    try:
        with ZipFile(BytesIO(content)) as archive:
            if sum(item.file_size for item in archive.infolist()) > 100 * 1024 * 1024:
                raise ValueError("Workbook expands beyond 100 MB")
        result = Preview(**preview_seed(content))
        result.conflicts = conflicts(result)
        return result
    except Exception as exc:
        raise HTTPException(422, "Invalid component seed workbook") from exc


def component_in_project(db: Session, project_id: str, component_id: str) -> StructuralComponent:
    component = db.scalar(select(StructuralComponent).where(
        StructuralComponent.id == component_id, StructuralComponent.project_id == project_id))
    if component is None:
        raise HTTPException(404, "Component not found")
    return component


def scope_data(scope: RepairScope) -> dict:
    return {"id": scope.id, "kind": scope.kind, "revision": scope.revision,
            "verification": scope.verification, "approval_reference": scope.approval_reference,
            "reviewed_by": scope.reviewed_by,
            "reviewed_at": scope.reviewed_at.isoformat() if scope.reviewed_at else None}


def event_data(event: ProgressEvent) -> dict:
    return {"id": event.id, "component_id": event.component_id, "stage_id": event.component_stage_id,
            "event_date": event.event_date.isoformat(), "status": event.status,
            "quantity": event.quantity, "unit": event.unit, "note": event.note,
            "evidence_refs": json.loads(event.evidence_refs or "[]"),
            "batch_id": event.batch_id,
            "created_by": event.created_by, "created_at": event.created_at.isoformat()}


def progress_events_for(db: Session, component_id: str) -> list[ProgressEvent]:
    return list(db.scalars(select(ProgressEvent).where(
        ProgressEvent.component_id == component_id,
        ProgressEvent.voided_at.is_(None)).order_by(
        ProgressEvent.event_date, ProgressEvent.created_at, ProgressEvent.id)))


def stage_definition_for(db: Session, component_id: str, stage_id: str):
    return db.execute(select(ComponentStage, StageDefinition).join(
        StageDefinition, ComponentStage.stage_definition_id == StageDefinition.id).where(
        ComponentStage.id == stage_id, ComponentStage.component_id == component_id)).first()


@router.post("/projects/{project_id}/components/import-preview")
async def import_preview(project_id: str, file: UploadFile = File(...), db: Session = Depends(get_db)):
    require_project_role(project_id, {"project_manager", "engineer"})
    content = await file.read(10 * 1024 * 1024 + 1)
    result = parse_uploaded_seed(content)
    try:
        existing = db.execute(select(StructuralComponent, Segment, StructureZone).join(
            Segment, StructuralComponent.segment_id == Segment.id).join(
            StructureZone, Segment.zone_id == StructureZone.id).where(StructuralComponent.project_id == project_id)).all()
        by_key = {(zone.name_key, segment.number, component.type, component.canonical_code): component
                  for component, segment, zone in existing}
        identifiers = db.execute(select(ComponentAlias, StructuralComponent, Segment, StructureZone).join(
            StructuralComponent, ComponentAlias.component_id == StructuralComponent.id).join(
            Segment, StructuralComponent.segment_id == Segment.id).join(
            StructureZone, Segment.zone_id == StructureZone.id).where(StructuralComponent.project_id == project_id)).all()
        by_key.update({(zone.name_key, segment.number, component.type, alias.alias): component
                       for alias, component, segment, zone in identifiers})
        if any((old := by_key.get((zone_key(c.zone), c.segment, c.type, c.canonical_code.strip().upper()))) and
               (old.source_hash != result.source_sha256 or old.source_id != c.source_id) for c in result.components):
            result.conflicts.append("Existing component requires manual reconciliation")
        if any((old := by_key.get((zone_key(c.zone), c.segment, c.type, alias.strip().upper()))) and
               (old.source_hash != result.source_sha256 or old.source_id != c.source_id)
               for c in result.components for alias in c.aliases):
            result.conflicts.append("Existing component alias requires manual reconciliation")
        return result
    except Exception as exc:
        raise HTTPException(422, "Invalid component seed workbook") from exc


@router.post("/projects/{project_id}/components/import-commit")
def import_commit(project_id: str, payload: Commit, db: Session = Depends(get_db)):
    actor = require_project_role(project_id, {"project_manager", "engineer"})
    preview = payload.preview
    try:
        content = base64.b64decode(payload.source_file_base64, validate=True)
    except ValueError as exc:
        raise HTTPException(422, "Invalid source encoding") from exc
    source_preview = parse_uploaded_seed(content)
    if source_preview.model_dump(exclude={"conflicts"}) != preview.model_dump(exclude={"conflicts"}):
        raise HTTPException(409, "Reviewed data does not match source workbook")
    digest = hashlib.sha256(preview.model_dump_json().encode()).hexdigest()
    previous = db.scalar(select(ComponentImportBatch).where(ComponentImportBatch.project_id == project_id,
                         ComponentImportBatch.idempotency_key == payload.idempotency_key))
    if previous:
        if previous.payload_hash != digest:
            raise HTTPException(409, "Idempotency key already used for different data")
        return json.loads(previous.result)
    if preview.conflicts or conflicts(preview):
        raise HTTPException(409, "Import has unresolved conflicts")
    try:
        zones = {}
        segments = {}
        for item in preview.segments:
            key = zone_key(item.zone)
            if key not in zones:
                zone = db.scalar(select(StructureZone).where(StructureZone.project_id == project_id, StructureZone.name_key == key))
                if not zone:
                    zone = StructureZone(project_id=project_id, name=item.zone.strip(), name_key=key)
                    db.add(zone)
                    db.flush()
                zones[key] = zone
            segment = db.scalar(select(Segment).where(Segment.zone_id == zones[key].id, Segment.number == item.number))
            if not segment:
                segment = Segment(zone_id=zones[key].id, number=item.number, source_code=item.source_id)
                db.add(segment)
                db.flush()
            elif segment.source_code != item.source_id:
                raise HTTPException(409, "Existing segment requires manual reconciliation")
            segments[(key, item.number)] = segment
        components = {}
        for item in preview.components:
            segment = segments[(zone_key(item.zone), item.segment)]
            code = item.canonical_code.strip().upper()
            component = db.scalar(select(StructuralComponent).where(StructuralComponent.project_id == project_id,
                                  StructuralComponent.segment_id == segment.id, StructuralComponent.type == item.type,
                                  StructuralComponent.canonical_code == code))
            if component:
                if component.source_hash != preview.source_sha256 or component.source_id != item.source_id:
                    raise HTTPException(409, "Existing component requires manual reconciliation")
                scope = db.scalar(select(RepairScope).where(RepairScope.component_id == component.id, RepairScope.kind == item.scope))
                group = db.get(DesignGroup, component.design_group_id) if component.design_group_id else None
                stored_aliases = set(db.scalars(select(ComponentAlias.alias).where(ComponentAlias.component_id == component.id)))
                if (not scope or (group.name if group else None) != item.design_group or
                    (group and (group.drawing != item.drawing or group.source != item.source)) or
                    stored_aliases != {code, *(alias.strip().upper() for alias in item.aliases)} or
                    component.source_row != item.source_row or component.raw_code != item.raw_code):
                    raise HTTPException(409, "Existing component details require manual reconciliation")
            else:
                group = None
                if item.design_group:
                    group = db.scalar(select(DesignGroup).where(DesignGroup.project_id == project_id,
                                      DesignGroup.group_type == "PILE_REPAIR_CLASS", DesignGroup.name == item.design_group,
                                      DesignGroup.drawing == item.drawing))
                    if not group:
                        page = re.search(r"\btrang\s+(\d+)\b", item.source, re.IGNORECASE)
                        group = DesignGroup(project_id=project_id, group_type="PILE_REPAIR_CLASS", name=item.design_group,
                                            drawing=item.drawing, source=item.source,
                                            source_page=int(page.group(1)) if page else None)
                        db.add(group)
                        db.flush()
                component = StructuralComponent(project_id=project_id, segment_id=segment.id, type=item.type,
                    raw_code=item.raw_code, canonical_code=code, source_id=item.source_id,
                    source_hash=preview.source_sha256, source_row=item.source_row,
                    design_group_id=group.id if group else None, verification="VERIFIED", created_by=actor.id)
                db.add(component)
                db.flush()
                db.add(RepairScope(component_id=component.id, kind=item.scope, verification="VERIFIED",
                                   reviewed_by=actor.id, reviewed_at=now()))
                for alias in [code, *(alias.strip().upper() for alias in item.aliases)]:
                    db.add(ComponentAlias(component_id=component.id, project_id=project_id,
                                          segment_id=segment.id, type=item.type, alias=alias))
            components[item.source_id] = component
        for link in preview.work_links:
            component = components[link.source_id]
            exists = db.scalar(select(ComponentWorkLink).where(ComponentWorkLink.component_id == component.id,
                               ComponentWorkLink.source_hash == preview.source_sha256, ComponentWorkLink.dm_row == link.dm_row))
            if exists and (exists.work != link.work or exists.raw_location != link.raw_location or exists.seed_row != link.seed_row):
                raise HTTPException(409, "Existing work link requires manual reconciliation")
            if not exists:
                db.add(ComponentWorkLink(component_id=component.id, source_hash=preview.source_sha256,
                       dm_row=link.dm_row, seed_row=link.seed_row, work=link.work, raw_location=link.raw_location))
        result = {"components": len(components), "work_links": len(preview.work_links), "segments": len(segments)}
        batch = ComponentImportBatch(project_id=project_id, idempotency_key=payload.idempotency_key,
                                     payload_hash=digest, result=json.dumps(result))
        db.add(batch)
        db.flush()
        db.add(AuditLog(project_id=project_id, actor_id=actor.id, action="import_reviewed", entity="ComponentImportBatch",
                        entity_id=batch.id, detail=json.dumps({"source_sha256": preview.source_sha256, **result})))
        db.commit()
        return result
    except IntegrityError as exc:
        db.rollback()
        previous = db.scalar(select(ComponentImportBatch).where(ComponentImportBatch.project_id == project_id,
                             ComponentImportBatch.idempotency_key == payload.idempotency_key))
        if previous and previous.payload_hash == digest:
            return json.loads(previous.result)
        raise HTTPException(409, "Concurrent import conflict; preview again") from exc


@router.post("/projects/{project_id}/components", status_code=201)
def create_component(project_id: str, payload: ComponentCreate, db: Session = Depends(get_db)):
    actor = require_project_role(project_id, {"project_manager", "engineer"})
    segment = db.scalar(select(Segment).join(StructureZone, Segment.zone_id == StructureZone.id).where(
        Segment.id == payload.segment_id, StructureZone.project_id == project_id))
    if segment is None:
        raise HTTPException(404, "Segment not found")
    raw_code = payload.raw_code.strip()
    code = payload.canonical_code.strip().upper()
    aliases: list[str] = []
    for alias in [*payload.aliases, raw_code, code]:
        value = alias.strip().upper()
        if not value or len(value) > 120:
            raise HTTPException(422, "Invalid component code or alias")
        if value not in aliases:
            aliases.append(value)
    duplicate = db.scalar(select(StructuralComponent.id).where(
        StructuralComponent.project_id == project_id, StructuralComponent.segment_id == segment.id,
        StructuralComponent.type == payload.type,
        StructuralComponent.canonical_code.in_(aliases) | func.upper(StructuralComponent.raw_code).in_(aliases)))
    alias_taken = db.scalar(select(ComponentAlias.id).where(
        ComponentAlias.project_id == project_id, ComponentAlias.segment_id == segment.id,
        ComponentAlias.type == payload.type, ComponentAlias.alias.in_(aliases)))
    if duplicate or alias_taken:
        raise HTTPException(409, "Component code or alias already exists in this segment")
    group = None
    if payload.design_group_id:
        group = db.scalar(select(DesignGroup).where(
            DesignGroup.id == payload.design_group_id,
            DesignGroup.project_id == project_id,
        ))
        if group is None:
            raise HTTPException(404, "Design group not found")
    record_origin = "MANUAL_ENTRY"
    try:
        component = StructuralComponent(project_id=project_id, segment_id=segment.id, type=payload.type,
            raw_code=raw_code, canonical_code=code, verification="NEEDS_REVIEW",
            record_origin=record_origin, design_group_id=group.id if group else None,
            created_by=actor.id)
        db.add(component)
        db.flush()
        db.add(RepairScope(
            component_id=component.id,
            kind=payload.scope,
            verification="NEEDS_REVIEW",
            revision=1,
            approval_reference=(payload.approval_reference or "").strip() or None,
        ))
        for alias in aliases:
            db.add(ComponentAlias(component_id=component.id, project_id=project_id,
                                  segment_id=segment.id, type=payload.type, alias=alias))
        db.add(AuditLog(project_id=project_id, actor_id=actor.id, action="component_created",
                        entity="StructuralComponent", entity_id=component.id,
                        detail=json.dumps({"canonical_code": code, "raw_code": raw_code,
                                           "segment_id": segment.id, "scope": payload.scope,
                                           "design_group_id": group.id if group else None,
                                           "approval_reference": (payload.approval_reference or "").strip() or None,
                                           "record_origin": record_origin})))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Component code or alias already exists in this segment") from exc
    zone = db.get(StructureZone, segment.zone_id)
    return {"id": component.id, "type": component.type, "raw_code": component.raw_code,
            "canonical_code": component.canonical_code, "segment_id": segment.id,
            "segment_number": segment.number, "zone": zone.name if zone else None,
            "design_group_id": group.id if group else None,
            "design_group": group.name if group else None,
            "aliases": [alias for alias in aliases if alias != code],
            "verification": component.verification, "record_origin": component.record_origin,
            "source": {"sha256": None, "sheet": None, "row": None},
            "scopes": [{"kind": payload.scope, "revision": 1, "verification": "NEEDS_REVIEW",
                        "approval_reference": (payload.approval_reference or "").strip() or None}]}


@router.get("/projects/{project_id}/stage-definitions")
def list_stage_definitions(project_id: str, type: Literal["pile", "beam"] | None = None,
                           db: Session = Depends(get_db)):
    require_project_member(project_id)
    query = select(StageDefinition).where(StageDefinition.project_id == project_id)
    if type:
        query = query.where(StageDefinition.component_type == type)
    return [{"id": item.id, "type": item.component_type, "code": item.code, "name": item.name,
             "position": item.position}
            for item in db.scalars(query.order_by(StageDefinition.position, StageDefinition.code))]


@router.post("/projects/{project_id}/stage-definitions", status_code=201)
def create_stage_definition(project_id: str, payload: StageDefinitionCreate, db: Session = Depends(get_db)):
    actor = require_project_role(project_id, {"project_manager", "engineer"})
    code, name = payload.code.strip().upper(), payload.name.strip()
    if not code or not name:
        raise HTTPException(422, "Invalid stage definition")
    definition = StageDefinition(project_id=project_id, component_type=payload.type, code=code,
                                 name=name, position=payload.position)
    db.add(definition)
    try:
        db.flush()
        db.add(AuditLog(project_id=project_id, actor_id=actor.id, action="stage_definition_created",
                        entity="StageDefinition", entity_id=definition.id,
                        detail=json.dumps({"type": payload.type, "code": code, "name": name,
                                           "position": payload.position})))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Stage definition already exists for this component type") from exc
    return {"id": definition.id, "type": definition.component_type, "code": definition.code,
            "name": definition.name, "position": definition.position}


@router.post("/projects/{project_id}/components/{component_id}/repair-scopes", status_code=201)
def propose_repair_scope(project_id: str, component_id: str, payload: RepairScopeCreate,
                         db: Session = Depends(get_db)):
    actor = require_project_role(project_id, {"project_manager", "engineer"})
    component = component_in_project(db, project_id, component_id)
    latest = db.scalar(select(func.max(RepairScope.revision)).where(
        RepairScope.component_id == component.id, RepairScope.kind == payload.kind))
    scope = RepairScope(component_id=component.id, kind=payload.kind, verification="NEEDS_REVIEW",
                        revision=(latest or 0) + 1,
                        approval_reference=(payload.approval_reference or "").strip() or None)
    db.add(scope)
    try:
        db.flush()
        db.add(AuditLog(project_id=project_id, actor_id=actor.id, action="repair_scope_proposed",
                        entity="RepairScope", entity_id=scope.id,
                        detail=json.dumps({"component_id": component.id, "kind": scope.kind,
                                           "revision": scope.revision})))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Scope revision conflict; retry") from exc
    return scope_data(scope)


@router.post("/projects/{project_id}/components/{component_id}/repair-scopes/{scope_id}/review")
def review_repair_scope(project_id: str, component_id: str, scope_id: str, payload: RepairScopeReview,
                        db: Session = Depends(get_db)):
    actor = require_project_role(project_id, {"project_manager"})
    component = component_in_project(db, project_id, component_id)
    scope = db.scalar(select(RepairScope).where(RepairScope.id == scope_id,
                       RepairScope.component_id == component.id))
    if scope is None:
        raise HTTPException(404, "Repair scope not found")
    if scope.verification != "NEEDS_REVIEW":
        raise HTTPException(409, "Repair scope already reviewed")
    reference = (payload.approval_reference or "").strip() or (scope.approval_reference or "").strip()
    if payload.decision == "VERIFIED" and scope.kind == "ADDITIONAL_SCOPE" and not reference:
        raise HTTPException(422, "Approval reference required for additional scope")
    changed = db.execute(update(RepairScope).where(
        RepairScope.id == scope.id, RepairScope.verification == "NEEDS_REVIEW").values(
        verification=payload.decision, reviewed_by=actor.id, reviewed_at=now(),
        approval_reference=reference or None))
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Repair scope already reviewed")
    db.add(AuditLog(project_id=project_id, actor_id=actor.id, action="repair_scope_reviewed",
                    entity="RepairScope", entity_id=scope.id,
                    detail=json.dumps({"decision": payload.decision, "kind": scope.kind,
                                       "revision": scope.revision, "note": payload.note})))
    db.commit()
    db.refresh(scope)
    return scope_data(scope)


@router.post("/projects/{project_id}/components/{component_id}/stages", status_code=201)
def create_component_stage(project_id: str, component_id: str, payload: ComponentStageCreate,
                           db: Session = Depends(get_db)):
    actor = require_project_role(project_id, {"project_manager", "engineer"})
    component = component_in_project(db, project_id, component_id)
    definition = db.scalar(select(StageDefinition).where(StageDefinition.id == payload.stage_definition_id,
                           StageDefinition.project_id == project_id))
    if definition is None:
        raise HTTPException(404, "Stage definition not found")
    if definition.component_type != component.type:
        raise HTTPException(409, "Stage definition does not match component type")
    scope = db.scalar(select(RepairScope).where(RepairScope.id == payload.repair_scope_id,
                       RepairScope.component_id == component.id))
    if scope is None:
        raise HTTPException(404, "Repair scope not found")
    stage = ComponentStage(component_id=component.id, stage_definition_id=definition.id,
                           repair_scope_id=scope.id, created_by=actor.id)
    db.add(stage)
    try:
        db.flush()
        db.add(AuditLog(project_id=project_id, actor_id=actor.id, action="component_stage_created",
                        entity="ComponentStage", entity_id=stage.id,
                        detail=json.dumps({"component_id": component.id, "stage_definition_id": definition.id,
                                           "repair_scope_id": scope.id})))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Stage already attached") from exc
    return {"id": stage.id, "component_id": component.id, "stage_definition_id": definition.id,
            "repair_scope_id": scope.id, "code": definition.code, "name": definition.name,
            "position": definition.position, "status": "NOT_STARTED"}


@router.get("/projects/{project_id}/components/{component_id}/progress-events")
def list_progress_events(project_id: str, component_id: str, stage_id: str | None = None,
                         db: Session = Depends(get_db)):
    require_project_member(project_id)
    component = component_in_project(db, project_id, component_id)
    events = progress_events_for(db, component.id)
    if stage_id:
        if stage_definition_for(db, component.id, stage_id) is None:
            raise HTTPException(404, "Stage not found")
        events = [event for event in events if event.component_stage_id == stage_id]
    t_value = load_t_values(db, [component.id]).get(component.id)
    stage_names = {
        stage.id: display_stage_name(definition.name, [t_value])
        for stage, definition in db.execute(
            select(ComponentStage, StageDefinition)
            .join(StageDefinition, ComponentStage.stage_definition_id == StageDefinition.id)
            .where(ComponentStage.component_id == component.id)
        ).all()
    }
    return [
        {**event_data(event), "stage_name": stage_names.get(event.component_stage_id)}
        for event in events
    ]


@router.post("/projects/{project_id}/components/{component_id}/progress-events", status_code=201)
def append_progress_event(project_id: str, component_id: str, payload: ProgressEventCreate,
                          db: Session = Depends(get_db)):
    actor = require_project_role(project_id, {"project_manager", "engineer"})
    component = component_in_project(db, project_id, component_id)
    row = stage_definition_for(db, component.id, payload.stage_id)
    if row is None:
        raise HTTPException(404, "Stage not found")
    stage, definition = row
    refs = validate_evidence_refs(db, project_id, payload.evidence_refs)
    event = ProgressEvent(component_id=component.id, component_stage_id=stage.id,
                          event_date=payload.event_date, status=payload.status,
                          quantity=payload.quantity,
                          unit=(payload.unit or "").strip() or None,
                          note=(payload.note or "").strip() or None,
                          evidence_refs=json.dumps(refs), created_by=actor.id)
    db.add(event)
    db.flush()
    db.add(AuditLog(project_id=project_id, actor_id=actor.id, action="component_progress_recorded",
                    entity="ProgressEvent", entity_id=event.id,
                    detail=json.dumps({"component_id": component.id, "stage": definition.code,
                                       "status": event.status, "event_date": event.event_date.isoformat(),
                                       "quantity": event.quantity, "unit": event.unit})))
    db.commit()
    return event_data(event)


@router.get("/projects/{project_id}/segments")
def list_segments(project_id: str, zone: str | None = None, db: Session = Depends(get_db)):
    require_project_member(project_id)
    query = select(Segment, StructureZone).join(StructureZone, Segment.zone_id == StructureZone.id).where(
        StructureZone.project_id == project_id)
    if zone:
        query = query.where(StructureZone.name_key == zone_key(zone))
    return [{"id": segment.id, "number": segment.number, "source_code": segment.source_code,
             "zone": area.name} for segment, area in db.execute(query.order_by(Segment.number))]


@router.get("/projects/{project_id}/design-groups")
def list_design_groups(project_id: str, db: Session = Depends(get_db)):
    require_project_member(project_id)
    groups = db.scalars(select(DesignGroup).where(
        DesignGroup.project_id == project_id).order_by(DesignGroup.name, DesignGroup.drawing))
    return [{"id": group.id, "name": group.name, "drawing": group.drawing,
             "group_type": group.group_type} for group in groups]


@router.get("/projects/{project_id}/components")
def list_components(project_id: str, q: str | None = None, zone: str | None = None,
                    segment_id: str | None = None, type: Literal["pile", "beam"] | None = None,
                    group_id: str | None = None, scope: Literal["DESIGN_SCOPE", "ADDITIONAL_SCOPE"] | None = None,
                    batch_id: str | None = None, db: Session = Depends(get_db)):
    require_project_member(project_id)
    query = select(StructuralComponent, Segment, StructureZone, DesignGroup).join(
        Segment, StructuralComponent.segment_id == Segment.id).join(
        StructureZone, Segment.zone_id == StructureZone.id).outerjoin(
        DesignGroup, StructuralComponent.design_group_id == DesignGroup.id).where(
        StructuralComponent.project_id == project_id, StructureZone.project_id == project_id)
    if zone:
        query = query.where(StructureZone.name_key == zone_key(zone))
    if segment_id:
        query = query.where(StructuralComponent.segment_id == segment_id)
    if type:
        query = query.where(StructuralComponent.type == type)
    if group_id:
        query = query.where(StructuralComponent.design_group_id == group_id)
    if scope:
        query = query.where(StructuralComponent.id.in_(select(RepairScope.component_id).where(RepairScope.kind == scope)))
    if batch_id:
        query = query.where(
            StructuralComponent.id.in_(batch_component_ids(project_id, batch_id))
        )
    if q:
        code = q.strip().upper()
        query = query.where((StructuralComponent.canonical_code == code) | StructuralComponent.id.in_(
            select(ComponentAlias.component_id).where(ComponentAlias.alias == code)))
    rows = db.execute(query.order_by(StructuralComponent.canonical_code)).all()
    ids = [component.id for component, _, _, _ in rows]
    aliases = {}
    if ids:
        for component_id, alias in db.execute(select(ComponentAlias.component_id, ComponentAlias.alias).where(
                ComponentAlias.component_id.in_(ids))):
            aliases.setdefault(component_id, []).append(alias)
    return [{"id": c.id, "type": c.type, "canonical_code": c.canonical_code,
             "raw_code": c.raw_code, "segment_id": c.segment_id, "segment_number": segment.number,
             "zone": area.name, "design_group_id": c.design_group_id,
             "design_group": group.name if group else None,
             "aliases": [alias for alias in aliases.get(c.id, []) if alias != c.canonical_code],
             "verification": c.verification, "record_origin": c.record_origin}
            for c, segment, area, group in rows]


@router.get("/projects/{project_id}/components/{component_id}")
def component_detail(project_id: str, component_id: str, db: Session = Depends(get_db)):
    require_project_member(project_id)
    component = db.scalar(select(StructuralComponent).where(StructuralComponent.id == component_id,
                          StructuralComponent.project_id == project_id))
    if component is None:
        raise HTTPException(404, "Component not found")
    scopes = db.scalars(select(RepairScope).where(RepairScope.component_id == component.id).order_by(RepairScope.revision)).all()
    links = db.scalars(select(ComponentWorkLink).where(ComponentWorkLink.component_id == component.id).order_by(ComponentWorkLink.dm_row)).all()
    group = db.get(DesignGroup, component.design_group_id) if component.design_group_id else None
    stage_rows = db.execute(select(ComponentStage, StageDefinition).join(
        StageDefinition, ComponentStage.stage_definition_id == StageDefinition.id).where(
        ComponentStage.component_id == component.id).order_by(
        StageDefinition.position, StageDefinition.code)).all()
    events = progress_events_for(db, component.id)
    latest: dict[str, ProgressEvent] = {}
    for event in events:
        current = latest.get(event.component_stage_id)
        if current is None or (event.created_at, event.id) > (current.created_at, current.id):
            latest[event.component_stage_id] = event
    from app.site.progress_inference import apply_inferred_progress

    parameters = load_parameters(db, [component.id]).get(component.id, [])
    t_value = next(
        (float(item["value"]) for item in parameters if item["name"] == "t_cm"),
        None,
    )
    stage_names = {
        stage.id: display_stage_name(definition.name, [t_value])
        for stage, definition in stage_rows
    }
    stages = apply_inferred_progress(component.type, [
        {"id": stage.id, "stage_definition_id": definition.id,
         "repair_scope_id": stage.repair_scope_id, "code": definition.code,
         "name": stage_names[stage.id], "position": definition.position,
         "status": latest[stage.id].status if stage.id in latest else "NOT_STARTED",
         "latest_event_at": latest[stage.id].created_at if stage.id in latest else None}
        for stage, definition in stage_rows
    ])
    return {"id": component.id, "type": component.type, "raw_code": component.raw_code,
            "canonical_code": component.canonical_code, "verification": component.verification,
            "record_origin": component.record_origin,
            "aliases": [alias for alias in db.scalars(select(ComponentAlias.alias).where(
                ComponentAlias.component_id == component.id)) if alias != component.canonical_code],
            "source": {"sha256": component.source_hash,
                       "sheet": "DANH_MUC" if component.record_origin == "SEED_IMPORT" else None,
                       "row": component.source_row},
            "design_group": {"name": group.name, "drawing": group.drawing, "source": group.source,
                             "source_page": group.source_page} if group else None,
            "design_parameters": parameters,
            "scopes": [scope_data(scope) for scope in scopes],
            "stages": stages,
            "progress_events": [
                {**event_data(event), "stage_name": stage_names.get(event.component_stage_id)}
                for event in events
            ],
            "work_links": [{"dm_row": link.dm_row, "seed_sheet": link.seed_sheet, "seed_row": link.seed_row,
                            "source_sha256": link.source_hash, "work": link.work, "raw_location": link.raw_location}
                           for link in links]}
