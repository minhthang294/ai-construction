"""Read-only question suggestions built from the project's real component data."""

from __future__ import annotations

from collections import Counter
from typing import Dict, List

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.component_models import (
    ComponentStage,
    DesignGroup,
    ProgressEvent,
    Segment,
    StageDefinition,
    StructuralComponent,
    StructureZone,
)
from .database_chat import _component_tables_available
from .embeddings import fold_text
from .schemas import QuestionSuggestionOut

MAX_SUGGESTIONS = 5


def _load_project(db: Session, project_id: str):
    components = list(
        db.scalars(
            select(StructuralComponent)
            .where(StructuralComponent.project_id == project_id)
            .order_by(StructuralComponent.canonical_code)
        ).all()
    )
    if not components:
        return None
    zones = {
        row.id: row
        for row in db.scalars(
            select(StructureZone).where(StructureZone.project_id == project_id)
        ).all()
    }
    segments = {
        row.id: row
        for row in (
            db.scalars(select(Segment).where(Segment.zone_id.in_(list(zones)))).all()
            if zones
            else []
        )
    }
    definitions = {
        row.id: row
        for row in db.scalars(
            select(StageDefinition).where(StageDefinition.project_id == project_id)
        ).all()
    }
    groups = {
        row.id: row
        for row in db.scalars(
            select(DesignGroup).where(DesignGroup.project_id == project_id)
        ).all()
    }
    ids = [component.id for component in components]
    stages = list(
        db.scalars(select(ComponentStage).where(ComponentStage.component_id.in_(ids))).all()
    )
    events = list(
        db.scalars(select(ProgressEvent).where(ProgressEvent.component_id.in_(ids))).all()
    )
    return components, zones, segments, definitions, groups, stages, events


def _noun(component_type: str) -> str:
    return "cọc" if component_type == "pile" else "dầm" if component_type == "beam" else "cấu kiện"


def _stage_name(definition: StageDefinition) -> str:
    name = " ".join(str(definition.name or "").split())
    return name or str(definition.code or "công đoạn")


def _pending_stage_suggestion(
    components: List[StructuralComponent],
    segments: Dict[str, Segment],
    definitions: Dict[str, StageDefinition],
    stages: List[ComponentStage],
    events: List[ProgressEvent],
) -> QuestionSuggestionOut | None:
    segment_counts = Counter(
        component.segment_id for component in components if component.segment_id in segments
    )
    if not segment_counts:
        return None
    segment_id, _count = segment_counts.most_common(1)[0]
    segment_number = segments[segment_id].number
    scoped = [component for component in components if component.segment_id == segment_id]
    pile_ids = {component.id for component in scoped if component.type == "pile"}
    scoped_ids = pile_ids or {component.id for component in scoped}

    stage_by_component: Dict[str, List[ComponentStage]] = {}
    for stage in stages:
        if stage.component_id in scoped_ids and stage.stage_definition_id in definitions:
            stage_by_component.setdefault(stage.component_id, []).append(stage)
    if not stage_by_component:
        return None

    definition_ids = Counter(
        stage.stage_definition_id
        for rows in stage_by_component.values()
        for stage in rows
    )
    chosen_id = definition_ids.most_common(1)[0][0]
    definition = definitions.get(chosen_id)
    if definition is None:
        return None
    stage_ids = {
        stage.id
        for rows in stage_by_component.values()
        for stage in rows
        if stage.stage_definition_id == chosen_id
    }
    completed = {
        event.component_stage_id
        for event in events
        if event.component_stage_id in stage_ids and event.status == "COMPLETED"
    }
    with_stage = [
        component_id
        for component_id, rows in stage_by_component.items()
        if any(stage.stage_definition_id == chosen_id for stage in rows)
    ]
    pending = [
        component_id
        for component_id in with_stage
        if not any(
            stage.id in completed
            for stage in stage_by_component[component_id]
            if stage.stage_definition_id == chosen_id
        )
    ]
    noun = "cọc" if scoped_ids is pile_ids else "cấu kiện"
    stage_text = _stage_name(definition).lower()
    action = "đục bê tông" if "duc" in fold_text(stage_text) and "be tong" in fold_text(stage_text) else stage_text
    prompt = f"PD{segment_number} còn bao nhiêu {noun} chưa {action}?"
    label = (
        f"PD{segment_number}: còn {len(pending)}/{len(with_stage)} {noun} chưa {action}"
        if with_stage
        else f"PD{segment_number}: {noun} chưa {action}"
    )
    return QuestionSuggestionOut(
        id="pending-stage",
        label=label,
        prompt=prompt,
        mode="send",
        badge="caution",
    )


