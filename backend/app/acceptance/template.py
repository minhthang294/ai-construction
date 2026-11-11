"""Read-only Excel template handling for PYC/BBNT exports.

The source workbook is never opened for writing.  Export starts from a byte copy
of the original zip package and edits only the worksheet XML cells that carry
validated values.  This keeps drawings/logos, printer settings, merges, styles,
row heights, column widths and hidden-sheet structure intact (features that a
plain ``openpyxl`` save would drop).
"""

from __future__ import annotations

import hashlib
import os
import posixpath
import re
import zipfile
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Dict, Iterable, Mapping, MutableMapping, Optional
from xml.sax.saxutils import escape

from .errors import TemplateError

# Repo-owned canonical template.  Resolve from this package's location so the
# default is correct regardless of the process working directory.  Missing
# files raise a clear TemplateError; there is deliberately no fallback to a
# user's Downloads folder.
DEFAULT_TEMPLATE_PATH = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "templates"
    / "acceptance-original.xlsx"
)
TEMPLATE_ENV = "ACCEPTANCE_TEMPLATE"
SUPPORTED_SHEETS = ("PYC", "BBNT")

# Cells that must exist in a usable template.  Empty cells may be inserted by
# the writer using a neighbouring style, but these anchor cells prove the sheet
# is the expected PYC/BBNT form rather than an arbitrary workbook.
REQUIRED_CELLS: Dict[str, tuple[str, ...]] = {
    "PYC": ("C1", "A6", "B6", "A8", "A14", "A20", "E20", "H20"),
    "BBNT": ("B1", "A5", "B5", "A8", "A20", "A24", "A32", "A36", "A43"),
}

CELL_RE = re.compile(r"<c\b(?P<attrs>[^>]*?)(?:/>|>(?P<body>.*?)</c>)", re.S)
ROW_RE = re.compile(r"<row\b(?P<attrs>[^>]*?)(?:/>|>(?P<body>.*?)</row>)", re.S)
STYLE_RE = re.compile(r'\bs="(\d+)"')
COORD_RE = re.compile(r"^([A-Z]+)(\d+)$")


def template_path() -> Path:
    """Return the configured template path (evaluated at call time for tests)."""

    raw = os.getenv(TEMPLATE_ENV)
    return Path(raw).expanduser() if raw else DEFAULT_TEMPLATE_PATH


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _column_index(letters: str) -> int:
    value = 0
    for char in letters:
        value = value * 26 + (ord(char) - 64)
    return value


def _coord_parts(coord: str) -> tuple[str, int]:
    match = COORD_RE.match(coord)
    if not match:
        raise TemplateError(f"Invalid cell coordinate: {coord}")
    return match.group(1), int(match.group(2))


def _read_parts(path: Path) -> Dict[str, bytes]:
    try:
        with zipfile.ZipFile(path, "r") as archive:
            return {name: archive.read(name) for name in archive.namelist()}
    except FileNotFoundError as exc:
        raise TemplateError(
            f"Acceptance template not found: {path}", code="template_missing"
        ) from exc
    except zipfile.BadZipFile as exc:
        raise TemplateError(
            f"Acceptance template is not a valid xlsx file: {path}",
            code="template_invalid",
        ) from exc


def _sheet_paths(parts: Mapping[str, bytes]) -> Dict[str, str]:
    """Map workbook sheet names to their zip part paths."""

    workbook = parts.get("xl/workbook.xml")
    rels = parts.get("xl/_rels/workbook.xml.rels")
    if workbook is None or rels is None:
        raise TemplateError("Workbook is missing workbook.xml or its relationships")

    import xml.etree.ElementTree as ET

    ns = {
        "m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
        "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
        "p": "http://schemas.openxmlformats.org/package/2006/relationships",
    }
    try:
        root = ET.fromstring(workbook)
        rel_root = ET.fromstring(rels)
    except ET.ParseError as exc:
        raise TemplateError("Workbook XML is malformed", code="template_invalid") from exc

    targets = {
        rel.get("Id"): rel.get("Target")
        for rel in rel_root.findall("p:Relationship", ns)
    }
    result: Dict[str, str] = {}
    for sheet in root.findall("m:sheets/m:sheet", ns):
        name = sheet.get("name")
        rid = sheet.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
        target = targets.get(rid)
        if not name or not target:
            continue
        if target.startswith("/"):
            part = target.lstrip("/")
        else:
            part = posixpath.normpath(posixpath.join("xl", target))
        result[name] = part
    return result


