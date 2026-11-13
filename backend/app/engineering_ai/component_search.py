"""Exact lookup of engineer-verified component facts in page extractions."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from .embeddings import fold_text
from .models import DocumentPage, PageExtraction, SourceDocument


@dataclass(frozen=True)
class ComponentFactMatch:
    fact: dict
    document_id: str
    document_name: str
    page_number: int
    drawing_number: Optional[str]
    revision: Optional[str]
    table_row: Optional[int]
    table_column: Optional[str | int]
    url: str


def _label(value: object) -> str:
    return fold_text(str(value or "")).strip()


def _numbered_label(value: object) -> str:
    label = _label(value)
    match = re.search(r"\d+", label)
    return str(int(match.group())) if match else label


def find_component_facts(
    db: Session,
    project_id: str,
    *,
    component_code: Optional[str] = None,
    location: Optional[str] = None,
    segment: Optional[str] = None,
    group: Optional[str] = None,
    scope: str = "effective",
) -> list[ComponentFactMatch]:
    """Return matching facts from verified pages of ready project documents."""

    if not component_code and not segment and not group:
        return []
    if scope not in {"effective", "history"}:
        raise ValueError("scope must be effective or history")
    conditions = [
        PageExtraction.project_id == project_id,
        DocumentPage.project_id == project_id,
        SourceDocument.project_id == project_id,
        PageExtraction.status == "verified",
        SourceDocument.status == "ready",
    ]
    if scope == "effective":
        conditions.append(SourceDocument.is_effective.is_(True))
    rows = db.execute(
        select(PageExtraction, DocumentPage, SourceDocument)
        .join(
            DocumentPage,
            (PageExtraction.page_id == DocumentPage.id)
            & (PageExtraction.document_id == DocumentPage.document_id),
        )
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
        facts = data.get("component_facts", [])
        if not isinstance(facts, list):
            continue
        drawing_number = data.get("drawing_number")
        if not isinstance(drawing_number, str) or not drawing_number.strip():
            drawing_number = None
        revision = data.get("revision")
        if not isinstance(revision, str) or not revision.strip():
            revision = None
        for fact in facts:
            if not isinstance(fact, dict):
                continue
            if component_code and _label(fact.get("component_code")) != _label(component_code):
                continue
            if location and _label(fact.get("location")) != _label(location):
                continue
            if segment and _numbered_label(fact.get("segment")) != _numbered_label(segment):
                continue
            if group and _numbered_label(fact.get("group")) != _numbered_label(group):
                continue
            matches.append(
                ComponentFactMatch(
                    fact=fact,
                    document_id=document.id,
                    document_name=document.original_name,
                    page_number=page.page_number,
                    drawing_number=drawing_number or page.drawing_number,
                    revision=revision or page.revision,
                    table_row=fact.get("table_row"),
                    table_column=fact.get("table_column"),
                    url=f"/projects/{project_id}/documents/{document.id}/pages/{page.page_number}",
                )
            )
    return matches