def _component_stage_suggestion(
    components: List[StructuralComponent],
    stages: List[ComponentStage],
    events: List[ProgressEvent],
) -> QuestionSuggestionOut | None:
    event_component_ids = {event.component_id for event in events}
    with_stage = {stage.component_id for stage in stages}
    chosen = next(
        (component for component in components if component.id in event_component_ids),
        next((component for component in components if component.id in with_stage), None),
    )
    if chosen is None:
        return None
    noun = "Cọc" if chosen.type == "pile" else "Dầm" if chosen.type == "beam" else "Cấu kiện"
    return QuestionSuggestionOut(
        id="component-stage",
        label=f"{noun} {chosen.canonical_code} đang ở bước nào?",
        prompt=f"{noun} {chosen.canonical_code} đang ở bước nào?",
        mode="fill",
        badge="verified" if chosen.id in event_component_ids else "proposed",
    )


def _latest_progress_suggestion(events: List[ProgressEvent]) -> QuestionSuggestionOut:
    if not events:
        return QuestionSuggestionOut(
            id="latest-progress",
            label="Tiến độ ngày gần nhất?",
            prompt="Tiến độ ngày gần nhất?",
            mode="send",
            badge="caution",
        )
    latest = max(event.event_date for event in events)
    label = f"Tiến độ ngày {latest.day}/{latest.month}?"
    return QuestionSuggestionOut(
        id="latest-progress",
        label=label,
        prompt=f"Tiến độ ngày {latest.day:02d}/{latest.month:02d}?",
        mode="send",
        badge="caution",
    )


def _drawing_suggestion(
    component: StructuralComponent,
    segments: Dict[str, Segment],
    groups: Dict[str, DesignGroup],
) -> QuestionSuggestionOut | None:
    segment = segments.get(component.segment_id)
    if segment is None:
        return None
    group = groups.get(component.design_group_id or "")
    group_number = next(
        (part for part in (group.name if group else "").replace("-", " ").split() if part.isdigit()),
        None,
    )
    noun = "cọc" if component.type == "pile" else "dầm" if component.type == "beam" else "cấu kiện"
    if group_number:
        prompt = f"Mở bản vẽ nhóm {noun} {group_number} PD{segment.number}"
        label = prompt
    else:
        prompt = f"Mở bản vẽ {noun} phân đoạn {segment.number}"
        label = prompt
    return QuestionSuggestionOut(
        id="open-drawing",
        label=label,
        prompt=prompt,
        mode="send",
        badge="navigation",
    )


def _count_suggestion(components: List[StructuralComponent]) -> QuestionSuggestionOut:
    pile_count = sum(1 for component in components if component.type == "pile")
    noun = "cọc" if pile_count >= len(components) - pile_count else "cấu kiện"
    return QuestionSuggestionOut(
        id="project-count",
        label=f"Công trình có bao nhiêu {noun}?",
        prompt=f"Công trình có bao nhiêu {noun}?",
        mode="send",
        badge="verified",
    )


def question_suggestions(db: Session, project_id: str) -> List[QuestionSuggestionOut]:
    """4-5 chips built from existing components, stages, progress and groups."""

    if not _component_tables_available(db):
        return []
    loaded = _load_project(db, project_id)
    if loaded is None:
        return []
    components, _zones, segments, definitions, groups, stages, events = loaded

    suggestions: List[QuestionSuggestionOut] = []
    pending = _pending_stage_suggestion(components, segments, definitions, stages, events)
    if pending is not None:
        suggestions.append(pending)
    component_stage = _component_stage_suggestion(components, stages, events)
    if component_stage is not None:
        suggestions.append(component_stage)
    suggestions.append(_latest_progress_suggestion(events))
    representative = next(
        (component for component in components if component.id in {e.component_id for e in events}),
        components[0],
    )
    drawing = _drawing_suggestion(representative, segments, groups)
    if drawing is not None:
        suggestions.append(drawing)
    suggestions.append(_count_suggestion(components))

    seen: set[str] = set()
    unique = []
    for suggestion in suggestions:
        if suggestion.prompt in seen:
            continue
        seen.add(suggestion.prompt)
        unique.append(suggestion)
    return unique[:MAX_SUGGESTIONS]
