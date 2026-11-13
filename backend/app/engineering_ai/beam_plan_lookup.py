"""Exact beam location from structured repair-plan rows."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from .embeddings import fold_text
from .models import DocumentPage, PageExtraction, SourceDocument


@dataclass(frozen=True)
class BeamPlanEntry:
    code: str
    group: str | None
    segment: str | None
    beam_type: str | None
    location: str
    document_id: str
    page_number: int
    table_row: int
    url: str


def _norm(value: object) -> str:
    return re.sub(r"\s+", "", fold_text(str(value or "")).upper())


def find_proposed_beam_plan(
    db: Session, project_id: str, component_code: str, scope: str = "effective"
) -> list[BeamPlanEntry]:
    if scope not in {"effective", "history"}:
        raise ValueError("scope must be effective or history")
    target = _norm(component_code)
    if not re.fullmatch(r"[A-Z]{1,3}(?:-[A-Z]{1,3})?[-.]\d+(?:-\d+)?", target):
        return []
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
    rows = db.execute(
        select(PageExtraction, DocumentPage, SourceDocument)
        .join(DocumentPage, (PageExtraction.page_id == DocumentPage.id) & (PageExtraction.document_id == DocumentPage.document_id))
        .join(SourceDocument, PageExtraction.document_id == SourceDocument.id)
        .where(*conditions)
    ).all()
    matches: list[BeamPlanEntry] = []
    seen: set[tuple[str, int, int]] = set()
    for extraction, page, document in rows:
        try:
            data = json.loads(extraction.extraction_json)
        except (TypeError, ValueError):
            continue
        if not isinstance(data, dict) or "MATBANG" not in _norm(data.get("title")):
            continue
        table = data.get("table_rows")
        if not isinstance(table, list):
            continue
        for header_index, header in enumerate(table):
            if not isinstance(header, list):
                continue
            labels = [_norm(cell) for cell in header]
            if not all(label in labels for label in ("KYHIEUDAM", "PHANNHOM", "PHANDOAN")):
                continue
            columns = {label: labels.index(label) for label in ("KYHIEUDAM", "PHANNHOM", "PHANDOAN")}
            beam_type_col = labels.index("LOAIDAM") if "LOAIDAM" in labels else None
            location = "Cầu dẫn" if "CAUDAN" in _norm(data.get("title")) else "Cầu chính" if "CAUCHINH" in _norm(data.get("title")) else "Không rõ vị trí"
            for row_number, row in enumerate(table[header_index + 1:], header_index + 2):
                if not isinstance(row, list) or max(columns.values()) >= len(row) or _norm(row[columns["KYHIEUDAM"]]) != target:
                    continue
                group = _norm(row[columns["PHANNHOM"]])
                segment = _norm(row[columns["PHANDOAN"]])
                if not re.fullmatch(r"[123]", group) or not re.fullmatch(r"PD\d{1,2}", segment):
                    continue
                key = (document.id, page.page_number, row_number)
                if key in seen:
                    continue
                seen.add(key)
                matches.append(BeamPlanEntry(
                    code=str(row[columns["KYHIEUDAM"]]).strip(),
                    group=group,
                    segment=segment,
                    beam_type=str(row[beam_type_col]).strip() or None if beam_type_col is not None and beam_type_col < len(row) else None,
                    location=location,
                    document_id=document.id,
                    page_number=page.page_number,
                    table_row=row_number,
                    url=f"/projects/{project_id}/documents/{document.id}/pages/{page.page_number}",
                ))
            break
    return matches
