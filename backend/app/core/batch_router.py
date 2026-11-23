"""Project-scoped construction batches ("Đợt thi công").

A batch groups components executed together on site without changing each
component's design zone/segment. Reads are open to project members; writes need
the project editor role and are audited.
"""

from __future__ import annotations

import json
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .access import require_project_member, require_project_role
from .component_models import (
    ComponentAlias,
    ConstructionBatch,
    ConstructionBatchComponent,
    DesignGroup,
    Segment,
    StructuralComponent,
    StructureZone,
)
from .database import get_db
from .models import AuditLog

router = APIRouter(tags=["components"])


class BatchIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    note: str | None = Field(default=None, max_length=2000)


class BatchPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    note: str | None = Field(default=None, max_length=2000)
    archived: bool | None = None


class BatchCodesIn(BaseModel):
    codes: list[str] = Field(min_length=1, max_length=1000)


class BatchAddIn(BaseModel):
    component_ids: list[str] = Field(min_length=1, max_length=1000)
    reason: str | None = Field(default=None, max_length=1000)


def _batch(db: Session, project_id: str, batch_id: str) -> ConstructionBatch:
    batch = db.scalar(
        select(ConstructionBatch).where(
            ConstructionBatch.id == batch_id,
            ConstructionBatch.project_id == project_id,
        )
    )
    if batch is None:
        raise HTTPException(404, "Construction batch not found")
    return batch


def _component_data(
    component: StructuralComponent,
    segment: Segment,
    zone: StructureZone,
    group: DesignGroup | None,
) -> dict:
    return {
        "id": component.id,
        "type": component.type,
        "canonical_code": component.canonical_code,
        "raw_code": component.raw_code,
        "segment_id": component.segment_id,
        "segment_number": segment.number,
        "zone": zone.name,
        "design_group": group.name if group else None,
        "verification": component.verification,
    }


def _batch_components(db: Session, batch_id: str):
    return db.execute(
        select(
            StructuralComponent,
            Segment,
            StructureZone,
            DesignGroup,
            ConstructionBatchComponent,
        )
        .join(
            ConstructionBatchComponent,
            ConstructionBatchComponent.component_id == StructuralComponent.id,
        )
        .join(Segment, Segment.id == StructuralComponent.segment_id)
        .join(StructureZone, StructureZone.id == Segment.zone_id)
        .outerjoin(DesignGroup, DesignGroup.id == StructuralComponent.design_group_id)
        .where(ConstructionBatchComponent.batch_id == batch_id)
        .order_by(StructureZone.name, Segment.number, StructuralComponent.canonical_code)
    ).all()


def _batch_data(db: Session, batch: ConstructionBatch) -> dict:
    rows = _batch_components(db, batch.id)
    zones = Counter(zone.name for _, _, zone, _, _ in rows)
    primary_zone = zones.most_common(1)[0][0] if zones else None
    return {
        "id": batch.id,
        "name": batch.name,
        "note": batch.note,
        "archived": batch.archived,
        "created_by": batch.created_by,
        "created_at": batch.created_at.isoformat(),
        "component_count": len(rows),
        "primary_zone": primary_zone,
    }


@router.get("/projects/{project_id}/construction-batches")
def list_batches(
    project_id: str,
    include_archived: bool = False,
    db: Session = Depends(get_db),
):
    require_project_member(project_id)
    query = select(ConstructionBatch).where(ConstructionBatch.project_id == project_id)
    if not include_archived:
        query = query.where(ConstructionBatch.archived.is_(False))
    batches = db.scalars(
        query.order_by(ConstructionBatch.created_at.desc(), ConstructionBatch.id)
    )
    return [_batch_data(db, batch) for batch in batches]


