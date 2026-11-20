"""Read-only candidate pipeline for the DAP design review.

The pipeline consumes structured rows that already exist in the local review
database (``data/storage/design-review/dap-design.sqlite3``) or mappings with
the same columns.  It never reads a PDF, never runs OCR, never writes to the
review database or the application database, and never invents a code: a
candidate is only emitted for an exact code present in a source row, with its
project/zone/segment/stage/group and source provenance attached.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Sequence

PILE_CODE = re.compile(r"^[A-Z]{1,2}\d{1,3}$")
BEAM_CODE = re.compile(r"^[A-Z]{1,3}-?\d{1,3}-\d{1,3}$")
KIND_PATTERNS = {"PILE": PILE_CODE, "BEAM": BEAM_CODE}
DESIGN_SHEETS = {"01_COC": "PILE", "02_DAM": "BEAM"}
NUMBER_RE = re.compile(r"^-?\d+(?:\.\d+)?$")
REVIEW_STATUS = "NEEDS_REVIEW"
GROUP_RANGE = range(1, 4)


@dataclass(frozen=True)
class SourceRef:
    source_hash: str
    source_name: str
    source_kind: str
    page: Optional[int] = None
    drawing: Optional[str] = None
    sheet: Optional[str] = None
    row: Optional[int] = None
    column: Optional[str | int] = None


@dataclass(frozen=True)
class ComponentCandidate:
    project_id: str
    stage: Optional[str]
    revision: Optional[str]
    zone: str
    segment: int
    kind: str
    design_group: Optional[int]
    raw_code: str
    canonical_code: str
    review_status: str
    source: SourceRef


@dataclass(frozen=True)
class DesignWorkItem:
    project_id: str
    stage: Optional[str]
    revision: Optional[str]
    zone: str
    segment: int
    kind: str
    code: str
    work_name: str
    unit: Optional[str]
    value: float
    raw_value: str
    source: SourceRef
    evidence_kind: Optional[str] = None
    note: Optional[str] = None
    design_group: Optional[int] = None


@dataclass(frozen=True)
class ReviewNote:
    source: SourceRef
    zone: Optional[str]
    note: str


@dataclass(frozen=True)
class CandidateReport:
    project_id: str
    stage: Optional[str]
    revision: Optional[str]
    components: tuple[ComponentCandidate, ...]
    work_items: tuple[DesignWorkItem, ...]
    notes: tuple[ReviewNote, ...]
    conflicts: tuple[str, ...]
    rejected: tuple[dict[str, Any], ...]
    pages_needing_review: tuple[int, ...]


@dataclass(frozen=True)
class StagingResult:
    items: tuple[DesignWorkItem, ...]
    inserted: int
    existing: int
    conflicts: tuple[str, ...]
    rejected: tuple[dict[str, Any], ...]


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _source(sources: Mapping[str, Any], source_hash: str) -> Optional[SourceRef]:
    item = sources.get(source_hash)
    if not item:
        return None
    get = item.get if isinstance(item, Mapping) else lambda key, default=None: getattr(item, key, default)
    return SourceRef(
        source_hash=source_hash,
        source_name=_text(get("name")),
        source_kind=_text(get("kind")),
    )


def _with(source: SourceRef, **fields: Any) -> SourceRef:
    return SourceRef(
        source_hash=source.source_hash,
        source_name=source.source_name,
        source_kind=source.source_kind,
        page=fields.get("page", source.page),
        drawing=fields.get("drawing", source.drawing),
        sheet=fields.get("sheet", source.sheet),
        row=fields.get("row", source.row),
        column=fields.get("column", source.column),
    )


def _number(value: Any) -> Optional[float]:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text or text.startswith("=") or not NUMBER_RE.match(text):
        return None
    return float(text)


def _component_candidates(
    rows: Iterable[Mapping[str, Any]],
    sources: Mapping[str, Any],
    *,
    project_id: str,
    stage: Optional[str],
    revision: Optional[str],
    conflicts: list[str],
    rejected: list[dict[str, Any]],
) -> list[ComponentCandidate]:
    candidates: list[ComponentCandidate] = []
    seen: dict[tuple[str, int, str, str], ComponentCandidate] = {}
    for row in rows:
        raw = _text(row.get("raw_code"))
        kind = _text(row.get("kind")).upper()
        zone = _text(row.get("zone"))
        segment = row.get("segment")
        group = row.get("design_group")
        status = _text(row.get("review_status")).upper()
        source = _source(sources, _text(row.get("source_hash")))
        page = row.get("page")
        drawing = _text(row.get("drawing"))
        reason = None
        if kind not in KIND_PATTERNS:
            reason = f"kind {kind!r} is not PILE/BEAM"
        elif not raw:
            reason = "code is missing"
        elif not KIND_PATTERNS[kind].match(raw.upper()):
            reason = f"code {raw!r} is not an accepted {kind} code"
        elif not zone:
            reason = "zone is missing"
        elif isinstance(segment, bool) or not isinstance(segment, int) or segment < 1:
            reason = "segment is missing or invalid"
        elif group is not None and (isinstance(group, bool) or group not in GROUP_RANGE):
            reason = f"design group {group!r} is not 1..3"
        elif status != REVIEW_STATUS:
            reason = f"review_status must stay {REVIEW_STATUS}, got {status or 'missing'}"
        elif source is None:
            reason = f"unknown source hash {row.get('source_hash')!r}"
        elif isinstance(page, bool) or not isinstance(page, int) or page < 1:
            reason = "page is required for drawing provenance"
        elif not drawing:
            reason = "drawing number is required for drawing provenance"
        if reason is not None:
            conflicts.append(f"component {raw or '?'}: {reason}")
            rejected.append({"raw_code": raw, "reason": reason, "source_hash": row.get("source_hash")})
            continue

        canonical = raw.upper()
        candidate = ComponentCandidate(
            project_id=project_id,
            stage=stage,
            revision=revision,
            zone=zone,
            segment=segment,
            kind=kind,
            design_group=group,
            raw_code=raw,
            canonical_code=canonical,
            review_status=REVIEW_STATUS,
            source=_with(source, page=page, drawing=drawing),
        )
        key = (zone, segment, kind, canonical)
        previous = seen.get(key)
        if previous is not None:
            if previous.design_group != group:
                conflicts.append(
                    f"component {canonical}: group conflict "
                    f"{previous.design_group} on page {previous.source.page} vs "
                    f"{group} on page {page}"
                )
            elif (previous.source.page, previous.source.drawing) != (page, drawing):
                conflicts.append(
                    f"component {canonical}: duplicate candidate on page {page} "
                    f"and page {previous.source.page}"
                )
            continue
        seen[key] = candidate
        candidates.append(candidate)
    return candidates


def _work_items(
    rows: Iterable[Mapping[str, Any]],
    sources: Mapping[str, Any],
    *,
    project_id: str,
    stage: Optional[str],
    revision: Optional[str],
    conflicts: list[str],
    rejected: list[dict[str, Any]],
) -> list[DesignWorkItem]:
    grouped: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for row in rows:
        sheet = _text(row.get("sheet"))
        if not sheet.startswith(tuple(DESIGN_SHEETS)):
            continue
        grouped.setdefault((_text(row.get("source_hash")), sheet), []).append(row)

    items: list[DesignWorkItem] = []
    seen: set[tuple[str, str, int, int]] = set()
    values: dict[tuple[str, str, str, str], float] = {}
    for (source_hash, sheet), block in grouped.items():
        source = _source(sources, source_hash)
        if source is None:
            conflicts.append(f"work sheet {sheet}: unknown source hash {source_hash!r}")
            continue
        kind = next(kind for prefix, kind in DESIGN_SHEETS.items() if sheet.startswith(prefix))
        header: dict[int, str] = {}
        for row in sorted(block, key=lambda item: int(item.get("row_number") or 0)):
            row_number = int(row.get("row_number") or 0)
            try:
                cells = json.loads(row.get("cells_json") or "[]")
            except (TypeError, ValueError):
                conflicts.append(f"work sheet {sheet} row {row_number}: invalid cells_json")
                continue
            if not isinstance(cells, list):
                continue
            if _text(cells[0] if cells else "").upper() == "STT":
                header = {
                    index: _text(cell).upper()
                    for index, cell in enumerate(cells)
                    if index >= 3 and cell is not None
                }
                continue
            if not header or row_number < 1:
                continue
            work_name = _text(cells[1] if len(cells) > 1 else "")
            if not work_name:
                continue
            unit = _text(cells[2] if len(cells) > 2 else "") or None
            segment = row.get("segment")
            zone = _text(row.get("zone"))
            if not zone or isinstance(segment, bool) or not isinstance(segment, int) or segment < 1:
                conflicts.append(f"work sheet {sheet} row {row_number}: zone/segment missing")
                continue
            for column, code in header.items():
                if column >= len(cells):
                    continue
                value = _number(cells[column])
                if value is None:
                    continue
                if not KIND_PATTERNS[kind].match(code):
                    continue
                key = (source_hash, sheet, row_number, column)
                if key in seen:
                    continue
                seen.add(key)
                value_key = (kind, code, work_name, unit or "")
                previous = values.get(value_key)
                if previous is not None and previous != value:
                    conflicts.append(
                        f"work {code} {work_name}: value conflict "
                        f"{previous} at {sheet}!{row_number} vs {value}"
                    )
                else:
                    values[value_key] = value
                items.append(
                    DesignWorkItem(
                        project_id=project_id,
                        stage=stage,
                        revision=revision,
                        zone=zone,
                        segment=segment,
                        kind=kind,
                        code=code,
                        work_name=work_name,
                        unit=unit,
                        value=value,
                        raw_value=_text(cells[column]),
                        source=_with(source, sheet=sheet, row=row_number, column=column + 1),
                        evidence_kind="direct",
                    )
                )
    return items


def build_candidate_report(
    *,
    components: Iterable[Mapping[str, Any]],
    sources: Mapping[str, Any],
    notes: Iterable[Mapping[str, Any]] = (),
    thkl_rows: Iterable[Mapping[str, Any]] = (),
    project_id: str,
    stage: Optional[str] = None,
    revision: Optional[str] = None,
) -> CandidateReport:
    """Build review-only candidates; nothing is written or promoted."""

    project_id = _text(project_id)
    stage = _text(stage) or None
    revision = _text(revision) or None
    if not project_id:
        raise ValueError("project_id is required")

    conflicts: list[str] = []
    rejected: list[dict[str, Any]] = []
    candidates = _component_candidates(
        components,
        sources,
        project_id=project_id,
        stage=stage,
        revision=revision,
        conflicts=conflicts,
        rejected=rejected,
    )
    work_items = _work_items(
        thkl_rows,
        sources,
        project_id=project_id,
        stage=stage,
        revision=revision,
        conflicts=conflicts,
        rejected=rejected,
    )
    review_notes: list[ReviewNote] = []
    for row in notes:
        source = _source(sources, _text(row.get("source_hash")))
        if source is None:
            conflicts.append(f"note: unknown source hash {row.get('source_hash')!r}")
            continue
        page = row.get("page")
        review_notes.append(
            ReviewNote(
                source=_with(
                    source,
                    page=page if isinstance(page, int) and not isinstance(page, bool) else None,
                    drawing=_text(row.get("drawing")) or None,
                ),
                zone=_text(row.get("zone")) or None,
                note=_text(row.get("note")),
            )
        )

    pages = {c.source.page for c in candidates if c.source.page}
    pages.update(note.source.page for note in review_notes if note.source.page)
    return CandidateReport(
        project_id=project_id,
        stage=stage,
        revision=revision,
        components=tuple(candidates),
        work_items=tuple(work_items),
        notes=tuple(review_notes),
        conflicts=tuple(conflicts),
        rejected=tuple(rejected),
        pages_needing_review=tuple(sorted(pages)),
    )


def load_review_database(path: str | Path) -> dict[str, Any]:
    """Read the review database in mode=ro; never creates or migrates it."""

    db_path = Path(path).resolve()
    if not db_path.is_file():
        raise FileNotFoundError(db_path)
    connection = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    try:
        connection.execute("pragma query_only = on")
        sources = {
            row["hash"]: row
            for row in (
                dict(zip(("hash", "name", "kind"), values))
                for values in connection.execute("select hash, name, kind from sources")
            )
        }
        components = [
            dict(zip(
                ("source_hash", "zone", "segment", "kind", "design_group", "raw_code",
                 "page", "drawing", "review_status", "note"),
                values,
            ))
            for values in connection.execute(
                "select source_hash, zone, segment, kind, design_group, raw_code, page, "
                "drawing, review_status, note from component_candidates order by zone, segment, kind, raw_code"
            )
        ]
        notes = [
            dict(zip(("source_hash", "page", "drawing", "zone", "note"), values))
            for values in connection.execute(
                "select source_hash, page, drawing, zone, notes from drawing_notes "
                "order by page, zone"
            )
        ]
        thkl_rows = [
            dict(zip(
                ("source_hash", "sheet", "row_number", "zone", "segment",
                 "entry_kind", "review_status", "cells_json"),
                values,
            ))
            for values in connection.execute(
                "select source_hash, sheet, row_number, zone, segment, entry_kind, "
                "review_status, cells_json from thkl_rows order by sheet, row_number"
            )
        ]
        return {
            "sources": sources,
            "components": components,
            "notes": notes,
            "thkl_rows": thkl_rows,
        }
    finally:
        connection.close()


def build_from_review_database(
    path: str | Path,
    *,
    project_id: str,
    stage: Optional[str] = None,
    revision: Optional[str] = None,
) -> CandidateReport:
    dataset = load_review_database(path)
    return build_candidate_report(
        components=dataset["components"],
        sources=dataset["sources"],
        notes=dataset["notes"],
        thkl_rows=dataset["thkl_rows"],
        project_id=project_id,
        stage=stage,
        revision=revision,
    )


def _int(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    text = _text(value)
    return int(text) if text.isdigit() else None


def _source_by_name(
    sources: Mapping[str, Any], name: str
) -> tuple[Optional[str], Optional[Mapping[str, Any]]]:
    for source_hash, item in sources.items():
        get = item.get if isinstance(item, Mapping) else lambda key, default=None: getattr(item, key, default)
        if _text(get("name")) == name:
            return source_hash, item
    return None, None


def facts_to_work_items(
    page: Mapping[str, Any],
    *,
    sources: Mapping[str, Any],
    project_id: str,
    revision: Optional[str] = None,
    conflicts: Optional[list[str]] = None,
) -> list[DesignWorkItem]:
    """Turn visual-confirmed page facts into work items with cell provenance.

    Only numeric facts with a source page, sheet, row and column are accepted.
    Identity/text facts are skipped; incomplete provenance is reported.
    """

    project_id = _text(project_id)
    if not project_id:
        raise ValueError("project_id is required")
    problems = conflicts if conflicts is not None else []
    name = _text(page.get("document_name"))
    source_hash, _ = _source_by_name(sources, name)
    if source_hash is None:
        raise ValueError(f"source {name!r} is not registered")
    page_number = _int(page.get("page_number"))
    extraction = page.get("extraction") or {}
    drawing = _text(extraction.get("drawing_number"))
    if page_number is None or page_number < 1:
        raise ValueError("page_number is required")
    if not drawing:
        raise ValueError("drawing_number is required")
    page_revision = (
        _text(page.get("revision"))
        or _text(extraction.get("revision"))
        or (_text(revision) or None)
    )
    source = _source(sources, source_hash)
    items: list[DesignWorkItem] = []
    for fact in extraction.get("component_facts") or []:
        if not isinstance(fact, Mapping):
            continue
        value = _number(fact.get("value"))
        if value is None:
            continue
        kind = _text(fact.get("component_type")).upper()
        code = _text(fact.get("component_code")).upper()
        zone = _text(fact.get("location"))
        group = _int(fact.get("group"))
        segment = _int(fact.get("segment"))
        unit = _text(fact.get("unit"))
        sheet = _text(fact.get("source_sheet"))
        row = _int(fact.get("source_row"))
        column = _text(fact.get("source_column"))
        source_page = _int(fact.get("source_page"))
        evidence = _text(fact.get("evidence_kind")).lower()
        work_name = _text(fact.get("fact_name"))
        reason = None
        if kind not in KIND_PATTERNS:
            reason = f"kind {kind!r} is not PILE/BEAM"
        elif not KIND_PATTERNS[kind].match(code):
            reason = f"code {code!r} is not an accepted {kind} code"
        elif not zone:
            reason = "location/zone is missing"
        elif group not in GROUP_RANGE or segment is None or segment < 1:
            reason = "group/segment is missing"
        elif not work_name:
            reason = "fact name is missing"
        elif not unit:
            reason = "unit is missing"
        elif evidence not in {"direct", "joined"}:
            reason = "evidence_kind must be direct or joined"
        elif source_page != page_number:
            reason = f"source_page {source_page!r} does not match page {page_number}"
        elif not sheet or row is None or row < 1 or not column:
            reason = "source sheet/row/column is required"
        if reason is not None:
            problems.append(f"fact {code or '?'} {work_name or '?'}: {reason}")
            continue
        items.append(
            DesignWorkItem(
                project_id=project_id,
                stage=None,
                revision=page_revision,
                zone=zone,
                segment=segment,
                kind=kind,
                code=code,
                work_name=work_name,
                unit=unit,
                value=value,
                raw_value=_text(fact.get("value")),
                source=_with(
                    source,
                    page=page_number,
                    drawing=drawing,
                    sheet=sheet,
                    row=row,
                    column=column,
                ),
                evidence_kind=evidence,
                note=_text(fact.get("join_note")) or None,
                design_group=group,
            )
        )
    return items


WORK_ITEMS_SQL = """
create table if not exists design_work_items(
    id text primary key,
    project_id text not null,
    stage text,
    revision text,
    source_hash text not null,
    zone text not null,
    segment integer not null,
    kind text not null,
    code text not null,
    design_group integer,
    work_name text not null,
    unit text,
    value real not null,
    raw_value text,
    page integer,
    sheet text,
    row_number integer,
    column_number text,
    evidence_kind text,
    review_status text not null,
    note text
)
"""


def _item_id(item: DesignWorkItem) -> str:
    parts = (
        item.project_id,
        item.stage or "",
        item.revision or "",
        item.source.source_hash,
        item.kind,
        item.code,
        item.work_name,
        item.unit or "",
        item.source.page or 0,
        item.source.sheet or "",
        item.source.row or 0,
        str(item.source.column or ""),
    )
    return hashlib.sha256("|".join(str(part) for part in parts).encode()).hexdigest()


def _sandbox_path(path: str | Path) -> Path:
    resolved = Path(path).resolve()
    if resolved.name == "app.db":
        raise ValueError("the application database is not a staging target")
    if resolved.parent.name != "design-review":
        raise ValueError("staging is limited to the design-review sandbox")
    return resolved


def stage_review_database(
    path: str | Path,
    *,
    project_id: str,
    fixtures: Iterable[Mapping[str, Any]] = (),
    stage: Optional[str] = None,
    revision: Optional[str] = None,
) -> StagingResult:
    """Stage validated work items into the sandbox; component candidates are untouched."""

    db_path = _sandbox_path(path)
    dataset = load_review_database(db_path)
    report = build_candidate_report(
        components=dataset["components"],
        sources=dataset["sources"],
        notes=dataset["notes"],
        thkl_rows=dataset["thkl_rows"],
        project_id=project_id,
        stage=stage,
        revision=revision,
    )
    conflicts = list(report.conflicts)
    rejected = list(report.rejected)
    items = list(report.work_items)
    candidates = {
        (candidate.segment, candidate.kind, candidate.canonical_code): candidate
        for candidate in report.components
    }
    for page in fixtures:
        for item in facts_to_work_items(
            page,
            sources=dataset["sources"],
            project_id=project_id,
            revision=revision,
            conflicts=conflicts,
        ):
            candidate = candidates.get((item.segment, item.kind, item.code))
            if candidate and (
                candidate.design_group != item.design_group or candidate.zone != item.zone
            ):
                conflicts.append(
                    f"work {item.code}: identity mismatch with candidate "
                    f"(group {candidate.design_group}, {candidate.zone})"
                )
                rejected.append({"code": item.code, "reason": "identity mismatch"})
                continue
            items.append(item)

    unique: dict[str, DesignWorkItem] = {}
    for item in items:
        unique.setdefault(_item_id(item), item)
    items = list(unique.values())

    connection = sqlite3.connect(db_path)
    try:
        connection.execute(WORK_ITEMS_SQL)
        before = connection.execute("select count(*) from design_work_items").fetchone()[0]
        connection.executemany(
            "insert or ignore into design_work_items("
            "id, project_id, stage, revision, source_hash, zone, segment, kind, code, "
            "design_group, work_name, unit, value, raw_value, page, sheet, row_number, "
            "column_number, evidence_kind, review_status, note"
            ") values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [
                (
                    _item_id(item),
                    item.project_id,
                    item.stage,
                    item.revision,
                    item.source.source_hash,
                    item.zone,
                    item.segment,
                    item.kind,
                    item.code,
                    item.design_group,
                    item.work_name,
                    item.unit,
                    item.value,
                    item.raw_value,
                    item.source.page,
                    item.source.sheet,
                    item.source.row,
                    None if item.source.column is None else str(item.source.column),
                    item.evidence_kind,
                    "NEEDS_REVIEW",
                    item.note,
                )
                for item in items
            ],
        )
        connection.commit()
        after = connection.execute("select count(*) from design_work_items").fetchone()[0]
    finally:
        connection.close()
    inserted = after - before
    return StagingResult(
        items=tuple(items),
        inserted=inserted,
        existing=len(items) - inserted,
        conflicts=tuple(conflicts),
        rejected=tuple(rejected),
    )
