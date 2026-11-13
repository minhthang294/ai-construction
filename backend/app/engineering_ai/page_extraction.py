"""Pure page-tile and JSON-merge helpers for the DeepSeek page-extraction POC.

No model/API, database, storage or migration code is used here.  Inputs are
plain dicts matching the POC schema used by ``scripts/deepseek_page_extract.py``.
The functions are designed to be called by the coordinator when it wires tiled
DeepSeek extraction.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

SCHEMA_FIELDS = (
    "page_type",
    "title",
    "drawing_number",
    "revision",
    "summary",
    "key_values",
    "table_rows",
    "warnings",
    "confidence",
)
PAGE_TYPES = {"drawing", "specification", "table", "text", "other"}

MAX_KEY_VALUES = 200
MAX_COMPONENT_FACTS = 200
MAX_TABLE_ROWS = 200
MAX_TABLE_COLUMNS = 50
MAX_WARNINGS = 100
MAX_TEXT = 4000
MIN_TILE_SIDE = 4
MAX_NUMERIC_WARNINGS = 20

_COMPONENT_FACT_FIELDS = (
    "component_type",
    "component_code",
    "fact_name",
    "value",
    "unit",
    "quote",
    "group",
    "segment",
    "location",
    "table_row",
    "table_column",
)

_TILE_NOISE_MARKERS = (
    "vùng crop",
    "vung crop",
    "đây là vùng",
    "day la vung",
    "trong vùng",
    "trong vung",
    "không đủ ngữ cảnh",
    "khong du ngu canh",
    "bị cắt",
    "bi cat",
    "không thấy số hiệu bản vẽ",
    "khong thay so hieu ban ve",
    "không thấy revision",
    "khong thay revision",
    "không xác định được revision",
    "khong xac dinh duoc revision",
)

_NUMBER_RE = re.compile(r"(?<![\w.])(\d{1,8}(?:[.,]\d+)?)", re.UNICODE)
_NUMBER_UNIT_RE = re.compile(
    r"(?<![\w.])(\d{1,8}(?:[.,]\d+)?)\s*"
    r"(mm|cm|m2|m²|m3|m³|kg|mpa|kn|%|độ|do|°|m|tấn|tan|t)(?=\W|$)",
    re.IGNORECASE | re.UNICODE,
)
@dataclass(frozen=True)
class Tile:
    label: str
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top

    @property
    def area(self) -> int:
        return max(0, self.width) * max(0, self.height)


def plan_page_tiles(
    width: int,
    height: int,
    grid: int = 2,
    overlap: float = 0.06,
    include_title_block: bool = True,
) -> List[Tile]:
    """Plan evenly distributed overlapping tiles covering the page.

    Coordinates are integer pixels with origin at the top-left.  Tiles that
    would be empty or smaller than ``MIN_TILE_SIDE`` are omitted.  When enabled,
    a title-block tile is added at the bottom-right (the usual drawing layout).
    """

    if width <= 0 or height <= 0:
        raise ValueError("width and height must be positive")
    if not isinstance(grid, int) or grid < 1:
        raise ValueError("grid must be a positive integer")
    if not 0 <= overlap <= 0.5:
        raise ValueError("overlap must be between 0 and 0.5")

    cell_width = width / grid
    cell_height = height / grid
    overlap_x = cell_width * overlap
    overlap_y = cell_height * overlap
    tiles: List[Tile] = []
    for row in range(grid):
        for column in range(grid):
            left = max(0, int(round(column * cell_width - overlap_x / 2)))
            right = min(width, int(round((column + 1) * cell_width + overlap_x / 2)))
            top = max(0, int(round(row * cell_height - overlap_y / 2)))
            bottom = min(height, int(round((row + 1) * cell_height + overlap_y / 2)))
            if right - left < MIN_TILE_SIDE or bottom - top < MIN_TILE_SIDE:
                continue
            tiles.append(
                Tile(
                    label=f"r{row + 1}c{column + 1}",
                    left=left,
                    top=top,
                    right=right,
                    bottom=bottom,
                )
            )

    if include_title_block and width >= MIN_TILE_SIDE and height >= MIN_TILE_SIDE:
        title_width = max(MIN_TILE_SIDE, int(round(width * 0.35)))
        title_height = max(MIN_TILE_SIDE, int(round(height * 0.28)))
        title_width = min(title_width, width)
        title_height = min(title_height, height)
        tile = Tile(
            label="title_block",
            left=width - title_width,
            top=height - title_height,
            right=width,
            bottom=height,
        )
        if tile.area > 0 and not any(
            (existing.left, existing.top, existing.right, existing.bottom)
            == (tile.left, tile.top, tile.right, tile.bottom)
            for existing in tiles
        ):
            tiles.append(tile)
    return tiles


def _norm(value: Any) -> str:
    text = " ".join(str(value or "").strip().split()).casefold()
    # "TK - 04", "TK-04" and "TK- 04" are the same identifier for conflict
    # detection; drawings frequently vary spacing around punctuation.
    text = re.sub(r"\s*([./-])\s*", r"\1", text)
    return text


def _clean_text(value: Any, limit: int = MAX_TEXT) -> Optional[str]:
    if value is None:
        return None
    text = " ".join(str(value).strip().split())
    return text[:limit] if text else None


def _valid_confidence(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if 0 <= float(value) <= 1:
        return float(value)
    return None


def _append_warning(warnings: List[str], value: Any) -> None:
    text = _clean_text(value)
    if text and _norm(text) not in {_norm(item) for item in warnings}:
        if len(warnings) < MAX_WARNINGS:
            warnings.append(text)


def _first_text(
    full_page: Mapping[str, Any],
    parts: Sequence[Mapping[str, Any]],
    field: str,
    *,
    prefer_full: bool = True,
) -> Optional[str]:
    if prefer_full and field in full_page and _clean_text(full_page.get(field)):
        return _clean_text(full_page.get(field))
    for part in parts:
        if _clean_text(part.get(field)):
            return _clean_text(part.get(field))
    if not prefer_full and field in full_page:
        return _clean_text(full_page.get(field))
    return None


def _metadata_conflicts(
    full_page: Mapping[str, Any],
    parts: Sequence[Mapping[str, Any]],
) -> List[str]:
    conflicts: List[str] = []
    # Title and page_type are page-level metadata; a tile seeing only a region
    # must not create a page-level conflict.  Only drawing number and revision
    # are compared between the full page and tiles.
    for field in ("drawing_number", "revision"):
        full_value = _norm(full_page.get(field))
        if not full_value:
            continue
        for part in parts:
            part_value = _norm(part.get(field))
            if part_value and part_value != full_value:
                conflicts.append(
                    f"Mâu thuẫn {field} giữa full_page và tile: "
                    f"{full_page.get(field)!r} vs {part.get(field)!r}"
                )
                break
    return conflicts


def _is_tile_noise_warning(value: Any) -> bool:
    text = _norm(value)
    return any(marker in text for marker in _TILE_NOISE_MARKERS)


def _normalise_key_value(item: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(item, dict):
        return None
    name = _clean_text(item.get("name"), 500)
    value = _clean_text(item.get("value"), 500)
    unit = _clean_text(item.get("unit"), 60)
    quote = _clean_text(item.get("quote"), 1000)
    if not name or value is None or not quote:
        return None
    return {"name": name, "value": value, "unit": unit, "quote": quote}


def _component_fact_errors(fact: Any, prefix: str) -> List[str]:
    errors: List[str] = []
    if not isinstance(fact, dict):
        return [f"{prefix} is not an object"]
    if fact.get("component_type") not in {"pile", "beam"}:
        errors.append(f"{prefix}.component_type must be 'pile' or 'beam'")
    for field in ("component_code", "fact_name", "unit", "quote"):
        item = fact.get(field)
        if not isinstance(item, str) or not item.strip():
            errors.append(f"{prefix}.{field} must be a non-empty string")
    fact_value = fact.get("value")
    if (
        isinstance(fact_value, bool)
        or not isinstance(fact_value, (str, int, float))
        or not str(fact_value).strip()
    ):
        errors.append(f"{prefix}.value must be a non-empty string or number")
    for field in ("group", "segment", "location"):
        item = fact.get(field)
        if item is not None and (
            not isinstance(item, str) or not item.strip()
        ):
            errors.append(f"{prefix}.{field} must be a non-empty string or null")
    table_row = fact.get("table_row")
    if table_row is not None and (
        isinstance(table_row, bool)
        or not isinstance(table_row, int)
        or table_row < 0
    ):
        errors.append(f"{prefix}.table_row must be a non-negative integer or null")
    table_column = fact.get("table_column")
    if table_column is not None and not (
        (
            isinstance(table_column, int)
            and not isinstance(table_column, bool)
            and table_column >= 0
        )
        or (isinstance(table_column, str) and table_column.strip())
    ):
        errors.append(
            f"{prefix}.table_column must be a non-empty string, "
            "a non-negative integer or null"
        )
    return errors


def merge_extractions(
    parts: Iterable[Mapping[str, Any]],
    full_page: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Merge tile JSON and a full-page JSON into one POC-schema object.

    Metadata/summary come from ``full_page`` first.  Key values, table rows and
    warnings are merged and de-duplicated.  Confidence is a conservative
    weighted/min value; conflicting tile metadata/key values add warnings.
    """

    raw_parts = list(parts)
    clean_parts = [part for part in raw_parts if isinstance(part, Mapping)]
    full: Mapping[str, Any] = full_page if isinstance(full_page, Mapping) else {}
    warnings: List[str] = []

    if full_page is not None and not isinstance(full_page, Mapping):
        warnings.append("full_page không phải object; đã bỏ qua.")
    for index, part in enumerate(raw_parts):
        if not isinstance(part, Mapping):
            _append_warning(warnings, f"Bỏ qua tile {index}: không phải JSON object.")

    full_page_type = _clean_text(full.get("page_type"), 60)
    page_type = full_page_type if full_page_type in PAGE_TYPES else None
    if page_type is None:
        for part in clean_parts:
            candidate = _clean_text(part.get("page_type"), 60)
            if candidate in PAGE_TYPES:
                page_type = candidate
                break
    if page_type is None:
        page_type = "other"

    title = _first_text(full, clean_parts, "title")
    drawing_number = _first_text(full, clean_parts, "drawing_number")
    revision = _first_text(full, clean_parts, "revision")
    summary = _first_text(full, clean_parts, "summary")
    if summary is None:
        summary = ""

    conflicts = _metadata_conflicts(full, clean_parts)
    for conflict in conflicts:
        _append_warning(warnings, conflict)

    key_values: List[Dict[str, Any]] = []
    seen_keys: Set[Tuple[str, str, str, str]] = set()
    seen_names: Dict[str, Tuple[str, str]] = {}
    sources = [full] + clean_parts
    for source in sources:
        raw_items = source.get("key_values")
        if raw_items is None:
            continue
        if not isinstance(raw_items, list):
            _append_warning(warnings, "Bỏ qua key_values không phải list.")
            continue
        for item in raw_items:
            clean = _normalise_key_value(item)
            if clean is None:
                _append_warning(warnings, "Bỏ qua key_value thiếu name/value/quote.")
                continue
            key = (
                _norm(clean["name"]),
                _norm(clean["value"]),
                _norm(clean["unit"]),
                _norm(clean["quote"]),
            )
            if key in seen_keys:
                continue
            seen_keys.add(key)
            name_key = _norm(clean["name"])
            pair = (_norm(clean["value"]), _norm(clean["unit"]))
            previous = seen_names.get(name_key)
            if previous is not None and previous != pair:
                _append_warning(
                    warnings,
                    f"Mâu thuẫn key_values {clean['name']}: "
                    f"{previous[0]} {previous[1]} vs {pair[0]} {pair[1]}",
                )
            else:
                seen_names[name_key] = pair
            if len(key_values) < MAX_KEY_VALUES:
                key_values.append(clean)
    if len(key_values) >= MAX_KEY_VALUES:
        _append_warning(warnings, f"key_values bị giới hạn ở {MAX_KEY_VALUES} mục.")
        key_values = key_values[:MAX_KEY_VALUES]

    table_rows: List[List[str]] = []
    seen_rows: Set[Tuple[str, ...]] = set()
    for source in sources:
        raw_rows = source.get("table_rows")
        if raw_rows is None:
            continue
        if not isinstance(raw_rows, list):
            _append_warning(warnings, "Bỏ qua table_rows không phải list.")
            continue
        for row in raw_rows:
            if not isinstance(row, list):
                continue
            values = ["" if cell is None else str(cell).strip() for cell in row]
            values = values[:MAX_TABLE_COLUMNS]
            key = tuple(_norm(cell) for cell in values)
            if not values or key in seen_rows:
                continue
            seen_rows.add(key)
            if len(table_rows) < MAX_TABLE_ROWS:
                table_rows.append(values)
    if len(table_rows) >= MAX_TABLE_ROWS:
        _append_warning(warnings, f"table_rows bị giới hạn ở {MAX_TABLE_ROWS} hàng.")
        table_rows = table_rows[:MAX_TABLE_ROWS]

    component_facts: List[Dict[str, Any]] = []
    component_facts_present = False
    seen_fact_keys: Set[Tuple[Tuple[str, str], ...]] = set()
    seen_fact_values: Dict[Tuple[str, str, str, str], Tuple[str, str]] = {}
    for source in sources:
        if "component_facts" in source:
            component_facts_present = True
        raw_facts = source.get("component_facts")
        if raw_facts is None:
            continue
        if not isinstance(raw_facts, list):
            _append_warning(warnings, "Bỏ qua component_facts không phải list.")
            continue
        for item in raw_facts:
            fact_errors = _component_fact_errors(item, "component_fact")
            if fact_errors:
                _append_warning(
                    warnings,
                    "Bỏ qua component_fact không hợp lệ: "
                    + "; ".join(fact_errors),
                )
                continue
            clean = {
                field: item[field]
                for field in _COMPONENT_FACT_FIELDS
                if field in item
            }
            fact_key = tuple(
                (field, _norm(clean.get(field)))
                for field in _COMPONENT_FACT_FIELDS
                if field in clean
            )
            if fact_key in seen_fact_keys:
                continue
            seen_fact_keys.add(fact_key)
            conflict_key = (
                _norm(clean.get("component_code")),
                _norm(clean.get("fact_name")),
                _norm(clean.get("table_row")),
                _norm(clean.get("table_column")),
            )
            conflict_value = (
                _norm(clean.get("value")),
                _norm(clean.get("unit")),
            )
            previous = seen_fact_values.get(conflict_key)
            if previous is None:
                seen_fact_values[conflict_key] = conflict_value
            elif previous != conflict_value:
                position: List[str] = []
                if clean.get("table_row") is not None:
                    position.append(f"hàng {clean['table_row']}")
                if clean.get("table_column") is not None:
                    position.append(f"cột {clean['table_column']}")
                location = ", ".join(position) or "không có vị trí bảng"
                _append_warning(
                    warnings,
                    f"Mâu thuẫn component_facts {clean['component_code']} / "
                    f"{clean['fact_name']} ({location}): "
                    f"{previous[0]} {previous[1]} vs "
                    f"{conflict_value[0]} {conflict_value[1]}",
                )
            if len(component_facts) < MAX_COMPONENT_FACTS:
                component_facts.append(clean)
    if len(component_facts) >= MAX_COMPONENT_FACTS:
        _append_warning(
            warnings,
            f"component_facts bị giới hạn ở {MAX_COMPONENT_FACTS} mục.",
        )
        component_facts = component_facts[:MAX_COMPONENT_FACTS]

    for source in sources:
        raw_warnings = source.get("warnings")
        if raw_warnings is None:
            continue
        if not isinstance(raw_warnings, list):
            _append_warning(warnings, "Bỏ qua warnings không phải list.")
            continue
        for warning in raw_warnings:
            # Full-page warnings are authoritative and always kept.  Tile
            # warnings about crop context are not page-level facts.
            if source is not full and _is_tile_noise_warning(warning):
                continue
            _append_warning(warnings, warning)

    full_confidence = _valid_confidence(full.get("confidence"))
    part_confidences = [
        confidence
        for part in clean_parts
        if (confidence := _valid_confidence(part.get("confidence"))) is not None
    ]
    if full_confidence is not None and part_confidences:
        confidence = 0.6 * full_confidence + 0.4 * (
            sum(part_confidences) / len(part_confidences)
        )
    elif full_confidence is not None:
        confidence = full_confidence
    elif part_confidences:
        confidence = sum(part_confidences) / len(part_confidences)
    else:
        confidence = 0.0

    high_confidence_key_conflict = any(
        "Mâu thuẫn key_values" in warning for warning in warnings
    )
    if conflicts or high_confidence_key_conflict:
        confidence = min(confidence, min(part_confidences or [confidence])) * 0.85
        _append_warning(warnings, "Có mâu thuẫn giữa các lần trích xuất; cần kiểm tra trang gốc.")
    confidence = round(max(0.0, min(1.0, confidence)), 4)

    merged: Dict[str, Any] = {
        "page_type": page_type,
        "title": title,
        "drawing_number": drawing_number,
        "revision": revision,
        "summary": summary,
        "key_values": key_values,
        "table_rows": table_rows,
        "warnings": warnings[:MAX_WARNINGS],
        "confidence": confidence,
    }
    if component_facts_present:
        merged["component_facts"] = component_facts
    return merged