@router.post("/projects/{project_id}/construction-batches", status_code=201)
def create_batch(project_id: str, payload: BatchIn, db: Session = Depends(get_db)):
    actor = require_project_role(project_id, {"project_manager", "engineer"})
    name = payload.name.strip()
    if not name:
        raise HTTPException(422, "Batch name is required")
    batch = ConstructionBatch(
        project_id=project_id,
        name=name,
        note=(payload.note or "").strip() or None,
        created_by=actor.id,
    )
    db.add(batch)
    db.flush()
    db.add(
        AuditLog(
            project_id=project_id,
            actor_id=actor.id,
            action="construction_batch_created",
            entity="ConstructionBatch",
            entity_id=batch.id,
            detail=json.dumps({"name": batch.name, "note": batch.note}),
        )
    )
    db.commit()
    return _batch_data(db, batch)


@router.patch("/projects/{project_id}/construction-batches/{batch_id}")
def update_batch(
    project_id: str,
    batch_id: str,
    payload: BatchPatch,
    db: Session = Depends(get_db),
):
    actor = require_project_role(project_id, {"project_manager", "engineer"})
    batch = _batch(db, project_id, batch_id)
    changes: dict = {}
    if payload.name is not None:
        name = payload.name.strip()
        if not name:
            raise HTTPException(422, "Batch name is required")
        batch.name = name
        changes["name"] = name
    if payload.note is not None:
        batch.note = payload.note.strip() or None
        changes["note"] = batch.note
    if payload.archived is not None:
        batch.archived = payload.archived
        changes["archived"] = payload.archived
    db.add(
        AuditLog(
            project_id=project_id,
            actor_id=actor.id,
            action="construction_batch_updated",
            entity="ConstructionBatch",
            entity_id=batch.id,
            detail=json.dumps(changes),
        )
    )
    db.commit()
    return _batch_data(db, batch)


@router.get("/projects/{project_id}/construction-batches/{batch_id}")
def get_batch(project_id: str, batch_id: str, db: Session = Depends(get_db)):
    require_project_member(project_id)
    batch = _batch(db, project_id, batch_id)
    rows = _batch_components(db, batch.id)
    return {
        **_batch_data(db, batch),
        "components": [
            {
                **_component_data(component, segment, zone, group),
                "reason": link.reason,
                "added_at": link.added_at.isoformat(),
            }
            for component, segment, zone, group, link in rows
        ],
    }


@router.post("/projects/{project_id}/construction-batches/{batch_id}/components/preview")
def preview_batch_components(
    project_id: str,
    batch_id: str,
    payload: BatchCodesIn,
    db: Session = Depends(get_db),
):
    require_project_member(project_id)
    batch = _batch(db, project_id, batch_id)
    codes = []
    for raw in payload.codes:
        code = raw.strip().upper()
        if code and code not in codes:
            codes.append(code)
    if not codes:
        raise HTTPException(422, "At least one code is required")

    alias_rows = db.execute(
        select(ComponentAlias.alias, ComponentAlias.component_id).where(
            ComponentAlias.project_id == project_id,
            ComponentAlias.alias.in_(codes),
        )
    ).all()
    ids_from_alias = {component_id for _, component_id in alias_rows}
    rows = db.execute(
        select(StructuralComponent, Segment, StructureZone, DesignGroup)
        .join(Segment, Segment.id == StructuralComponent.segment_id)
        .join(StructureZone, StructureZone.id == Segment.zone_id)
        .outerjoin(DesignGroup, DesignGroup.id == StructuralComponent.design_group_id)
        .where(
            StructuralComponent.project_id == project_id,
            StructureZone.project_id == project_id,
            (
                StructuralComponent.canonical_code.in_(codes)
                | func.upper(StructuralComponent.raw_code).in_(codes)
                | StructuralComponent.id.in_(ids_from_alias)
            ),
        )
    ).all()

    current = set(
        db.scalars(
            select(ConstructionBatchComponent.component_id).where(
                ConstructionBatchComponent.batch_id == batch.id
            )
        )
    )
    candidates: dict[str, list[dict]] = {code: [] for code in codes}
    for component, segment, zone, group in rows:
        data = {
            **_component_data(component, segment, zone, group),
            "in_batch": component.id in current,
        }
        if component.canonical_code.upper() in candidates:
            candidates[component.canonical_code.upper()].append(data)
        if component.raw_code.upper() in candidates:
            candidates[component.raw_code.upper()].append(data)
        for alias, component_id in alias_rows:
            if component_id == component.id and alias in candidates:
                candidates[alias].append(data)

    matched, ambiguous, missing, already = [], [], [], []
    seen: set[str] = set()
    for code in codes:
        items = candidates.get(code, [])
        unique = {item["id"]: item for item in items}
        values = list(unique.values())
        if not values:
            missing.append(code)
        elif len(values) > 1:
            ambiguous.append({"code": code, "candidates": values})
        else:
            item = values[0]
            if item["in_batch"]:
                already.append(code)
            elif item["id"] in seen:
                already.append(code)
            else:
                seen.add(item["id"])
                matched.append({"code": code, "component": item})

    return {
        "codes": codes,
        "matched": matched,
        "ambiguous": ambiguous,
        "missing": missing,
        "already_in_batch": already,
    }


