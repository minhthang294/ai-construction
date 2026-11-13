"""Conservative exact-code lookup in proposed beam schedules."""

from __future__ import annotations

import json
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from .component_search import ComponentFactMatch
from .embeddings import fold_text
from .models import DocumentPage, PageExtraction, SourceDocument


def _norm(value: object) -> str:
    return re.sub(r"\s+", "", fold_text(str(value or "")).upper())


def _field(header: str) -> tuple[str, str] | None:
    name = fold_text(header).strip().lower()
    compact = re.sub(r"\s+", "", name)
    if re.fullmatch(r"(?:kichthuoc)?l\(m(?:m)?\)", compact):
        return "chiều dài dầm", "mm" if "(mm)" in compact else "m"
    if re.fullmatch(r"(?:kichthuoc)?b\(m(?:m)?\)", compact):
        return "chiều rộng dầm", "mm" if "(mm)" in compact else "m"
    if re.fullmatch(r"h\((?:mm|cm)\)", compact):
        return "chiều cao dầm", "mm" if "(mm)" in compact else "cm"
    if "khoi luong" in name and "(m3)" in compact:
        return "khối lượng " + name.split("khoi luong", 1)[1].split("(", 1)[0].strip(), "m³"
    if "tong dien tich" in name and "(m2)" in compact:
        return "tổng diện tích", "m²"
    return None


def find_proposed_beam_table_facts(
    db: Session, project_id: str, component_code: str, scope: str = "effective"
) -> list[ComponentFactMatch]:
    """Only numeric cells in an exact beam-code row are candidates; status stays proposed."""
    if scope not in {"effective", "history"}:
        raise ValueError("scope must be effective or history")
    target = _norm(component_code)
    if not re.fullmatch(r"[A-Z]{1,3}(?:-[A-Z]{1,3})?[.\-]\d+(?:-\d+)?", target):
        return []
    conditions = [
        PageExtraction.project_id == project_id,
        DocumentPage.project_id == project_id,
        SourceDocument.project_id == project_id,
        PageExtraction.status == "proposed",
        SourceDocument.status == "ready",
    ]
    if scope == "effective":
        conditions.append(SourceDocument.is_effective.is_(True))
    rows = db.execute(
        select(PageExtraction, DocumentPage, SourceDocument)
        .join(DocumentPage, (PageExtraction.page_id == DocumentPage.id)
              & (PageExtraction.document_id == DocumentPage.document_id))
        .join(SourceDocument, PageExtraction.document_id == SourceDocument.id)
        .where(*conditions)
    ).all()
    matches: list[ComponentFactMatch] = []
    for extraction, page, document in rows:
        try:
            data = json.loads(extraction.extraction_json)
        except (TypeError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        table = data.get("table_rows")
        if not isinstance(table, list):
            continue
        for header_index, header in enumerate(table):
            if not isinstance(header, list):
                continue
            labels = [fold_text(str(cell or "")).strip().lower() for cell in header]
            code_columns = [i for i, label in enumerate(labels) if label in {"ten dam", "ky hieu dam"}]
            if len(code_columns) != 1:
                continue
            code_column = code_columns[0]
            fields = [(i, _field(str(label or ""))) for i, label in enumerate(header)]
            for row_number, row in enumerate(table[header_index + 1:], header_index + 2):
                if not isinstance(row, list) or code_column >= len(row):
                    continue
                # A range or multiple codes is never evidence for an individual beam.
                if _norm(row[code_column]) != target:
                    continue
                for column, field in fields:
                    if field is None or column >= len(row):
                        continue
                    value = str(row[column]).strip()
                    if not re.fullmatch(r"\d+(?:[,.]\d+)?", value):
                        continue
                    fact_name, unit = field
                    matches.append(ComponentFactMatch(
                        fact={"component_type": "beam", "component_code": component_code.upper(),
                              "fact_name": fact_name, "value": value, "unit": unit,
                              "quote": f"{row[code_column]} | {header[column]} = {value} {unit}",
                              "table_row": row_number, "table_column": str(header[column]),
                              "status": "proposed"},
                        document_id=document.id, document_name=document.original_name,
                        page_number=page.page_number,
                        drawing_number=data.get("drawing_number") or page.drawing_number,
                        revision=data.get("revision") or page.revision,
                        table_row=row_number, table_column=str(header[column]),
                        url=f"/projects/{project_id}/documents/{document.id}/pages/{page.page_number}",
                    ))
            break
    return matches