def validate_extraction(value: Any) -> List[str]:
    """Return schema/type errors for one POC extraction object."""

    if not isinstance(value, dict):
        return ["top-level JSON must be an object"]
    errors: List[str] = []
    missing = [field for field in SCHEMA_FIELDS if field not in value]
    if missing:
        errors.append(f"missing fields: {missing}")

    if value.get("page_type") not in PAGE_TYPES:
        errors.append("invalid page_type")
    for field in ("title", "drawing_number", "revision"):
        if field in value and value[field] is not None and not isinstance(value[field], str):
            errors.append(f"{field} must be string or null")
    summary = value.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        errors.append("summary is empty or not a string")

    key_values = value.get("key_values")
    if not isinstance(key_values, list):
        errors.append("key_values is not a list")
    else:
        for index, item in enumerate(key_values):
            if not isinstance(item, dict):
                errors.append(f"key_values[{index}] is not an object")
                continue
            for field in ("name", "value", "quote"):
                if not isinstance(item.get(field), str) or not item.get(field, "").strip():
                    errors.append(f"key_values[{index}].{field} must be a non-empty string")
            unit = item.get("unit")
            if unit is not None and not isinstance(unit, str):
                errors.append(f"key_values[{index}].unit must be string or null")

    component_facts = value.get("component_facts")
    if component_facts is not None:
        if not isinstance(component_facts, list):
            errors.append("component_facts is not a list")
        else:
            for index, fact in enumerate(component_facts):
                errors.extend(
                    _component_fact_errors(fact, f"component_facts[{index}]")
                )

    rows = value.get("table_rows")
    if not isinstance(rows, list):
        errors.append("table_rows is not a list")
    else:
        for row_index, row in enumerate(rows):
            if not isinstance(row, list):
                errors.append(f"table_rows[{row_index}] is not a list")
                continue
            for column_index, cell in enumerate(row):
                if not isinstance(cell, str):
                    errors.append(
                        f"table_rows[{row_index}][{column_index}] is not a string"
                    )

    warnings = value.get("warnings")
    if not isinstance(warnings, list):
        errors.append("warnings is not a list")
    else:
        for index, warning in enumerate(warnings):
            if not isinstance(warning, str):
                errors.append(f"warnings[{index}] is not a string")

    confidence = value.get("confidence")
    if (
        isinstance(confidence, bool)
        or not isinstance(confidence, (int, float))
        or not 0 <= float(confidence) <= 1
    ):
        errors.append("confidence is not a number in 0..1")
    return errors