def _style_for(xml: str, coord: str) -> Optional[str]:
    """Return a neighbouring style id when inserting a missing cell."""

    try:
        target_col, target_row = _coord_parts(coord)
        target_col_idx = _column_index(target_col)
    except TemplateError:
        return None

    best: Optional[tuple[int, str]] = None
    for match in CELL_RE.finditer(xml):
        attrs = match.group("attrs")
        ref_match = re.search(r'\br="([A-Z]+)(\d+)"', attrs)
        style_match = STYLE_RE.search(attrs)
        if not ref_match or not style_match:
            continue
        col_idx = _column_index(ref_match.group(1))
        row = int(ref_match.group(2))
        distance = abs(col_idx - target_col_idx) + abs(row - target_row)
        candidate = (distance, style_match.group(1))
        if best is None or candidate[0] < best[0]:
            best = candidate
    return best[1] if best else None


def _build_cell(coord: str, value: object, style: Optional[str]) -> str:
    style_attr = f' s="{style}"' if style else ""
    if value is None or value == "":
        return f'<c r="{coord}"{style_attr}/>'

    if isinstance(value, bool):
        return f'<c r="{coord}"{style_attr}><v>{1 if value else 0}</v></c>'

    if isinstance(value, datetime):
        serial = _excel_serial(value.date())
        return f'<c r="{coord}"{style_attr}><v>{serial}</v></c>'

    if isinstance(value, date):
        serial = _excel_serial(value)
        return f'<c r="{coord}"{style_attr}><v>{serial}</v></c>'

    if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
        return f'<c r="{coord}"{style_attr}><v>{value}</v></c>'

    text = escape(str(value))
    return (
        f'<c r="{coord}"{style_attr} t="inlineStr">'
        f'<is><t xml:space="preserve">{text}</t></is></c>'
    )


def _excel_serial(value: date) -> int:
    # Excel's 1900 date system; valid for all modern dates used here.
    return (value - date(1899, 12, 30)).days


def _insert_cell(xml: str, coord: str, cell_xml: str) -> str:
    col_letters, row_num = _coord_parts(coord)
    target_col = _column_index(col_letters)

    row_match = None
    for match in ROW_RE.finditer(xml):
        attrs = match.group("attrs")
        if re.search(rf'\br="{row_num}"', attrs):
            row_match = match
            break

    if row_match is None:
        new_row = f'<row r="{row_num}">{cell_xml}</row>'
        # Insert before the first row with a larger row number.
        insert_at = None
        for match in ROW_RE.finditer(xml):
            attrs = match.group("attrs")
            ref = re.search(r'\br="(\d+)"', attrs)
            if ref and int(ref.group(1)) > row_num:
                insert_at = match.start()
                break
        if insert_at is None:
            sheet_data_end = xml.find("</sheetData>")
            if sheet_data_end == -1:
                raise TemplateError("Worksheet has no sheetData element")
            insert_at = sheet_data_end
        return xml[:insert_at] + new_row + xml[insert_at:]

    row_attrs = row_match.group("attrs")
    body = row_match.group("body") or ""
    insert_at = None
    for match in CELL_RE.finditer(body):
        ref = re.search(r'\br="([A-Z]+)(\d+)"', match.group("attrs"))
        if ref and _column_index(ref.group(1)) > target_col:
            insert_at = match.start()
            break
    if insert_at is None:
        insert_at = len(body)
    new_body = body[:insert_at] + cell_xml + body[insert_at:]
    replacement = f'<row{row_attrs}>{new_body}</row>'
    return xml[: row_match.start()] + replacement + xml[row_match.end() :]


def set_cell_xml(xml: str, coord: str, value: object) -> str:
    """Set one cell in worksheet XML while preserving its style id."""

    for match in CELL_RE.finditer(xml):
        attrs = match.group("attrs")
        if not re.search(rf'\br="{re.escape(coord)}"', attrs):
            continue
        style_match = STYLE_RE.search(attrs)
        style = style_match.group(1) if style_match else _style_for(xml, coord)
        replacement = _build_cell(coord, value, style)
        return xml[: match.start()] + replacement + xml[match.end() :]

    cell_xml = _build_cell(coord, value, _style_for(xml, coord))
    return _insert_cell(xml, coord, cell_xml)


def validate_template(path: Optional[Path] = None) -> Path:
    path = path or template_path()
    if not path.exists():
        raise TemplateError(f"Acceptance template not found: {path}", code="template_missing")
    parts = _read_parts(path)
    sheet_paths = _sheet_paths(parts)
    missing_sheets = [name for name in SUPPORTED_SHEETS if name not in sheet_paths]
    if missing_sheets:
        raise TemplateError(
            "Acceptance template is missing sheet(s): " + ", ".join(missing_sheets)
        )
    for sheet, cells in REQUIRED_CELLS.items():
        xml = _sheet_xml(parts, sheet_paths, sheet)
        for coord in cells:
            if not re.search(rf'<c\b[^>]*\br="{re.escape(coord)}"', xml):
                raise TemplateError(
                    f"Acceptance template sheet {sheet!r} is missing required cell {coord}"
                )
    return path


