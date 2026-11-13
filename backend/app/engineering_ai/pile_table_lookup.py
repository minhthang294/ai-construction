"""Read explicit pile measurements from proposed page-extraction table rows."""

from __future__ import annotations

import json
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from .component_search import ComponentFactMatch
from .embeddings import fold_text
from .models import DocumentPage, PageExtraction, SourceDocument


def _label(value: object) -> str:
    return fold_text(str(value or "")).strip()


def _measurement(header: str, title: str = "") -> tuple[str, str] | None:
    if header == "t (cm)":
        return "chiều sâu đục (t)", "cm"
    if re.fullmatch(r"l[1-4] \(m\)", header):
        return header.split()[0].upper(), "m"
    if "chieu dai" in header and ("vet nut" in header or "coc nut" in header) and "(m)" in header:
        return "chiều dài vết nứt L", "m"
    if header == "chieu dai (m)" and "mat bang nhom coc" in title:
        return "chiều dài vết nứt L", "m"
    return None


def find_proposed_pile_measurements(
    db: Session, project_id: str, component_code: str, scope: str = "effective"
) -> list[ComponentFactMatch]:
    """Find only numeric cells on rows explicitly naming this pile.

    Empty merged cells remain unknown; repeated codes and conflicting values are
    returned separately with their own row and page for review.
    """
    if scope not in {"effective", "history"}:
        raise ValueError("scope must be effective or history")
    target = component_code.strip().upper()
    if not re.fullmatch(r"[A-Z]{1,3}-?\d{1,4}", target):
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
        if not isinstance(data, dict) or not isinstance(data.get("table_rows"), list):
            continue
        header: list[str] = []
        code_col: int | None = None
        for row_number, row in enumerate(data["table_rows"], 1):
            if not isinstance(row, list):
                header, code_col = [], None
                continue
            labels = [_label(value) for value in row]
            code_columns = [i for i, label in enumerate(labels)
                            if label in {"ten coc", "ten coc (ks)", "ten coc (cd)", "ten coc (kt)"}]
            if code_columns:
                header, code_col = labels, code_columns[0]
                continue
            # A different table header ends the current pile table.
            if any(label in {"stt", "hang muc", "ten cau kien (bi cat)"} for label in labels):
                header, code_col = [], None
            if code_col is None or code_col >= len(row):
                continue
            codes = re.findall(r"(?<![\w-])[A-Z]{1,3}-?\d{1,4}(?![\w-])", str(row[code_col]).upper())
            if target not in codes:
                continue
            location = ""
            group = ""
            for index, label in enumerate(header):
                if index >= len(row):
                    continue
                if label == "vi tri":
                    location = str(row[index] or "").strip()
                elif label in {"nhom", "phan loai"}:
                    group = str(row[index] or "").strip()
            for index, label in enumerate(header):
                measurement = _measurement(label, _label(data.get("title")))
                if measurement is None or index >= len(row):
                    continue
                raw = str(row[index] or "").strip()
                if not re.fullmatch(r"\d+(?:[,.]\d+)?", raw):
                    continue
                name, unit = measurement
                matches.append(ComponentFactMatch(
                    fact={"component_code": target, "fact_name": name,
                          "value": raw, "unit": unit, "location": location,
                          "group": group, "status": "proposed",
                          "quote": f"{row[code_col]} | {header[index]} = {raw} {unit}",
                          "table_row": row_number, "table_column": header[index]},
                    document_id=document.id, document_name=document.original_name,
                    page_number=page.page_number,
                    drawing_number=data.get("drawing_number") or page.drawing_number,
                    revision=data.get("revision") or page.revision,
                    table_row=row_number, table_column=header[index],
                    url=f"/projects/{project_id}/documents/{document.id}/pages/{page.page_number}",
                ))
    return matches