def _normalise_number(value: str) -> str:
    text = value.strip()
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")
    elif "." in text:
        left, right = text.split(".", 1)
        if left.isdigit() and left != "0" and len(right) == 3:
            text = left + right
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _normalise_unit(value: Optional[str]) -> str:
    if not value:
        return ""
    return value.strip().lower().replace("m²", "m2").replace("m³", "m3")


def _ocr_occurrences(ocr_text: str) -> Tuple[Set[str], Dict[str, Set[str]]]:
    numbers: Set[str] = set()
    units: Dict[str, Set[str]] = {}
    for match in _NUMBER_RE.finditer(ocr_text or ""):
        numbers.add(_normalise_number(match.group(1)))
    for match in _NUMBER_UNIT_RE.finditer(ocr_text or ""):
        number = _normalise_number(match.group(1))
        unit = _normalise_unit(match.group(2))
        numbers.add(number)
        units.setdefault(number, set()).add(unit)
    return numbers, units


def _dedupe_numeric_warnings(warnings: Sequence[str]) -> List[str]:
    unique: List[str] = []
    seen: Set[str] = set()
    for warning in warnings:
        key = _norm(warning)
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(warning)
    if len(unique) <= MAX_NUMERIC_WARNINGS:
        return unique
    remaining = len(unique) - MAX_NUMERIC_WARNINGS
    return [
        *unique[:MAX_NUMERIC_WARNINGS],
        f"Còn {remaining} cảnh báo số/đơn vị khác",
    ]


