"""Read proposed pile-group plan rows without treating them as verified facts.

The plan sheets are merged-cell tables: group/segment values frequently sit in
a single cell covering a block of rows, and one page may contain several
segments.  A row is therefore never given a group/segment from a guessed page
position; it gets one only when the extraction carries that value for the
block.  When a page was read more than once, the readings are compared row by
row and disagreements are reported instead of silently merged.
"""

from __future__ import annotations

import difflib
import json
import re
from dataclasses import dataclass
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from .embeddings import fold_text
from .models import DocumentPage, PageExtraction, SourceDocument


_CODE = re.compile(r"[A-Z]\d{1,3}")
_TITLE = re.compile(r"MAT BANG NHOM COC NHOM\s+([123])\b")
_REGISTER_TITLE = re.compile(r"BANG THONG KE COC HU HONG NHOM\s+(I{1,3}|[123])\b")
_ROMAN = {"I": "1", "II": "2", "III": "3"}
_FOOTER_LABELS = {
    "CTTK",
    "THIET KE",
    "KIEM TRA",
    "KCS",
    "TY LE",
    "LAN",
    "NHA THAU",
    "CHU DAU TU",
}


@dataclass(frozen=True)
class PileGroupEntry:
    code: str
    location: str | None
    segment: str | None
    crack_length: str | None
    document_id: str
    page_number: int
    table_row: int
    url: str
    ambiguous: bool = False
    group: str | None = None
    quote: str = ""
    drawing_number: str | None = None
    revision: str | None = None
    block: str = ""


@dataclass(frozen=True)
class PileGroupResult:
    entries: tuple[PileGroupEntry, ...]
    raw_count: int
    warnings: tuple[str, ...]


@dataclass
class _PendingRow:
    row_index: int
    cells: list[str]
    codes: list[tuple[str, bool]]
    metadata: list[tuple[str, str]]


@dataclass
class _Block:
    key: str
    columns: dict[str, int]
    header_metadata: list[tuple[str, str]]
    rows: list[_PendingRow]


def _norm(value: object) -> str:
    return fold_text(str(value or "")).strip().upper()


def _number(value: object) -> str | None:
    match = re.search(r"\d+", _norm(value))
    return str(int(match.group())) if match else None