def _sheet_xml(parts: Mapping[str, bytes], sheet_paths: Mapping[str, str], sheet: str) -> str:
    part = sheet_paths.get(sheet)
    if part is None or part not in parts:
        raise TemplateError(f"Acceptance template has no sheet {sheet!r}")
    try:
        return parts[part].decode("utf-8")
    except UnicodeDecodeError as exc:
        raise TemplateError(f"Worksheet {sheet!r} is not UTF-8 XML") from exc


def _strip_calc_chain(parts: MutableMapping[str, bytes]) -> None:
    """Drop the stale calcChain cache; Excel rebuilds it on open."""

    parts.pop("xl/calcChain.xml", None)
    content_types = parts.get("[Content_Types].xml")
    if content_types:
        text = content_types.decode("utf-8")
        text = re.sub(
            r'<Override[^>]*PartName="/xl/calcChain\.xml"[^>]*/>',
            "",
            text,
        )
        parts["[Content_Types].xml"] = text.encode("utf-8")

    rels = parts.get("xl/_rels/workbook.xml.rels")
    if rels:
        text = rels.decode("utf-8")
        text = re.sub(
            r'<Relationship[^>]*Type="[^"]*/calcChain"[^>]*/>',
            "",
            text,
        )
        parts["xl/_rels/workbook.xml.rels"] = text.encode("utf-8")


def _force_recalculation(parts: Mapping[str, bytes]) -> Optional[bytes]:
    workbook = parts.get("xl/workbook.xml")
    if not workbook:
        return None
    text = workbook.decode("utf-8")
    if "<calcPr" in text and "fullCalcOnLoad" not in text:
        text = re.sub(r"<calcPr\b", '<calcPr fullCalcOnLoad="1"', text, count=1)
        return text.encode("utf-8")
    return None


def copy_and_fill(
    template: Path,
    out_path: Path,
    replacements: Mapping[str, Mapping[str, object]],
    scrub: Optional[Mapping[str, Iterable[str]]] = None,
) -> Dict[str, object]:
    """Copy ``template`` and replace only the specified cells.

    ``replacements`` maps sheet name -> cell coordinate -> validated value.
    ``scrub`` maps sheet name -> coordinates to clear.  The original file is
    never written; ``out_path`` must be a different path.
    """

    template = validate_template(template)
    if template.resolve() == out_path.resolve():
        raise TemplateError("Refusing to overwrite the source acceptance template")
    if out_path.exists():
        out_path.unlink()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    template_hash = sha256_file(template)
    parts = _read_parts(template)
    sheet_paths = _sheet_paths(parts)

    for sheet, coords in (scrub or {}).items():
        if sheet not in sheet_paths:
            continue
        xml = _sheet_xml(parts, sheet_paths, sheet)
        for coord in coords:
            xml = set_cell_xml(xml, coord, None)
        parts[sheet_paths[sheet]] = xml.encode("utf-8")

    for sheet, values in replacements.items():
        if sheet not in sheet_paths:
            raise TemplateError(f"Acceptance template has no sheet {sheet!r}")
        xml = _sheet_xml(parts, sheet_paths, sheet)
        for coord, value in values.items():
            xml = set_cell_xml(xml, coord, value)
        parts[sheet_paths[sheet]] = xml.encode("utf-8")

    _strip_calc_chain(parts)
    recalculated = _force_recalculation(parts)
    if recalculated is not None:
        parts["xl/workbook.xml"] = recalculated

    temp_path = out_path.with_name(out_path.name + ".tmp")
    try:
        with zipfile.ZipFile(template, "r") as source:
            infos = source.infolist()
            with zipfile.ZipFile(temp_path, "w") as target:
                for info in infos:
                    if info.filename == "xl/calcChain.xml":
                        continue
                    data = parts.get(info.filename)
                    if data is None:
                        continue
                    target.writestr(info, data, compress_type=info.compress_type)
        os.replace(temp_path, out_path)
    finally:
        if temp_path.exists():
            temp_path.unlink()

    return {
        "path": str(out_path),
        "sha256": sha256_file(out_path),
        "template_sha256": template_hash,
        "size_bytes": out_path.stat().st_size,
    }