def numeric_cross_check(value: Mapping[str, Any], ocr_text: str) -> List[str]:
    """Warn when model key-value numbers/units are absent or conflict with OCR.

    This function never changes the model value.  OCR is a baseline, not truth.
    Warnings are de-duplicated and capped at 20 plus one aggregate warning.
    """

    ocr_numbers, ocr_units = _ocr_occurrences(ocr_text)
    warnings: List[str] = []
    key_values = value.get("key_values")
    if not isinstance(key_values, list):
        return warnings
    for item in key_values:
        if not isinstance(item, dict):
            continue
        raw_value = str(item.get("value") or "")
        raw_unit = _normalise_unit(item.get("unit") if isinstance(item.get("unit"), str) else None)
        numbers = [
            _normalise_number(match.group(1)) for match in _NUMBER_RE.finditer(raw_value)
        ]
        value_unit_match = _NUMBER_UNIT_RE.search(raw_value)
        if not raw_unit and value_unit_match:
            raw_unit = _normalise_unit(value_unit_match.group(2))
        for number in numbers:
            if number not in ocr_numbers:
                warnings.append(
                    f"Số {number} của model không xuất hiện trong OCR trang."
                )
                continue
            if raw_unit:
                seen_units = ocr_units.get(number, set())
                if seen_units and raw_unit not in seen_units:
                    warnings.append(
                        f"Đơn vị {raw_unit} của model mâu thuẫn với "
                        f"{', '.join(sorted(seen_units))} trong OCR trang cho số {number}."
                    )
    return _dedupe_numeric_warnings(warnings)
