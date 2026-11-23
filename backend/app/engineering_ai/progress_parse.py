"""Deterministic parser for field Zalo progress messages (read-only, no DB writes).

The parser extracts a date, work phrase, component codes and stage candidates
from free text.  It never guesses: ambiguous or risky input becomes a question
for the engineer.  An LLM fallback is intentionally not wired here; unreadable
lines are returned with ``needs_review`` warnings and no invented codes.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.component_models import (
    ComponentAlias,
    ComponentStage,
    ConstructionBatch,
    ConstructionBatchComponent,
    ProgressEvent,
    Segment,
    StageDefinition,
    StructuralComponent,
    StructureZone,
)
from .embeddings import fold_text, tokenize
from .schemas import (
    ProgressParseItemOut,
    ProgressParseLineOut,
    ProgressParseQuestionOptionOut,
    ProgressParseQuestionOut,
    ProgressParseResponse,
    StageCandidateOut,
)

_DATE_RE = re.compile(
    r"(?<![A-Za-z0-9-])(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?(?![A-Za-z0-9-])"
)
_TYPE_PREFIX_RE = re.compile(r"^\s*(?:cọc|coc|dầm|dam)\b\s*", re.IGNORECASE)
_PILE_CODE_RE = re.compile(r"^([A-Za-z]{1,3})(\d{1,4})$")
_BARE_NUMBER_RE = re.compile(r"^(\d{1,4})$")
_BEAM_SHORTHAND_RE = re.compile(r"^([A-Za-z]{1,3})(\d{1,4})?-([A-Za-z]{0,3})(\d{1,4})$")
_BEAM_CANONICAL_RE = re.compile(
    r"^[A-Za-z]{1,3}-(?:[A-Za-z]{1,3}-\d{1,4}|\d{1,4}-\d{1,4})$"
)
_GENERIC_WORK_TOKENS = {"coc", "dam", "pile", "beam", "be", "tong", "concrete", "thi", "cong"}


def _code_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", fold_text(value or ""))


@dataclass
class _Item:
    raw: str
    code: str
    component: Optional[StructuralComponent] = None
    status_guess: str = "COMPLETED"


@dataclass
class _ParsedLine:
    component_type: str
    work_text: str
    items: List[_Item] = field(default_factory=list)


def _parse_date(text: str, default_date: Optional[date]) -> Tuple[Optional[date], Optional[str]]:
    match = _DATE_RE.search(text)
    if match:
        day, month = int(match.group(1)), int(match.group(2))
        year = int(match.group(3)) if match.group(3) else None
        if year is not None and year < 100:
            year += 2000
        if year is None:
            year = (default_date or date.today()).year
        try:
            return date(year, month, day), "text"
        except ValueError:
            return None, None
    if default_date is not None:
        return default_date, "default_date"
    return None, None


def _clean_line(line: str) -> str:
    return _DATE_RE.sub(" ", line).strip()


def _line_type(line: str) -> Optional[str]:
    folded = fold_text(line).lstrip()
    if re.match(r"^(?:dam|beam)\b", folded):
        return "beam"
    if re.match(r"^(?:coc|pile)\b", folded):
        return "pile"
    return None


def _beam_code(token: str) -> Optional[str]:
    if _BEAM_CANONICAL_RE.fullmatch(token):
        return token.upper()
    match = _BEAM_SHORTHAND_RE.fullmatch(token)
    if match is None:
        return None
    first, first_number, second, second_number = match.groups()
    if second:
        return f"{first.upper()}-{second.upper()}-{second_number}"
    if first_number:
        return f"{first.upper()}-{first_number}-{second_number}"
    return None


def _codes_in_line(
    clean_line: str, component_type: str, initial_prefix: Optional[str] = None
) -> Tuple[List[Tuple[str, str]], Optional[str]]:
    """Return (raw token, candidate code) pairs, applying prefix shorthand."""

    body = _TYPE_PREFIX_RE.sub("", clean_line)
    tokens = [token.strip(".;:()[]") for token in re.split(r"[,\s]+", body) if token.strip(".;:()[]")]
    codes: List[Tuple[str, str]] = []
    last_prefix: Optional[str] = initial_prefix
    for token in tokens:
        if component_type == "beam":
            code = _beam_code(token)
            if code:
                codes.append((token, code))
            continue
        pile_match = _PILE_CODE_RE.fullmatch(token)
        if pile_match:
            last_prefix = pile_match.group(1).upper()
            codes.append((token, f"{last_prefix}{pile_match.group(2)}"))
            continue
        bare_match = _BARE_NUMBER_RE.fullmatch(token)
        if bare_match and last_prefix:
            codes.append((token, f"{last_prefix}{bare_match.group(1)}"))
    return codes, last_prefix


def _work_phrase(clean_line: str, component_type: str) -> Optional[str]:
    body = _TYPE_PREFIX_RE.sub("", clean_line)
    body = re.sub(r"[,\s]+", " ", body).strip(" .;:")
    if not body:
        return None
    if not re.search(r"[^\W\d_]", body, re.UNICODE):
        return None
    return body


def _verb_tokens(work_text: str) -> List[str]:
    return [
        token
        for token in tokenize(work_text)
        if token not in _GENERIC_WORK_TOKENS and len(token) >= 2
    ]


def _stage_candidates(
    definitions: List[StageDefinition], component_type: str, work_text: str
) -> List[StageCandidateOut]:
    tokens = _verb_tokens(work_text)
    if not tokens:
        return []
    candidates = []
    for definition in definitions:
        if definition.component_type != component_type:
            continue
        folded = fold_text(f"{definition.code} {definition.name}")
        if any(token in folded for token in tokens):
            candidates.append(
                StageCandidateOut(
                    stage_definition_id=definition.id,
                    name=" ".join(str(definition.name).split()),
                    component_type=component_type,
                )
            )
    return candidates


def _question_option(label: str, value: str) -> ProgressParseQuestionOptionOut:
    return ProgressParseQuestionOptionOut(label_vi=label, value=value)


def progress_parse(
    db: Session,
    project_id: str,
    text: str,
    default_date: Optional[date] = None,
    batch_id: Optional[str] = None,
) -> ProgressParseResponse:
    """Parse a pasted progress message; selects only, never commits."""

    event_date, date_source = _parse_date(text, default_date)
    warnings: List[str] = []
    if event_date is None:
        warnings.append("Chưa xác định được ngày thi công; hãy nhập ngày trước khi ghi.")

    components = list(
        db.scalars(
            select(StructuralComponent).where(
                StructuralComponent.project_id == project_id
            )
        ).all()
    )
    aliases = list(
        db.scalars(
            select(ComponentAlias).where(ComponentAlias.project_id == project_id)
        ).all()
    )
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
    definitions = list(
        db.scalars(
            select(StageDefinition).where(StageDefinition.project_id == project_id)
        ).all()
    )
    component_ids = [component.id for component in components]
    stages = (
        list(
            db.scalars(
                select(ComponentStage).where(
                    ComponentStage.component_id.in_(component_ids)
                )
            ).all()
        )
        if component_ids
        else []
    )
    events = (
        list(
            db.scalars(
                select(ProgressEvent).where(
                    ProgressEvent.component_id.in_(component_ids),
                    ProgressEvent.voided_at.is_(None),
                )
            ).all()
        )
        if component_ids
        else []
    )

    lookup: Dict[Tuple[str, str], List[StructuralComponent]] = {}
    for component in components:
        for value in (component.canonical_code, component.raw_code):
            lookup.setdefault((component.type, _code_key(value)), []).append(component)
    for alias in aliases:
        lookup.setdefault((alias.type, _code_key(alias.alias)), []).append(
            next(
                (component for component in components if component.id == alias.component_id),
                None,
            )
        )
    for key, rows in lookup.items():
        lookup[key] = [row for row in rows if row is not None]

    # Flatten message text: date masks keep I-30-31 style codes intact.
    lines: List[_ParsedLine] = []
    work_by_type: Dict[str, str] = {}
    current_work: Optional[str] = None
    folded_text = fold_text(text)
    in_progress = "dang" in folded_text
    status_guess = "IN_PROGRESS" if in_progress else "COMPLETED"
    prefix_by_type: Dict[str, Optional[str]] = {"pile": None, "beam": None}
    current_type = "pile"

    for raw_line in text.splitlines():
        if not raw_line.strip():
            continue
        clean = _clean_line(raw_line)
        component_type = _line_type(raw_line) or current_type
        current_type = component_type
        codes, final_prefix = _codes_in_line(
            clean, component_type, prefix_by_type.get(component_type)
        )
        prefix_by_type[component_type] = final_prefix
        phrase = _work_phrase(clean, component_type)
        if not codes:
            if phrase:
                verb = phrase
                current_work = verb
                work_by_type[component_type] = verb
            continue
        work_text = work_by_type.get(component_type) or current_work or phrase or ""
        if not work_text:
            work_text = "đục" if component_type == "pile" else "đục"
        parsed_line = _ParsedLine(
            component_type=component_type,
            work_text=(
                f"Cọc {work_text}" if component_type == "pile" and not work_text.casefold().startswith("cọc")
                else f"Dầm {work_text}" if component_type == "beam" and not work_text.casefold().startswith("dầm")
                else work_text
            ),
        )
        for raw_token, code in codes:
            matches = lookup.get((component_type, _code_key(code)), [])
            component = matches[0] if matches else None
            parsed_line.items.append(
                _Item(
                    raw=raw_token,
                    code=component.canonical_code if component else code,
                    component=component,
                    status_guess=status_guess,
                )
            )
        lines.append(parsed_line)

    if not any(line.items for line in lines):
        warnings.append("Không đọc được mã cấu kiện nào; cần kiểm tra lại tin nhắn.")

    # Expected zone/segment follows the majority of resolved pile items.
    scope_counts: Counter[Tuple[str, str]] = Counter()
    for line in lines:
        for item in line.items:
            component = item.component
            if component is None or line.component_type != "pile":
                continue
            if component.segment_id in segments:
                segment = segments[component.segment_id]
                scope_counts[(segment.zone_id, segment.id)] += 1
    expected_zone_id, expected_segment_id = (
        scope_counts.most_common(1)[0][0] if scope_counts else (None, None)
    )

    questions: List[ProgressParseQuestionOut] = []
    unknown_codes: List[str] = []
    seen_unknown: set[str] = set()
    seen_duplicates: set[str] = set()
    seen_components: Dict[str, int] = Counter()

    for line in lines:
        for item in line.items:
            if item.component is None:
                if item.code not in seen_unknown:
                    seen_unknown.add(item.code)
                    unknown_codes.append(item.code)
                continue
            seen_components[item.component.id] += 1

    for line in lines:
        if len(line.items) < 2:
            continue
        counts = Counter(_code_key(item.code) for item in line.items if item.component)
        for item in line.items:
            if not item.component:
                continue
            key = _code_key(item.code)
            if counts[key] < 2 or key in seen_duplicates:
                continue
            seen_duplicates.add(key)
            questions.append(
                ProgressParseQuestionOut(
                    id=f"duplicate:{item.code}",
                    kind="duplicate_code",
                    message_vi=(
                        f"Mã {item.code} xuất hiện {counts[key]} lần trong tin nhắn. "
                        "Bạn muốn xử lý thế nào?"
                    ),
                    options=[
                        _question_option("Bỏ trùng", "dedupe"),
                        _question_option("Mã khác", "replace_code"),
                    ],
                )
            )

    for code in unknown_codes:
        questions.append(
            ProgressParseQuestionOut(
                id=f"unknown:{code}",
                kind="unknown_code",
                message_vi=(
                    f"Không tìm thấy mã {code} trong công trình. Bạn muốn xử lý thế nào?"
                ),
                options=[
                    _question_option("Bỏ qua", "skip"),
                    _question_option("Mã khác", "replace_code"),
                ],
            )
        )

    # Candidate stages per line (work phrase + component type).
    line_candidates: Dict[int, List[StageCandidateOut]] = {}
    for index, line in enumerate(lines):
        candidates = _stage_candidates(definitions, line.component_type, line.work_text)
        line_candidates[index] = candidates
        if not candidates:
            warnings.append(
                f"Chưa khớp được công đoạn cho nhóm '{line.work_text}'; cần chọn tay."
            )

    stage_by_component: Dict[str, List[ComponentStage]] = {}
    for stage in stages:
        stage_by_component.setdefault(stage.component_id, []).append(stage)
    completed_events = [
        event for event in events if event.status == "COMPLETED" and event_date is not None
    ]
    seen_completed: set[str] = set()

    for index, line in enumerate(lines):
        candidates = line_candidates[index]
        candidate_ids = {candidate.stage_definition_id for candidate in candidates}
        stage_ids = {
            stage.id
            for stage in stages
            if stage.component_id in {item.component.id for item in line.items if item.component}
            and stage.stage_definition_id in candidate_ids
        }
        for item in line.items:
            component = item.component
            if component is None:
                continue

            # Multiple plausible stages for the work phrase.
            if len(candidates) > 1 and item.component.id not in {
                q.id.split("stage:", 1)[1] for q in questions if q.kind == "multiple_stage"
            }:
                questions.append(
                    ProgressParseQuestionOut(
                        id=f"stage:{component.id}",
                        kind="multiple_stage",
                        message_vi=(
                            f"Cấu kiện {component.canonical_code} có {len(candidates)} công "
                            f"đoạn khớp '{line.work_text}'. Chọn công đoạn đúng:"
                        ),
                        options=[
                            _question_option(candidate.name, candidate.stage_definition_id)
                            for candidate in candidates
                        ],
                    )
                )

            earlier = [
                event
                for event in completed_events
                if event_date is not None
                and event.component_id == component.id
                and event.component_stage_id in stage_ids
                and event.event_date < event_date
            ]
            if earlier:
                latest = max(earlier, key=lambda event: event.event_date)
                if latest.id in seen_completed:
                    continue
                seen_completed.add(latest.id)
                questions.append(
                    ProgressParseQuestionOut(
                        id=f"completed:{component.id}:{latest.id}",
                        kind="completed_earlier",
                        message_vi=(
                            f"{component.canonical_code} đã có COMPLETED ngày "
                            f"{latest.event_date:%d/%m/%Y}, trước ngày {event_date:%d/%m/%Y}. "
                            "Bạn muốn ghi thế nào?"
                        ),
                        options=[
                            _question_option("Ghi thêm hoàn thành", "add_completed"),
                            _question_option(
                                "Ngày trước là đang làm, hôm nay xong",
                                "previous_was_in_progress",
                            ),
                            _question_option("Bỏ qua", "skip"),
                        ],
                    )
                )

    # Components explicitly included in a construction batch are executed with
    # this message even when their design zone/segment differs.
    batch_component_ids: set[str] = set()
    if batch_id:
        batch = db.get(ConstructionBatch, batch_id)
        if batch is None or batch.project_id != project_id:
            warnings.append(
                "Đợt thi công đã chọn không thuộc công trình; không bỏ qua kiểm tra phạm vi."
            )
        else:
            batch_component_ids = set(
                db.scalars(
                    select(ConstructionBatchComponent.component_id).where(
                        ConstructionBatchComponent.batch_id == batch.id
                    )
                ).all()
            )

    # Components outside the majority zone/segment of this message.
    outside_groups: Dict[Tuple[str, str, str], List[StructuralComponent]] = {}
    for line in lines:
        for item in line.items:
            component = item.component
            if component is None or component.segment_id not in segments:
                continue
            if component.id in batch_component_ids:
                continue
            segment = segments[component.segment_id]
            if (
                expected_zone_id is not None
                and (segment.zone_id, segment.id) != (expected_zone_id, expected_segment_id)
            ):
                zone_name = zones[segment.zone_id].name if segment.zone_id in zones else "khác"
                outside_groups.setdefault(
                    (zone_name, str(segment.number), line.component_type), []
                ).append(component)
    expected_zone = zones.get(expected_zone_id).name if expected_zone_id in zones else None
    expected_segment = (
        segments.get(expected_segment_id).number if expected_segment_id in segments else None
    )
    for (zone_name, segment_number, component_type), components_outside in outside_groups.items():
        noun = "cọc" if component_type == "pile" else "dầm"
        codes = ", ".join(
            dict.fromkeys(component.canonical_code for component in components_outside)
        )
        questions.append(
            ProgressParseQuestionOut(
                id=f"outside:{zone_name}:{segment_number}:{component_type}",
                kind="outside_scope",
                message_vi=(
                    f"{len(components_outside)} {noun} ({codes}) thuộc {zone_name} - "
                    f"phân đoạn {segment_number}, ngoài phạm vi "
                    f"{expected_zone or 'chính'}"
                    + (f" - PD{expected_segment}" if expected_segment else "")
                    + ". Thi công cùng đợt?"
                ),
                options=[
                    _question_option("Thi công cùng đợt", "include"),
                    _question_option("Bỏ qua", "skip"),
                ],
            )
        )

    if in_progress:
        questions.append(
            ProgressParseQuestionOut(
                id="status:in_progress",
                kind="status_confirm",
                message_vi=(
                    "Tin nhắn có chữ 'đang' nên trạng thái được hiểu là đang thi công. "
                    "Xác nhận trạng thái ghi hôm nay:"
                ),
                options=[
                    _question_option("Hoàn thành", "COMPLETED"),
                    _question_option("Đang thi công", "IN_PROGRESS"),
                ],
            )
        )

    if not in_progress:
        warnings.append(
            "Trạng thái mặc định là COMPLETED cho công tác đã làm; sửa nếu thực tế khác."
        )

    out_lines: List[ProgressParseLineOut] = []
    for index, line in enumerate(lines):
        items_out = []
        for item in line.items:
            component = item.component
            segment = (
                segments.get(component.segment_id) if component and component.segment_id in segments else None
            )
            zone = zones.get(segment.zone_id) if segment and segment.zone_id in zones else None
            items_out.append(
                ProgressParseItemOut(
                    raw=item.raw,
                    code=item.code,
                    component_id=component.id if component else None,
                    zone=zone.name if zone else None,
                    segment=segment.number if segment else None,
                    status_guess=item.status_guess,
                )
            )
        out_lines.append(
            ProgressParseLineOut(
                work_text=line.work_text,
                stage_candidates=line_candidates[index],
                component_type=line.component_type,
                items=items_out,
            )
        )

    discovered = {
        component.id for line in lines for item in line.items if (component := item.component)
    }
    expected_ids = {
        component.id
        for component in components
        if component.segment_id == expected_segment_id
    } if expected_segment_id else set()
    outside_ids = (discovered - expected_ids) - batch_component_ids if expected_ids else set()
    if outside_ids:
        warnings.append(
            f"{len(outside_ids)} cấu kiện nằm ngoài phân đoạn chính; xác nhận trước khi ghi."
        )

    return ProgressParseResponse(
        event_date=event_date,
        date_source=date_source,
        batch_id=batch_id,
        lines=out_lines,
        questions=questions,
        unknown_codes=unknown_codes,
        warnings=warnings,
    )