def _unique(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _metadata(value: object) -> tuple[str, str] | None:
    """Return ``(role, value)`` for a merged-cell label, never for a code."""

    text = _norm(value)
    if not text:
        return None
    match = re.search(r"(?:NHOM|PHAN LOAI)\s*(?:NHOM\s*)?(I{1,3}|[123])\b", text)
    if match:
        raw = match.group(1)
        return ("group", _ROMAN.get(raw, raw))
    match = re.search(r"\b(?:PHAN\s*)?DOAN\s*(\d{1,3})\b", text)
    if match:
        return ("segment", str(int(match.group(1))))
    if "CAU CHINH" in text:
        return ("location", "Cầu chính")
    if "CAU DAN" in text:
        return ("location", "Cầu dẫn")
    return None


def _page_location(data: dict) -> str | None:
    """Use an explicit page title/summary location, never a majority guess."""

    text = _norm(f"{data.get('title') or ''} {data.get('summary') or ''}")
    main = "CAU CHINH" in text
    approach = "CAU DAN" in text
    if main and not approach:
        return "Cầu chính"
    if approach and not main:
        return "Cầu dẫn"
    return None


def _page_segment(data: dict) -> str | None:
    text = _norm(f"{data.get('title') or ''} {data.get('summary') or ''}")
    values = {
        str(int(match.group(1)))
        for match in re.finditer(r"\b(?:PHAN\s*)?DOAN\s*(\d{1,3})\b", text)
    }
    return next(iter(values)) if len(values) == 1 else None


def _plan_header(cells: list[str]) -> dict[str, int] | None:
    normalized = [_norm(cell) for cell in cells]
    code_index = next(
        (
            index
            for index, cell in enumerate(normalized)
            if re.fullmatch(r"TEN COC(?: \((?:KS|KT)\))?[.:]?", cell)
        ),
        None,
    )
    if code_index is None:
        return None
    if not any(
        marker in cell
        for cell in normalized
        for marker in ("PHAN LOAI", "PHAN DOAN", "VI TRI", "NHOM")
    ):
        return None
    columns: dict[str, int] = {"code": code_index}
    for index, cell in enumerate(normalized):
        if index == code_index:
            continue
        if "PHAN DOAN" in cell:
            columns.setdefault("segment", index)
        elif "PHAN LOAI" in cell or re.search(r"\bNHOM\b", cell):
            columns.setdefault("group", index)
        if "VI TRI" in cell:
            columns.setdefault("location", index)
        if "CHIEU DAI" in cell:
            columns.setdefault("crack", index)
    return columns


def _tokens(cell: str) -> list[tuple[str, bool]]:
    """Return ``(token, is_exact_code)`` for one table cell."""

    tokens: list[tuple[str, bool]] = []
    for piece in re.split(r"[,;\s]+", str(cell or "").strip().upper()):
        raw = piece.strip()
        if "..." in raw:
            tokens.append((raw, False))
            continue
        token = raw.strip(" .;:-")
        if not token:
            continue
        if _CODE.fullmatch(token):
            tokens.append((token, True))
        elif re.fullmatch(r"\d{1,3}", token) or re.fullmatch(
            r"[A-Z]{1,3}\d{1,5}", token
        ):
            tokens.append((token, False))
    return tokens


def _row_codes(cells: list[str], columns: dict[str, int]) -> list[tuple[str, bool]]:
    code_index = columns.get("code")
    if code_index is not None and code_index < len(cells):
        preferred = _tokens(cells[code_index])
        if preferred:
            exact_present = any(exact for _, exact in preferred)
            selected = [
                (token, exact)
                for token, exact in preferred
                if exact
                or "..." in token
                or (exact_present and re.fullmatch(r"\d{1,3}", token))
            ]
            if selected:
                return selected
    # A shifted OCR row (page 9) can put the code one column to the left.
    found: list[tuple[str, bool]] = []
    for index, cell in enumerate(cells):
        if index == code_index:
            continue
        found.extend((token, exact) for token, exact in _tokens(cell) if exact)
    return found


def _finalise_block(
    block: _Block,
    *,
    page: DocumentPage,
    document: SourceDocument,
    data: dict,
    project_id: str,
    group_number: str,
    page_location: str | None,
    page_segment: str | None,
    warnings: list[str],
) -> tuple[list[PileGroupEntry], int]:
    group_values = _unique(
        value for role, value in block.header_metadata if role == "group"
    )
    segment_values = _unique(
        value for role, value in block.header_metadata if role == "segment"
    )
    location_values = _unique(
        value for role, value in block.header_metadata if role == "location"
    )
    for row in block.rows:
        group_values = _unique(
            group_values + [value for role, value in row.metadata if role == "group"]
        )
        segment_values = _unique(
            segment_values
            + [value for role, value in row.metadata if role == "segment"]
        )
        location_values = _unique(
            location_values
            + [value for role, value in row.metadata if role == "location"]
        )

    default_group = group_values[0] if len(group_values) == 1 else None
    default_segment = (
        segment_values[0] if len(segment_values) == 1 else page_segment
    )
    default_location = (
        location_values[0] if len(location_values) == 1 else page_location
    )

    timeline: dict[int, list[tuple[str, str]]] = {}
    for row in block.rows:
        for role, value in row.metadata:
            timeline.setdefault(row.row_index, []).append((role, value))

    current_group = default_group
    current_segment = default_segment
    current_location = default_location
    entries: list[PileGroupEntry] = []
    seen_codes: set[
        tuple[str, str | None, str | None, str | None]
    ] = set()
    raw_count = sum(len(row.codes) for row in block.rows)
    for row in block.rows:
        for role, value in timeline.get(row.row_index, []):
            if role == "group":
                current_group = value
            elif role == "segment":
                current_segment = value
            elif role == "location":
                current_location = value
        # Values placed after a block (merged cells are commonly read last)
        # already became the single default for the whole block above.
        if len(group_values) == 1:
            current_group = default_group
        if len(segment_values) == 1:
            current_segment = default_segment
        if len(location_values) == 1:
            current_location = default_location
        quote = " | ".join(cell for cell in row.cells if cell)[:300]
        for token, exact in row.codes:
            duplicate_key = (
                token,
                current_group,
                current_segment,
                current_location,
            )
            if duplicate_key in seen_codes:
                warnings.append(
                    f"Trang {page.page_number}, dòng {row.row_index}: "
                    f"mã cọc lặp trong cùng bảng '{token}', đã bỏ dòng lặp."
                )
                continue
            if not exact:
                warnings.append(
                    f"Trang {page.page_number}, dòng {row.row_index}: "
                    f"mã cọc không rõ '{token}'."
                )
                if not re.fullmatch(r"\d{1,3}", token) or not (
                    current_location and current_segment
                ):
                    continue
            seen_codes.add(duplicate_key)
            entries.append(
                PileGroupEntry(
                    code=token,
                    location=current_location,
                    segment=current_segment,
                    crack_length=(
                        row.cells[block.columns["crack"]]
                        if "crack" in block.columns
                        and block.columns["crack"] < len(row.cells)
                        and row.cells[block.columns["crack"]]
                        else None
                    ),
                    document_id=document.id,
                    page_number=page.page_number,
                    table_row=row.row_index,
                    url=(
                        f"/projects/{project_id}/documents/{document.id}"
                        f"/pages/{page.page_number}"
                    ),
                    ambiguous=not exact,
                    group=current_group or group_number,
                    quote=quote,
                    drawing_number=data.get("drawing_number") or page.drawing_number,
                    revision=data.get("revision") or page.revision,
                    block=block.key,
                )
            )
    return entries, raw_count


def _parse_plan_tables(
    data: dict,
    *,
    page: DocumentPage,
    document: SourceDocument,
    extraction: PageExtraction,
    project_id: str,
    group_number: str,
    warnings: list[str],
) -> tuple[list[PileGroupEntry], int]:
    rows = data.get("table_rows")
    if not isinstance(rows, list):
        return [], 0
    page_location = _page_location(data)
    page_segment = _page_segment(data)
    entries: list[PileGroupEntry] = []
    raw_count = 0
    block: _Block | None = None
    block_index = 0
    saw_block = False
    skipped_after_reset = 0

    def finish() -> None:
        nonlocal block, raw_count
        if block is not None:
            block_entries, block_raw = _finalise_block(
                block,
                page=page,
                document=document,
                data=data,
                project_id=project_id,
                group_number=group_number,
                page_location=page_location,
                page_segment=page_segment,
                warnings=warnings,
            )
            entries.extend(block_entries)
            raw_count += block_raw
        block = None

    for row_index, row in enumerate(rows):
        if not isinstance(row, list):
            finish()
            continue
        cells = [str(cell or "").strip() for cell in row]
        normalized = [_norm(cell) for cell in cells]
        header = _plan_header(cells)
        if header is not None:
            finish()
            saw_block = True
            block_index += 1
            block = _Block(
                key=f"{extraction.id}:{block_index}",
                columns=header,
                header_metadata=[
                    metadata
                    for cell in cells
                    if (metadata := _metadata(cell)) is not None
                ],
                rows=[],
            )
            continue
        if block is None:
            if saw_block and any(_row_codes(cells, {"code": 0})):
                skipped_after_reset += 1
            continue
        if normalized and normalized[0] in _FOOTER_LABELS:
            finish()
            continue
        if any(_norm(cell) == "TEN COC" for cell in cells) or any(
            "TEN COC" in cell for cell in normalized
        ):
            finish()
            continue
        metadata = [
            metadata for cell in cells if (metadata := _metadata(cell)) is not None
        ]
        codes = _row_codes(cells, block.columns)
        if not codes:
            if metadata:
                block.rows.append(
                    _PendingRow(
                        row_index=row_index, cells=cells, codes=[], metadata=metadata
                    )
                )
                continue
            # A different layout without a pile header (e.g. a label/value
            # continuation) cannot be anchored to this block's segment.
            finish()
            continue
        block.rows.append(
            _PendingRow(
                row_index=row_index, cells=cells, codes=codes, metadata=metadata
            )
        )
    finish()
    if block is None and skipped_after_reset:
        warnings.append(
            f"Trang {page.page_number}: bỏ qua {skipped_after_reset} dòng có mã "
            "cọc sau khi bảng đổi bố cục vì không xác định được phân đoạn; "
            "chưa đưa vào danh sách."
        )
    return entries, raw_count


def _register_group(data: dict) -> str | None:
    match = _REGISTER_TITLE.search(_norm(data.get("title")))
    if not match:
        return None
    raw = match.group(1)
    return _ROMAN.get(raw, raw)


def _parse_register(data: dict) -> dict[str, set[str]]:
    """Return explicit ``location -> codes`` from a repair statistics table."""

    rows = data.get("table_rows")
    if not isinstance(rows, list):
        return {}
    found: dict[str, set[str]] = {}
    code_index: int | None = None
    for row in rows:
        if not isinstance(row, list):
            code_index = None
            continue
        cells = [str(cell or "").strip() for cell in row]
        normalized = [_norm(cell) for cell in cells]
        if "TEN COC" in normalized:
            code_index = normalized.index("TEN COC")
            continue
        if code_index is None or code_index >= len(cells):
            continue
        location = next(
            (
                value
                for cell in cells
                if (value := _metadata(cell)) is not None and value[0] == "location"
            ),
            None,
        )
        if location is None:
            # Do not inherit a location through blank merged cells here: a
            # wrong inheritance mixes cầu chính and cầu dẫn codes.
            continue
        codes = {
            token
            for token, exact in _tokens(cells[code_index])
            if exact
        }
        if codes:
            found.setdefault(location[1], set()).update(codes)
    return found


def _merge_readings(
    primary: list[PileGroupEntry],
    alternate: list[PileGroupEntry],
    *,
    register: set[str],
    page_number: int,
    warnings: list[str],
) -> list[PileGroupEntry]:
    """Align two readings of one table and keep only defensible codes."""

    left = list({entry.code: entry for entry in primary}.values())
    right = list({entry.code: entry for entry in alternate}.values())
    matcher = difflib.SequenceMatcher(
        a=[entry.code for entry in left],
        b=[entry.code for entry in right],
        autojunk=False,
    )
    merged: list[PileGroupEntry] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            merged.extend(left[i1:i2])
            continue
        if tag == "delete":
            for entry in left[i1:i2]:
                if register and entry.code not in register:
                    warnings.append(
                        f"Trang {page_number}: bỏ mã '{entry.code}' chỉ có ở một "
                        "lần đọc và không thấy trong bảng thống kê nhóm."
                    )
                else:
                    merged.append(entry)
            continue
        if tag == "insert":
            for entry in right[j1:j2]:
                if register and entry.code not in register:
                    warnings.append(
                        f"Trang {page_number}: bỏ mã '{entry.code}' chỉ có ở một "
                        "lần đọc và không thấy trong bảng thống kê nhóm."
                    )
                else:
                    merged.append(entry)
                    warnings.append(
                        f"Trang {page_number}: mã '{entry.code}' chỉ có ở một lần "
                        "đọc bảng; cần đối chiếu trang gốc."
                    )
            continue
        # replace: pair by visual/text similarity instead of raw position, so
        # a missing row in one reading does not shift every later comparison.
        left_entries = left[i1:i2]
        right_entries = right[j1:j2]
        candidates = sorted(
            (
                (
                    difflib.SequenceMatcher(
                        None, first.code, second.code
                    ).ratio(),
                    first_index,
                    second_index,
                )
                for first_index, first in enumerate(left_entries)
                for second_index, second in enumerate(right_entries)
            ),
            key=lambda item: (-item[0], item[1], item[2]),
        )
        used_left: set[int] = set()
        used_right: set[int] = set()
        pairs: list[tuple[int, int]] = []
        for ratio, first_index, second_index in candidates:
            if ratio < 0.5:
                break
            if first_index in used_left or second_index in used_right:
                continue
            used_left.add(first_index)
            used_right.add(second_index)
            pairs.append((first_index, second_index))
        for first_index, second_index in sorted(pairs):
            first = left_entries[first_index]
            second = right_entries[second_index]
            if first.code == second.code:
                merged.append(first)
                continue
            first_known = not register or first.code in register
            second_known = not register or second.code in register
            if second_known and not first_known:
                merged.append(second)
                warnings.append(
                    f"Trang {page_number}: hai lần đọc ghi '{first.code}' và "
                    f"'{second.code}'; giữ '{second.code}' theo bảng thống kê nhóm."
                )
            elif first_known and not second_known:
                merged.append(first)
                warnings.append(
                    f"Trang {page_number}: hai lần đọc ghi '{first.code}' và "
                    f"'{second.code}'; giữ '{first.code}'."
                )
            else:
                merged.append(first)
                warnings.append(
                    f"Trang {page_number}: hai lần đọc ghi '{first.code}' và "
                    f"'{second.code}'; giữ '{first.code}', cần đối chiếu trang gốc."
                )
        for first_index, first in enumerate(left_entries):
            if first_index in used_left:
                continue
            if register and first.code not in register:
                warnings.append(
                    f"Trang {page_number}: bỏ mã '{first.code}' chỉ có ở một "
                    "lần đọc và không thấy trong bảng thống kê nhóm."
                )
            else:
                merged.append(first)
        for second_index, second in enumerate(right_entries):
            if second_index in used_right:
                continue
            if register and second.code not in register:
                warnings.append(
                    f"Trang {page_number}: bỏ mã '{second.code}' chỉ có ở một "
                    "lần đọc và không thấy trong bảng thống kê nhóm."
                )
            else:
                merged.append(second)
    return merged


def _reconcile_readings(
    entries: list[PileGroupEntry], register: dict[str, set[str]], warnings: list[str]
) -> list[PileGroupEntry]:
    blocks: dict[str, list[PileGroupEntry]] = {}
    for entry in entries:
        blocks.setdefault(entry.block, []).append(entry)
    contexts: dict[tuple[str, int, str, str, str], list[str]] = {}
    for block_key, block_entries in blocks.items():
        first = block_entries[0]
        context = (
            first.document_id,
            first.page_number,
            first.location or "",
            first.segment or "",
            first.group or "",
        )
        contexts.setdefault(context, []).append(block_key)
    merged_blocks: dict[str, list[PileGroupEntry]] = {}
    for context_blocks in contexts.values():
        if len(context_blocks) == 1:
            merged_blocks[context_blocks[0]] = blocks[context_blocks[0]]
            continue
        context_blocks.sort(key=lambda key: blocks[key][0].table_row)
        primary = context_blocks[0]
        canonical = blocks[primary]
        first = canonical[0]
        corroboration = register.get(first.location or "", set())
        for alternate_key in context_blocks[1:]:
            canonical = _merge_readings(
                canonical,
                blocks[alternate_key],
                register=corroboration,
                page_number=first.page_number,
                warnings=warnings,
            )
        merged_blocks[primary] = canonical
    result: list[PileGroupEntry] = []
    seen_blocks: set[str] = set()
    for entry in entries:
        if entry.block in seen_blocks:
            continue
        seen_blocks.add(entry.block)
        result.extend(merged_blocks.get(entry.block, []))
    return result


def find_proposed_pile_register_codes(
    db: Session,
    project_id: str,
    group: str | int,
    *,
    location: str | None = None,
    scope: str = "effective",
) -> set[str]:
    """Return codes corroborated by a repair statistics table for the group."""

    group_number = _number(group)
    if group_number not in {"1", "2", "3"}:
        return set()
    rows = _proposed_extraction_rows(db, project_id, scope)
    found: set[str] = set()
    for extraction, _page, _document in rows:
        try:
            data = json.loads(extraction.extraction_json)
        except (TypeError, ValueError):
            continue
        if not isinstance(data, dict) or _register_group(data) != group_number:
            continue
        for place, codes in _parse_register(data).items():
            if location and _norm(location) != _norm(place):
                continue
            found.update(codes)
    return found


def _proposed_extraction_rows(
    db: Session, project_id: str, scope: str
) -> list[tuple[PageExtraction, DocumentPage, SourceDocument]]:
    if scope not in {"effective", "history"}:
        raise ValueError("scope must be effective or history")
    conditions = [
        PageExtraction.project_id == project_id,
        DocumentPage.project_id == project_id,
        SourceDocument.project_id == project_id,
        PageExtraction.status == "proposed",
        SourceDocument.status == "ready",
        SourceDocument.type == "drawing",
    ]
    if scope == "effective":
        conditions.append(SourceDocument.is_effective.is_(True))
    return db.execute(
        select(PageExtraction, DocumentPage, SourceDocument)
        .join(
            DocumentPage,
            (PageExtraction.page_id == DocumentPage.id)
            & (PageExtraction.document_id == DocumentPage.document_id),
        )
        .join(SourceDocument, PageExtraction.document_id == SourceDocument.id)
        .where(*conditions)
        .order_by(
            SourceDocument.id,
            DocumentPage.page_number,
            PageExtraction.created_at.desc(),
        )
    ).all()


def find_proposed_pile_group(
    db: Session,
    project_id: str,
    group: str | int,
    *,
    location: str | None = None,
    segment: str | int | None = None,
    scope: str = "effective",
) -> PileGroupResult:
    """Return plan entries and their source rows; ambiguous codes remain literal."""

    group_number = _number(group)
    if group_number not in {"1", "2", "3"}:
        return PileGroupResult((), 0, ())
    rows = _proposed_extraction_rows(db, project_id, scope)
    entries: list[PileGroupEntry] = []
    warnings: list[str] = []
    raw_count = 0
    register: dict[str, set[str]] = {}
    for extraction, page, document in rows:
        try:
            data = json.loads(extraction.extraction_json)
        except (TypeError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        if _register_group(data) == group_number:
            for place, codes in _parse_register(data).items():
                register.setdefault(place, set()).update(codes)
            continue
        match = _TITLE.search(_norm(data.get("title")))
        if not match or match.group(1) != group_number:
            continue
        page_location = _page_location(data)
        if location and page_location and _norm(page_location) != _norm(location):
            continue
        page_entries, page_raw = _parse_plan_tables(
            data,
            page=page,
            document=document,
            extraction=extraction,
            project_id=project_id,
            group_number=group_number,
            warnings=warnings,
        )
        raw_count += page_raw
        entries.extend(page_entries)
    entries = _reconcile_readings(entries, register, warnings)
    if location:
        entries = [
            entry for entry in entries if _norm(entry.location) == _norm(location)
        ]
    if segment:
        entries = [
            entry
            for entry in entries
            if _number(entry.segment) == _number(segment)
        ]
    if location or segment:
        relevant_pages = {entry.page_number for entry in entries}
        warnings = [
            warning
            for warning in warnings
            if not (
                (match := re.match(r"Trang (\d+)\b", warning))
                and int(match.group(1)) not in relevant_pages
            )
        ]
    # Stable ordering preserves the order of codes inside a row (e.g. a
    # merged cell "M297, M299, 299" keeps 299 last for review).
    entries.sort(
        key=lambda entry: (
            entry.document_id,
            entry.page_number,
            entry.table_row,
        )
    )
    return PileGroupResult(tuple(entries), raw_count, tuple(warnings))


def find_proposed_pile_locations(
    db: Session, project_id: str, code: str, *, scope: str = "effective"
) -> tuple[tuple[str, PileGroupEntry], ...]:
    """Find exact pile codes on the three group plans, retaining each source row."""

    wanted = _norm(code)
    if not _CODE.fullmatch(wanted):
        return ()
    return tuple(
        (group, entry)
        for group in ("1", "2", "3")
        for entry in find_proposed_pile_group(db, project_id, group, scope=scope).entries
        if not entry.ambiguous and _norm(entry.code) == wanted
    )