@router.post("/projects/{project_id}/construction-batches/{batch_id}/components", status_code=201)
def add_batch_components(
    project_id: str,
    batch_id: str,
    payload: BatchAddIn,
    db: Session = Depends(get_db),
):
    actor = require_project_role(project_id, {"project_manager", "engineer"})
    batch = _batch(db, project_id, batch_id)
    component_ids = list(dict.fromkeys(payload.component_ids))
    components = list(
        db.scalars(
            select(StructuralComponent).where(
                StructuralComponent.project_id == project_id,
                StructuralComponent.id.in_(component_ids),
            )
        )
    )
    found = {component.id for component in components}
    missing = [component_id for component_id in component_ids if component_id not in found]
    if missing:
        raise HTTPException(404, "Component not found in this project")
    current = set(
        db.scalars(
            select(ConstructionBatchComponent.component_id).where(
                ConstructionBatchComponent.batch_id == batch.id
            )
        )
    )
    added = []
    for component_id in component_ids:
        if component_id in current:
            continue
        db.add(
            ConstructionBatchComponent(
                batch_id=batch.id,
                component_id=component_id,
                added_by=actor.id,
                reason=(payload.reason or "").strip() or None,
            )
        )
        added.append(component_id)
        db.add(
            AuditLog(
                project_id=project_id,
                actor_id=actor.id,
                action="construction_batch_component_added",
                entity="ConstructionBatchComponent",
                entity_id=f"{batch.id}:{component_id}",
                detail=json.dumps({"batch_id": batch.id, "component_id": component_id,
                                   "reason": (payload.reason or "").strip() or None}),
            )
        )
    db.commit()
    return {"batch_id": batch.id, "added": len(added), "skipped": len(component_ids) - len(added)}


@router.delete("/projects/{project_id}/construction-batches/{batch_id}/components/{component_id}")
def remove_batch_component(
    project_id: str,
    batch_id: str,
    component_id: str,
    reason: str | None = Query(default=None, max_length=1000),
    db: Session = Depends(get_db),
):
    actor = require_project_role(project_id, {"project_manager", "engineer"})
    batch = _batch(db, project_id, batch_id)
    link = db.scalar(
        select(ConstructionBatchComponent).where(
            ConstructionBatchComponent.batch_id == batch.id,
            ConstructionBatchComponent.component_id == component_id,
        )
    )
    if link is None:
        raise HTTPException(404, "Component is not in this batch")
    db.delete(link)
    db.add(
        AuditLog(
            project_id=project_id,
            actor_id=actor.id,
            action="construction_batch_component_removed",
            entity="ConstructionBatchComponent",
            entity_id=f"{batch.id}:{component_id}",
            detail=json.dumps({"batch_id": batch.id, "component_id": component_id,
                               "reason": (reason or "").strip() or None}),
        )
    )
    db.commit()
    return {"batch_id": batch.id, "removed": component_id}
