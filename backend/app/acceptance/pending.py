"""Read-only pending-acceptance queue built from progress events.

Progress only tells us that construction reported COMPLETED. It never creates or
implies acceptance: a component is excluded only when a confirmed BBNT link
exists for the same stage/scope.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.component_models import (
    ComponentStage,
    ConstructionBatchComponent,
    ProgressEvent,
    Segment,
    StageDefinition,
    StructuralComponent,
    StructureZone,
)
from ..core.design_parameters import display_stage_name, load_t_values
from .models import AcceptanceRecord, ComponentAcceptanceLink
from .schemas import (
    PendingAcceptanceComponentOut,
    PendingAcceptanceGroupOut,
    PendingAcceptanceResponse,
)


def _latest_completed_events(
    db: Session,
    project_id: str,
    stage_definition_id: Optional[str] = None,
) -> List[Tuple[ProgressEvent, StructuralComponent, ComponentStage, StageDefinition]]:
    components = list(
        db.scalars(
            select(StructuralComponent).where(
                StructuralComponent.project_id == project_id
            )
        ).all()
    )
    if not components:
        return []
    component_by_id = {component.id: component for component in components}
    stages = {
        stage.id: stage
        for stage in db.scalars(
            select(ComponentStage).where(
                ComponentStage.component_id.in_(list(component_by_id))
            )
        ).all()
    }
    definitions = {
        definition.id: definition
        for definition in db.scalars(
            select(StageDefinition).where(StageDefinition.project_id == project_id)
        ).all()
    }
    events = list(
        db.scalars(
            select(ProgressEvent)
            .where(
                ProgressEvent.component_id.in_(list(component_by_id)),
                ProgressEvent.voided_at.is_(None),
            )
            .order_by(ProgressEvent.event_date, ProgressEvent.created_at)
        ).all()
    )
    latest: Dict[str, ProgressEvent] = {}
    for event in events:
        stage = stages.get(event.component_stage_id)
        if stage is None:
            continue
        if (
            stage_definition_id is not None
            and stage.stage_definition_id != stage_definition_id
        ):
            continue
        latest[event.component_id] = event

    rows: List[
        Tuple[ProgressEvent, StructuralComponent, ComponentStage, StageDefinition]
    ] = []
    for component_id, event in latest.items():
        if event.status != "COMPLETED":
            continue
        stage = stages.get(event.component_stage_id)
        definition = definitions.get(stage.stage_definition_id) if stage else None
        if stage is None or definition is None:
            continue
        rows.append((event, component_by_id[component_id], stage, definition))
    return rows


def _confirmed_link_keys(db: Session, project_id: str):
    links = list(
        db.scalars(
            select(ComponentAcceptanceLink).where(
                ComponentAcceptanceLink.project_id == project_id,
                ComponentAcceptanceLink.record_id.is_not(None),
            )
        ).all()
    )
    if not links:
        return set()
    record_ids = {link.record_id for link in links if link.record_id}
    confirmed = {
        record_id
        for record_id in db.scalars(
            select(AcceptanceRecord.id).where(
                AcceptanceRecord.project_id == project_id,
                AcceptanceRecord.id.in_(record_ids),
                AcceptanceRecord.status == "confirmed",
            )
        ).all()
    }
    keys = set()
    for link in links:
        if link.record_id in confirmed and link.component_id:
            keys.add((link.component_id, link.stage_id, link.scope_id))
    return keys


def _is_confirmed(
    keys,
    component_id: str,
    stage: ComponentStage,
) -> bool:
    for key_component, key_stage, key_scope in keys:
        if key_component != component_id:
            continue
        if key_stage == stage.id:
            return True
        if key_stage is None and key_scope in {None, stage.repair_scope_id}:
            return True
    return False


def _filter_stage_name(
    db: Session, project_id: str, stage_definition_id: Optional[str]
) -> Optional[str]:
    """Display name for the stage filter chip, with per-pile thickness."""

    if not stage_definition_id:
        return None
    definition = db.get(StageDefinition, stage_definition_id)
    if definition is None or definition.project_id != project_id:
        return None
    component_ids = list(
        db.scalars(
            select(ComponentStage.component_id).where(
                ComponentStage.stage_definition_id == stage_definition_id
            )
        ).all()
    )
    t_values = load_t_values(db, component_ids)
    return display_stage_name(
        " ".join(str(definition.name or "").split()), list(t_values.values())
    )


def pending_acceptance(
    db: Session,
    project_id: str,
    *,
    batch_id: Optional[str] = None,
    stage_definition_id: Optional[str] = None,
) -> PendingAcceptanceResponse:
    rows = _latest_completed_events(db, project_id, stage_definition_id)
    if batch_id:
        batch_component_ids = set(
            db.scalars(
                select(ConstructionBatchComponent.component_id).where(
                    ConstructionBatchComponent.batch_id == batch_id
                )
            ).all()
        )
        rows = [row for row in rows if row[1].id in batch_component_ids]

    confirmed_keys = _confirmed_link_keys(db, project_id)
    zones = {
        zone.id: zone
        for zone in db.scalars(
            select(StructureZone).where(StructureZone.project_id == project_id)
        ).all()
    }
    segments = {
        segment.id: segment
        for segment in (
            db.scalars(select(Segment).where(Segment.zone_id.in_(list(zones)))).all()
            if zones
            else []
        )
    }
    component_ids = [row[1].id for row in rows]
    t_values = load_t_values(db, component_ids)

    grouped: Dict[Tuple[str, str, int], List[PendingAcceptanceComponentOut]] = defaultdict(list)
    dates: Dict[Tuple[str, str, int], List] = defaultdict(list)
    for event, component, stage, definition in rows:
        if _is_confirmed(confirmed_keys, component.id, stage):
            continue
        segment = segments.get(component.segment_id)
        zone = zones.get(segment.zone_id) if segment else None
        stage_name = display_stage_name(
            " ".join(str(definition.name or "").split()),
            [t_values.get(component.id)],
        )
        key = (
            stage_name,
            zone.name if zone else "Không rõ khu",
            segment.number if segment else 0,
        )
        grouped[key].append(
            PendingAcceptanceComponentOut(
                component_id=component.id,
                code=component.canonical_code,
                type=component.type,
                event_id=event.id,
                event_date=event.event_date,
                stage_id=stage.id,
                stage_definition_id=definition.id,
                scope_id=stage.repair_scope_id,
                stage_name=stage_name,
            )
        )
        if event.event_date not in dates[key]:
            dates[key].append(event.event_date)

    groups = [
        PendingAcceptanceGroupOut(
            stage_name=stage_name,
            zone=zone_name,
            segment=segment_number,
            event_dates=sorted(dates[(stage_name, zone_name, segment_number)]),
            components=sorted(components, key=lambda item: item.code),
        )
        for (stage_name, zone_name, segment_number), components in sorted(
            grouped.items(), key=lambda item: (item[0][1], item[0][2], item[0][0])
        )
    ]
    return PendingAcceptanceResponse(
        project_id=project_id,
        batch_id=batch_id,
        stage_definition_id=stage_definition_id,
        stage_name=_filter_stage_name(db, project_id, stage_definition_id),
        groups=groups,
        total_components=sum(len(group.components) for group in groups),
    )
