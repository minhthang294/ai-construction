"""Structured chat context: AI page extractions plus the component database.

Raw OCR/chunk text is never used here.  Every answer line is tied to a
citation: an extraction cites its document/page, a database row cites its
record id.  When nothing can be cited the caller must return
``NO_SOURCE_ANSWER``.

Construction progress is not acceptance: progress rows are labelled and never
turned into an acceptance conclusion.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from sqlalchemy import func, inspect, select
from sqlalchemy.orm import Session

from ..core.component_models import (
    ComponentAlias,
    ComponentDesignParameter,
    ComponentStage,
    ComponentWorkLink,
    DesignGroup,
    ProgressEvent,
    RepairScope,
    Segment,
    StageDefinition,
    StructuralComponent,
    StructureZone,
)
from ..core.design_parameters import (
    display_stage_name,
    format_parameter_value,
    load_t_values,
)
from .constants import (
    GROUNDING_WARNING,
    LOW_OCR_THRESHOLD,
    LOW_OCR_WARNING,
    NO_SOURCE_ANSWER,
    UNVERIFIED_KB_NOTE,
)
from .embeddings import fold_text, tokenize
from .grounding import unsupported_technical_values
from .models import DocumentPage, PageExtraction, SourceDocument
from .providers import ProviderAnswer, SourceContext
from .schemas import CitationOut

MAX_EXTRACTION_PAGES = 5
MAX_CONTEXT_CHARS = 40000
MAX_MATCHED_COMPONENTS = 20
MAX_RELATED_ROWS = 40
MAX_AGGREGATE_CITATIONS = 5
MAX_QUOTE = 1200

PROPOSED_WARNING = (
    "Một phần dữ kiện do AI trích xuất và chưa được kỹ sư xác minh."
)
PROGRESS_WARNING = (
    "Tiến độ thi công không phải nghiệm thu; database chưa có kết luận nghiệm thu."
)
STRUCTURED_FOOTER = (
    "Chỉ các bản ghi được đánh số ở trên là nguồn cho câu trả lời này; "
    "không dùng văn bản OCR thô."
)

_EXTRA_STOPWORDS = {
    "bao", "nhieu", "gi", "nao", "dau", "thuoc", "hay", "hoac", "nhu", "cung",
    "bi", "se", "da", "dang", "phai", "lam", "sao", "roi", "chi", "tiet",
    "cho", "toi", "minh", "cau", "hoi", "xem", "mo",
}
_CODE_TOKEN_RE = re.compile(
    r"(?<![\w-])[a-z]{1,4}[-./]?\d{1,4}(?:[-./][a-z0-9]{1,8})*(?![\w-])",
    re.IGNORECASE,
)
_DB_INTENT_RE = re.compile(
    r"\b(?:bao nhieu|tong|danh sach|liet ke|thong ke|nhom thiet ke|nhom nao|"
    r"cong doan|giai doan|tien do|pham vi sua chua|cau kien)\b"
)
_DATE_RE = re.compile(r"\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b")
_SEGMENT_RE = re.compile(r"\b(?:phan\s*doan|pd)\s*(\d{1,3})\b")
_STAGE_HINTS = ("duc", "son", "quet", "tram", "dan soi", "bom", "vet nut")


@dataclass(frozen=True)
class _ProgressQuery:
    day: Optional[int] = None
    month: Optional[int] = None
    year: Optional[int] = None
    segment: Optional[str] = None
    latest: bool = False


@dataclass
class _Candidate:
    context: SourceContext
    citation: CitationOut
    quote: str
    verified: bool
    matched_lines: List[str] = field(default_factory=list)
    line: str = ""


def _code_key(value: object) -> str:
    """Whole-token key: A2 -> 'a2', A23 -> 'a23', I40-42 / I-40-42 -> 'i4042'."""

    return re.sub(r"[^a-z0-9]", "", fold_text(str(value or "")))


def _code_tokens(text: str) -> Set[str]:
    return {_code_key(match.group(0)) for match in _CODE_TOKEN_RE.finditer(fold_text(text))}


def _question_terms(text: str) -> List[str]:
    return [term for term in tokenize(text) if term not in _EXTRA_STOPWORDS]


def _matches_term(term: str, folded_text: str) -> bool:
    # Whole token only: "a2" must not match inside "a23".
    return bool(re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", folded_text))


def _page_url(project_id: str, document_id: str, page_number: int) -> str:
    return f"/api/v1/projects/{project_id}/documents/{document_id}/pages/{page_number}"


def _json_text(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, default=str)


def _text_value(value: object) -> str:
    return "" if value is None else str(value).strip()


def _table_names(db: Session) -> Set[str]:
    try:
        return set(inspect(db.get_bind()).get_table_names())
    except Exception:  # noqa: BLE001 - isolated module tests may lack core tables
        return set()


def _component_tables_available(db: Session) -> bool:
    return {
        "structural_components",
        "structure_segments",
        "structure_zones",
        "component_design_groups",
        "component_aliases",
        "component_repair_scopes",
        "component_stage_definitions",
        "component_stages",
        "component_progress_events",
    } <= _table_names(db)


def _finalise_lines(candidates: List[_Candidate]) -> List[_Candidate]:
    for index, candidate in enumerate(candidates, start=1):
        candidate.context.index = index
        page = candidate.citation
        source = f"{page.document_name} trang {page.page_number}"
        candidate.line = "\n".join(
            f"- {line} [{index}] — {source}" for line in candidate.matched_lines
        )
    return candidates


def _fit_candidates(candidates: List[_Candidate]) -> List[_Candidate]:
    total = 0
    fitted: List[_Candidate] = []
    for candidate in candidates:
        size = len(candidate.context.text)
        if fitted and total + size > MAX_CONTEXT_CHARS:
            break
        total += size
        fitted.append(candidate)
    return _finalise_lines(fitted)


# ---------------------------------------------------------------------------
# AI page extractions
# ---------------------------------------------------------------------------


def _extraction_items(data: dict) -> List[Tuple[str, str, str]]:
    """Return (label, quote, match_text) for one extraction page."""

    items: List[Tuple[str, str, str]] = []
    for fact in data.get("component_facts") or []:
        if not isinstance(fact, dict):
            continue
        name = str(fact.get("fact_name") or "").strip()
        value = _text_value(fact.get("value"))
        unit = str(fact.get("unit") or "").strip()
        quote = str(fact.get("quote") or "").strip() or f"{name}: {value} {unit}".strip()
        if not name or not value:
            continue
        label = f"{name}: {value}{f' {unit}' if unit else ''}"
        match_text = fold_text(
            " ".join(
                str(part or "")
                for part in (
                    fact.get("component_code"),
                    fact.get("component_type"),
                    name,
                    value,
                    unit,
                    fact.get("group"),
                    fact.get("segment"),
                    fact.get("location"),
                    fact.get("table_column"),
                    quote,
                )
            )
        )
        items.append((label, quote, match_text))
    for item in data.get("key_values") or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        value = _text_value(item.get("value"))
        unit = str(item.get("unit") or "").strip()
        quote = str(item.get("quote") or "").strip() or f"{name}: {value} {unit}".strip()
        if not name or not value:
            continue
        label = f"{name}: {value}{f' {unit}' if unit else ''}"
        items.append((label, quote, fold_text(f"{name} {value} {unit} {quote}")))
    summary = " ".join(str(data.get("summary") or "").split())
    title = " ".join(str(data.get("title") or "").split())
    if summary or title:
        items.append(
            (f"Tóm tắt trang: {summary or title}", summary or title, fold_text(f"{title} {summary}"))
        )
    return items


def _extraction_candidates(
    db: Session, project_id: str, message: str, scope: str, top_k: int
) -> Tuple[List[_Candidate], List[str]]:
    if scope not in {"effective", "history"}:
        raise ValueError("scope must be effective or history")
    document_conditions = [
        SourceDocument.project_id == project_id,
        SourceDocument.status == "ready",
    ]
    if scope == "effective":
        document_conditions.append(SourceDocument.is_effective.is_(True))
    documents = {
        row.id: row
        for row in db.scalars(select(SourceDocument).where(*document_conditions)).all()
    }
    if not documents:
        return [], []
    pages = {
        (row.document_id, row.page_number): row
        for row in db.scalars(
            select(DocumentPage).where(DocumentPage.project_id == project_id)
        ).all()
        if row.document_id in documents
    }
    extractions = db.scalars(
        select(PageExtraction).where(
            PageExtraction.project_id == project_id,
            PageExtraction.status.in_(("verified", "proposed")),
        )
    ).all()

    by_page: Dict[Tuple[str, int], List[PageExtraction]] = {}
    for extraction in extractions:
        if extraction.document_id in documents:
            by_page.setdefault((extraction.document_id, extraction.page_number), []).append(
                extraction
            )

    terms = _question_terms(message)
    codes = _code_tokens(message)
    if not terms and not codes:
        return [], []

    scored: List[Tuple[int, float, _Candidate]] = []
    for (document_id, page_number), rows in by_page.items():
        rows.sort(key=lambda row: 0 if row.status == "verified" else 1)
        extraction = rows[0]
        try:
            data = json.loads(extraction.extraction_json)
        except (TypeError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        page = pages.get((document_id, page_number))
        document = documents[document_id]

        matched: List[Tuple[str, str]] = []
        score = 0.0
        for label, quote, match_text in _extraction_items(data):
            hits = {term for term in terms if _matches_term(term, match_text)}
            if codes & _code_tokens(match_text):
                hits.add("code")
            if not hits:
                continue
            score += len(hits)
            matched.append((label, quote))
        if not matched:
            continue

        matched = matched[:12]
        text = "\n".join(label for label, _quote in matched)
        if len(text) > 3000:
            text = text[:3000]
        quote = " | ".join(
            dict.fromkeys(quote for _label, quote in matched if quote)
        )[:MAX_QUOTE] or text
        drawing_number = (
            str(data.get("drawing_number") or "").strip()
            or (page.drawing_number if page else None)
            or document.drawing_number
        )
        revision = (
            str(data.get("revision") or "").strip()
            or (page.revision if page else None)
            or document.revision
        )
        citation = CitationOut(
            document_id=document_id,
            document_name=document.original_name,
            version=document.version,
            page_number=page_number,
            drawing_number=drawing_number or None,
            revision=revision or None,
            quote=quote,
            url=_page_url(project_id, document_id, page_number),
            page_id=page.id if page else extraction.page_id,
            ocr_confidence=(
                page.ocr_confidence
                if page is not None and page.extraction_method == "ocr"
                else None
            ),
            record_id=extraction.id,
            source="page_extraction",
        )
        context = SourceContext(
            index=0,
            text=text,
            document_name=document.original_name,
            version=document.version,
            page_number=page_number,
            drawing_number=drawing_number or None,
            revision=revision or None,
        )
        candidate = _Candidate(
            context=context,
            citation=citation,
            quote=quote,
            verified=extraction.status == "verified",
            matched_lines=[label for label, _quote in matched],
        )
        scored.append((0 if extraction.status == "verified" else 1, score, candidate))

    scored.sort(key=lambda item: (item[0], -item[1]))
    limit = max(1, min(top_k, MAX_EXTRACTION_PAGES))
    candidates = _fit_candidates([item[2] for item in scored[:limit]])
    warnings = (
        [PROPOSED_WARNING]
        if candidates and not all(candidate.verified for candidate in candidates)
        else []
    )
    return candidates, warnings


def _answer_from_extractions(
    message: str,
    provider,
    candidates: List[_Candidate],
    warnings: List[str],
) -> Tuple[ProviderAnswer, List[CitationOut], List[str], bool, float]:
    contexts = [candidate.context for candidate in candidates]
    text = ""
    try:
        answer = provider.answer(message, contexts)
        text = (answer.text or "").strip()
        warnings.extend(answer.warnings)
    except Exception:  # noqa: BLE001 - degrade to deterministic extracted data
        warnings.append("AI provider không khả dụng; đã dùng dữ kiện trích xuất trực tiếp.")

    if text == NO_SOURCE_ANSWER:
        return ProviderAnswer(text=NO_SOURCE_ANSWER), [], warnings, True, 0.0

    used = candidates
    indexes = [int(match) for match in re.findall(r"\[(\d{1,2})\]", text)]
    indexes = [value for value in dict.fromkeys(indexes) if 1 <= value <= len(candidates)]
    if indexes:
        used = [candidates[value - 1] for value in indexes]
        if unsupported_technical_values(text, [candidate.quote for candidate in used]):
            warnings.append(GROUNDING_WARNING)
            text = ""
    elif text:
        warnings.append(
            "Câu trả lời của provider thiếu citation; đã thay bằng dữ kiện trích xuất."
        )
        text = ""

    if not text:
        text = "\n".join(
            ["Dữ kiện AI trích xuất từ hồ sơ công trình:", *[c.line for c in candidates], "", STRUCTURED_FOOTER]
        )
        used = candidates

    citations = [candidate.citation for candidate in used]
    if not citations:
        return ProviderAnswer(text=NO_SOURCE_ANSWER), [], warnings, True, 0.0
    confidence = 0.82 if all(candidate.verified for candidate in used) else 0.4
    low_ocr = any(
        citation.ocr_confidence is not None and citation.ocr_confidence < LOW_OCR_THRESHOLD
        for citation in citations
    )
    if low_ocr:
        warnings.append(LOW_OCR_WARNING)
        confidence = min(confidence, 0.4)
    return ProviderAnswer(text=text), citations, warnings, False, confidence


# ---------------------------------------------------------------------------
# Component database
# ---------------------------------------------------------------------------


def _load_components(db: Session, project_id: str) -> List[StructuralComponent]:
    return list(
        db.scalars(
            select(StructuralComponent)
            .where(StructuralComponent.project_id == project_id)
            .order_by(StructuralComponent.canonical_code)
        ).all()
    )


def _component_key(canonical_code: str, aliases: List[str]) -> Set[str]:
    return {_code_key(canonical_code)} | {_code_key(alias) for alias in aliases}


def _matched_components(
    components: List[StructuralComponent],
    aliases_by_component: Dict[str, List[str]],
    message: str,
) -> List[StructuralComponent]:
    """Match project codes by whole token only; A2 never matches A23."""

    codes = _code_tokens(message)
    if not codes:
        return []
    return [
        component
        for component in components
        if codes & _component_key(component.canonical_code, aliases_by_component.get(component.id, []))
    ]


def _row_quote(row) -> str:
    data = {
        column.name: getattr(row, column.name)
        for column in row.__table__.columns
        if column.name not in {"created_by", "reviewed_by"}
    }
    return _json_text(data)[:MAX_QUOTE]


def _row_candidate(table: str, row, label: str, verified: bool) -> _Candidate:
    quote = _row_quote(row)
    citation = CitationOut(
        document_id=row.id,
        document_name=f"Database · {table}",
        version=1,
        page_number=0,
        quote=quote,
        url="",
        record_id=row.id,
        source="database",
    )
    context = SourceContext(
        index=0,
        text=quote,
        document_name=f"Database · {table}",
        version=1,
        page_number=0,
    )
    return _Candidate(
        context=context,
        citation=citation,
        quote=quote,
        verified=verified,
        matched_lines=[label],
    )


def _parameter_rows(db: Session, component_ids: List[str]):
    if not component_ids:
        return []
    return list(
        db.scalars(
            select(ComponentDesignParameter)
            .where(ComponentDesignParameter.component_id.in_(component_ids))
            .order_by(ComponentDesignParameter.component_id, ComponentDesignParameter.name)
        ).all()
    )


def _parameter_label(row: ComponentDesignParameter) -> str:
    name = {
        "t_cm": "t",
        "L1_m": "L1",
        "L2_m": "L2",
        "L3_m": "L3",
        "L4_m": "L4",
        "a_mm": "a",
        "b_mm": "b",
    }.get(row.name, row.name)
    unit = f" {row.unit}" if row.unit else ""
    return f"{name} = {format_parameter_value(row.value)}{unit}"


def _parameter_source(row: ComponentDesignParameter) -> str:
    parts = []
    if row.source_drawing:
        parts.append(f"bảng {row.source_drawing}")
    if row.source_page:
        parts.append(f"trang {row.source_page}")
    if row.source_row:
        parts.append(f"dòng {row.source_row}")
    return ", ".join(parts)


def _parameter_citation(
    row: ComponentDesignParameter,
) -> CitationOut:
    drawing = row.source_drawing
    page = int(row.source_page or 0)
    quote = _parameter_label(row)
    source = _parameter_source(row)
    if source:
        quote += f" — {source}"
    return CitationOut(
        document_id=row.id,
        document_name=f"Bảng thiết kế {drawing}" if drawing else "Bảng thiết kế",
        version=1,
        page_number=page,
        drawing_number=drawing,
        section=f"dòng {row.source_row}" if row.source_row else None,
        quote=quote,
        url="",
        record_id=row.id,
        source="database",
    )


def _parameter_lines(
    rows: List[ComponentDesignParameter],
) -> Tuple[List[str], List[CitationOut]]:
    lines: List[str] = []
    citations: List[CitationOut] = []
    for index, row in enumerate(rows, start=1):
        source = _parameter_source(row)
        suffix = f" ({source})" if source else ""
        lines.append(f"- {_parameter_label(row)}{suffix} [{index}]")
        citations.append(_parameter_citation(row))
    return lines, citations


def _design_parameter_intent(message: str) -> Optional[str]:
    folded = fold_text(message)
    if "thong so" in folded:
        return "list"
    if "chieu day" in folded or "do day" in folded:
        return "t"
    if re.search(r"\b(?:duc|dao|cat)\s+day\b", folded):
        return "t"
    if _parameter_range_query(message) is not None:
        return "value"
    if re.search(r"\bt\b", folded):
        return "value" if re.search(r"\bt\s*(?:=|bang|la)?\s*\d", folded) else "t"
    return None


def _parameter_value_query(message: str) -> Optional[float]:
    folded = fold_text(message)
    match = re.search(r"\bt\s*(?:=|bang|la)?\s*(\d+(?:[.,]\d+)?)", folded)
    if not match:
        return None
    raw = match.group(1).replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


def _parameter_range_query(message: str) -> Optional[Tuple[float, float]]:
    folded = fold_text(message)
    match = re.search(
        r"\bt\s*(?:tu|from)?\s*(\d+(?:[.,]\d+)?)\s*(?:-|–|den|toi)\s*(\d+(?:[.,]\d+)?)",
        folded,
    )
    if not match:
        return None
    try:
        low = float(match.group(1).replace(",", "."))
        high = float(match.group(2).replace(",", "."))
    except ValueError:
        return None
    return (min(low, high), max(low, high))


def answer_design_parameter_question(
    db: Session,
    project_id: str,
    message: str,
) -> Optional[Tuple[ProviderAnswer, List[CitationOut], List[str], bool, float]]:
    """Answer per-pile design-parameter questions from reviewed tables only."""

    if not _component_tables_available(db):
        return None
    intent = _design_parameter_intent(message)
    if intent is None:
        return None
    components = _load_components(db, project_id)
    if not components:
        return None
    aliases = _related_rows(db, ComponentAlias, [component.id for component in components])
    aliases_by_component: Dict[str, List[str]] = {}
    for alias in aliases:
        aliases_by_component.setdefault(alias.component_id, []).append(alias.alias)

    matched = _matched_components(components, aliases_by_component, message)
    query = _parse_progress_query(message)
    if intent in {"t", "list"} and matched:
        rows = _parameter_rows(db, [component.id for component in matched])
        if intent == "list":
            heading = f"Thông số thiết kế của {('cọc' if matched[0].type == 'pile' else 'dầm')} {matched[0].canonical_code}:"
            if rows:
                lines, citations = _parameter_lines(rows)
                return (
                    ProviderAnswer(text="\n".join([heading, *lines, "", STRUCTURED_FOOTER])),
                    citations,
                    [],
                    False,
                    0.8,
                )
            component_candidate = _row_candidate(
                "structural_components",
                matched[0],
                f"{'Cọc' if matched[0].type == 'pile' else 'Dầm'} "
                f"{matched[0].canonical_code} — bản ghi {matched[0].id}",
                matched[0].verification == "verified",
            )
            component_candidate = _finalise_lines([component_candidate])[0]
            return (
                ProviderAnswer(
                    text=(
                        f"{heading}\n- Chưa có thông số thiết kế trong bảng.\n"
                        f"{component_candidate.line}"
                    )
                ),
                [component_candidate.citation],
                ["Chưa có thông số thiết kế đã nhập cho cấu kiện này."],
                False,
                0.5,
            )
        t_rows = [row for row in rows if row.name == "t_cm"]
        if t_rows:
            lines, citations = _parameter_lines(t_rows[:3])
            heading = (
                f"{'Cọc' if matched[0].type == 'pile' else 'Dầm'} "
                f"{matched[0].canonical_code}:"
            )
            return (
                ProviderAnswer(text="\n".join([heading, *lines])),
                citations,
                [],
                False,
                0.8,
            )
        component_candidate = _row_candidate(
            "structural_components",
            matched[0],
            f"{'Cọc' if matched[0].type == 'pile' else 'Dầm'} "
            f"{matched[0].canonical_code} — bản ghi {matched[0].id}",
            matched[0].verification == "verified",
        )
        component_candidate = _finalise_lines([component_candidate])[0]
        answer = (
            f"{'Cọc' if matched[0].type == 'pile' else 'Dầm'} "
            f"{matched[0].canonical_code}: chưa có số liệu t trong bảng thiết kế. "
            f"{component_candidate.line}"
        )
        return (
            ProviderAnswer(text=answer),
            [component_candidate.citation],
            ["Chưa có số liệu t trong bảng thiết kế; không suy đoán giá trị."],
            False,
            0.5,
        )

    if intent == "value":
        bounds = _parameter_range_query(message)
        if bounds is not None:
            low, high = bounds
        else:
            target = _parameter_value_query(message)
            if target is None:
                return None
            low = high = target
        scoped = components
        scope_label = "công trình"
        if query.segment:
            segments = {
                row.id: row
                for row in db.scalars(
                    select(Segment)
                    .join(StructureZone, Segment.zone_id == StructureZone.id)
                    .where(StructureZone.project_id == project_id)
                ).all()
            }
            scoped = [
                component
                for component in components
                if component.segment_id in segments
                and str(segments[component.segment_id].number) == query.segment
            ]
            scope_label = f"PD{query.segment}"
        if not scoped:
            return (
                ProviderAnswer(text=NO_SOURCE_ANSWER),
                [],
                [f"Không có cấu kiện nào trong {scope_label}."],
                True,
                0.0,
            )
        rows = [
            row
            for row in _parameter_rows(db, [component.id for component in scoped])
            if row.name == "t_cm" and low <= float(row.value) <= high
        ]
        if rows:
            component_by_id = {component.id: component for component in scoped}
            lines: List[str] = []
            citations: List[CitationOut] = []
            for index, row in enumerate(rows[:10], start=1):
                component = component_by_id.get(row.component_id)
                code = component.canonical_code if component else row.component_id
                source = _parameter_source(row)
                suffix = f" ({source})" if source else ""
                lines.append(f"- {code}: {_parameter_label(row)}{suffix} [{index}]")
                citations.append(_parameter_citation(row))
            answer = (
                f"{scope_label}: {len(rows)} cọc có t = "
                f"{format_parameter_value(low)}"
                + (f"–{format_parameter_value(high)}" if high != low else "")
                + " cm trong bảng thiết kế:"
            )
            if len(rows) > 10:
                answer += f"\n- Chỉ nêu 10/{len(rows)} cọc."
            return (
                ProviderAnswer(text="\n".join([answer, *lines])),
                citations,
                [],
                False,
                0.8,
            )
        component_candidates = [
            _row_candidate(
                "structural_components",
                component,
                f"{'Cọc' if component.type == 'pile' else 'Dầm'} "
                f"{component.canonical_code} — bản ghi {component.id}",
                component.verification == "verified",
            )
            for component in scoped[:5]
        ]
        component_candidates = _finalise_lines(component_candidates)
        answer = (
            f"{scope_label}: không có cọc nào có t = "
            f"{format_parameter_value(low)}"
            + (f"–{format_parameter_value(high)}" if high != low else "")
            + " cm trong bảng thiết kế "
            f"(đã kiểm tra {len(scoped)} cấu kiện)."
        )
        if component_candidates:
            answer += "\n" + "\n".join(
                candidate.line for candidate in component_candidates
            )
        return (
            ProviderAnswer(text=answer),
            [candidate.citation for candidate in component_candidates],
            ["Không tìm thấy giá trị t yêu cầu trong bảng thiết kế; không suy đoán."],
            False,
            0.5,
        )
    return None


def _related_rows(db: Session, model, ids: List[str]):
    if not ids:
        return []
    query = select(model).where(model.component_id.in_(ids))
    if model is ProgressEvent:
        # Voided events are corrections and must never feed answers.
        query = query.where(ProgressEvent.voided_at.is_(None))
    return list(db.scalars(query).all())


def _component_detail(
    db: Session,
    project_id: str,
    components: List[StructuralComponent],
) -> Tuple[List[_Candidate], List[str]]:
    ids = [component.id for component in components]
    aliases = _related_rows(db, ComponentAlias, ids)
    scopes = _related_rows(db, RepairScope, ids)
    work_links = _related_rows(db, ComponentWorkLink, ids)
    stages = _related_rows(db, ComponentStage, ids)
    events = _related_rows(db, ProgressEvent, ids)
    t_by_component = load_t_values(db, ids)

    stage_definitions = {
        row.id: row
        for row in db.scalars(
            select(StageDefinition).where(StageDefinition.project_id == project_id)
        ).all()
    }
    zones = {
        row.id: row
        for row in db.scalars(
            select(StructureZone).where(StructureZone.project_id == project_id)
        ).all()
    }
    segments = {
        row.id: row
        for row in db.scalars(select(Segment).where(Segment.zone_id.in_(list(zones)))).all()
    } if zones else {}

    candidates: List[_Candidate] = []
    for component in components:
        segment = segments.get(component.segment_id)
        zone = zones.get(segment.zone_id) if segment else None
        place = ", ".join(part for part in (
            f"phân đoạn {segment.number}" if segment else "",
            zone.name if zone else "",
        ) if part)
        scope_names = [
            f"{scope.kind} (revision {scope.revision}, {scope.verification})"
            for scope in scopes
            if scope.component_id == component.id
        ]
        label = (
            f"Cấu kiện {component.canonical_code} ({component.type})"
            + (f", {place}" if place else "")
            + (f", phạm vi sửa chữa: {', '.join(scope_names)}" if scope_names else "")
            + f", xác minh: {component.verification}"
        )
        candidates.append(
            _row_candidate(
                "structural_components",
                component,
                f"{label} — bản ghi {component.id}",
                component.verification == "verified",
            )
        )
    for alias in aliases:
        candidates.append(
            _row_candidate(
                "component_aliases",
                alias,
                f"Mã thay thế {alias.alias} — bản ghi {alias.id}",
                True,
            )
        )
    for scope in scopes:
        candidates.append(
            _row_candidate(
                "component_repair_scopes",
                scope,
                f"Phạm vi {scope.kind} revision {scope.revision} "
                f"({scope.verification}) — bản ghi {scope.id}",
                scope.verification == "verified",
            )
        )
    for link in work_links:
        candidates.append(
            _row_candidate(
                "component_work_links",
                link,
                f"Liên kết công việc: {link.work} ({link.raw_location}) "
                f"— bản ghi {link.id}",
                True,
            )
        )
    for stage in stages:
        definition = stage_definitions.get(stage.stage_definition_id)
        component = next(
            (row for row in components if row.id == stage.component_id), None
        )
        name = _stage_label(
            definition, t_by_component.get(stage.component_id) if component else None
        )
        quantity = (
            f", khối lượng thiết kế: {_json_text(stage.design_quantity)}"
            if stage.design_quantity
            else ""
        )
        candidates.append(
            _row_candidate(
                "component_stages",
                stage,
                f"Công đoạn {name}{quantity} — bản ghi {stage.id}",
                True,
            )
        )
    for event in events:
        candidates.append(
            _row_candidate(
                "component_progress_events",
                event,
                f"Tiến độ thi công ngày {event.event_date}: {event.status} "
                f"(không phải nghiệm thu) — bản ghi {event.id}",
                True,
            )
        )

    warnings = [PROGRESS_WARNING]
    if len(candidates) > MAX_RELATED_ROWS:
        return [], warnings
    if sum(len(candidate.context.text) for candidate in candidates) > MAX_CONTEXT_CHARS:
        return [], warnings
    return _finalise_lines(candidates), warnings


def _aggregate_candidates(
    db: Session, project_id: str, components: List[StructuralComponent], notice: str = ""
) -> Tuple[List[_Candidate], str, List[str]]:
    pile = sum(1 for component in components if component.type == "pile")
    beam = sum(1 for component in components if component.type == "beam")
    groups = db.scalar(
        select(func.count()).select_from(DesignGroup).where(DesignGroup.project_id == project_id)
    ) or 0
    stage_count = db.scalar(
        select(func.count())
        .select_from(StageDefinition)
        .where(StageDefinition.project_id == project_id)
    ) or 0
    progress_count = db.scalar(
        select(func.count())
        .select_from(ProgressEvent)
        .where(
            ProgressEvent.component_id.in_([component.id for component in components]),
            ProgressEvent.voided_at.is_(None),
        )
    ) or 0
    segments = db.scalar(
        select(func.count())
        .select_from(Segment)
        .join(StructureZone, Segment.zone_id == StructureZone.id)
        .where(StructureZone.project_id == project_id)
    ) or 0
    lines = [
        "Tổng hợp database cấu kiện của công trình (không phải kết luận nghiệm thu):",
        f"- {len(components)} cấu kiện: {pile} cọc, {beam} dầm; "
        f"{segments} phân đoạn, {groups} nhóm thiết kế.",
        f"- {stage_count} định nghĩa công đoạn; {progress_count} sự kiện tiến độ đã ghi "
        "(tiến độ không phải nghiệm thu).",
        "Nêu một mã cấu kiện cụ thể để xem chi tiết; không liệt kê toàn bộ công trình.",
    ]
    citations = [
        _row_candidate(
            "structural_components",
            component,
            f"Cấu kiện {component.canonical_code} ({component.type}) — bản ghi {component.id}",
            component.verification == "verified",
        )
        for component in components[:MAX_AGGREGATE_CITATIONS]
    ]
    citations = _finalise_lines(citations)
    text = notice + "\n".join(lines)
    if citations:
        text += "\n" + "\n".join(candidate.line for candidate in citations)
        text += f"\nĐại diện {len(citations)}/{len(components)} bản ghi; tổng hợp đếm từ toàn bộ."
    text += f"\n{PROGRESS_WARNING}"
    return citations, text, [PROGRESS_WARNING]


def _project_rows(db: Session, project_id: str):
    components = _load_components(db, project_id)
    component_by_id = {row.id: row for row in components}
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
    stage_definitions = {
        row.id: row
        for row in db.scalars(
            select(StageDefinition).where(StageDefinition.project_id == project_id)
        ).all()
    }
    stages = _related_rows(db, ComponentStage, list(component_by_id)) if component_by_id else []
    events = _related_rows(db, ProgressEvent, list(component_by_id)) if component_by_id else []
    return (
        components,
        component_by_id,
        zones,
        segments,
        stage_definitions,
        stages,
        events,
    )


def _parse_progress_query(message: str) -> _ProgressQuery:
    folded = fold_text(message)
    date_match = _DATE_RE.search(folded)
    segment_match = _SEGMENT_RE.search(folded)
    day = month = year = None
    if date_match:
        day = int(date_match.group(1))
        month = int(date_match.group(2))
        raw_year = date_match.group(3)
        if raw_year:
            year = int(raw_year)
            if year < 100:
                year += 2000
    return _ProgressQuery(
        day=day,
        month=month,
        year=year,
        segment=str(int(segment_match.group(1))) if segment_match else None,
        latest=bool(re.search(r"\b(?:gan nhat|moi nhat|hom nay|moi cap nhat)\b", folded)),
    )


def is_progress_question(message: str) -> bool:
    """True for daily-progress, pending-stage or 'current stage' questions."""

    folded = fold_text(message)
    if "tien do" in folded or "buoc nao" in folded or "dang o buoc" in folded:
        return True
    if _DATE_RE.search(folded):
        return True
    return "chua" in folded and any(hint in folded for hint in _STAGE_HINTS)


def _stage_label(
    definition: Optional[StageDefinition], t_value: Optional[float] = None
) -> str:
    if definition is None:
        return "công đoạn"
    return display_stage_name(
        f"{definition.code} {definition.name}".strip(),
        [t_value],
    )


def _stage_for_component(
    stage: ComponentStage, definitions: Dict[str, StageDefinition]
) -> StageDefinition:
    return definitions.get(stage.stage_definition_id)


def _event_candidate(event: ProgressEvent, label: str) -> _Candidate:
    return _row_candidate("component_progress_events", event, label, True)


def _daily_progress_answer(
    db: Session,
    project_id: str,
    message: str,
    query: _ProgressQuery,
    components: List[StructuralComponent],
    segments: Dict[str, Segment],
    definitions: Dict[str, StageDefinition],
    stages: List[ComponentStage],
    events: List[ProgressEvent],
) -> Optional[Tuple[ProviderAnswer, List[CitationOut], List[str], bool, float]]:
    component_by_id = {row.id: row for row in components}
    stage_by_id = {row.id: row for row in stages}
    relevant = [
        event
        for event in events
        if event.component_id in component_by_id
        and (
            query.segment is None
            or (
                component_by_id[event.component_id].segment_id in segments
                and str(segments[component_by_id[event.component_id].segment_id].number)
                == query.segment
            )
        )
    ]
    if query.day is not None and query.month is not None:
        relevant = [
            event
            for event in relevant
            if event.event_date.day == query.day
            and event.event_date.month == query.month
            and (query.year is None or event.event_date.year == query.year)
        ]
        if not relevant:
            label = f"{query.day:02d}/{query.month:02d}"
            if query.year:
                label += f"/{query.year}"
            return (
                ProviderAnswer(text=NO_SOURCE_ANSWER),
                [],
                [
                    f"Không có sự kiện tiến độ ngày {label}"
                    + (f" cho PD{query.segment}" if query.segment else "")
                    + " trong database cấu kiện."
                ],
                True,
                0.0,
            )
    else:
        if not relevant:
            return (
                ProviderAnswer(text=NO_SOURCE_ANSWER),
                [],
                ["Chưa có sự kiện tiến độ nào trong database cấu kiện."],
                True,
                0.0,
            )
        latest_date = max(event.event_date for event in relevant)
        relevant = [event for event in relevant if event.event_date == latest_date]

    relevant.sort(key=lambda event: (event.event_date, event.created_at), reverse=True)
    date = relevant[0].event_date
    status_counts: Dict[str, int] = {}
    for event in relevant:
        status_counts[event.status] = status_counts.get(event.status, 0) + 1
    component_ids = {event.component_id for event in relevant}
    header = "Tiến độ thi công ngày " + date.strftime("%d/%m/%Y")
    if query.segment:
        header += f" · PD{query.segment}"
    header += " (không phải nghiệm thu):"
    lines = [
        header,
        f"- {len(relevant)} sự kiện / {len(component_ids)} cấu kiện: "
        + ", ".join(f"{key} {value}" for key, value in sorted(status_counts.items()))
        + ".",
    ]

    candidates: List[_Candidate] = []
    t_by_component = load_t_values(db, [event.component_id for event in relevant])
    for event in relevant[:MAX_RELATED_ROWS]:
        component = component_by_id[event.component_id]
        stage = stage_by_id.get(event.component_stage_id)
        definition = _stage_for_component(stage, definitions) if stage else None
        quantity = (
            f", {event.quantity:g} {event.unit or ''}".rstrip()
            if event.quantity is not None
            else ""
        )
        label = (
            f"{'Cọc' if component.type == 'pile' else 'Dầm'} {component.canonical_code}"
            f" · {_stage_label(definition, t_by_component.get(component.id))}: "
            f"{event.status}{quantity} "
            f"(ngày {event.event_date:%d/%m/%Y}) — bản ghi {event.id}"
        )
        candidates.append(_event_candidate(event, label))
    if len(relevant) > MAX_RELATED_ROWS:
        lines.append(
            f"- Chỉ nêu {MAX_RELATED_ROWS}/{len(relevant)} sự kiện; tổng hợp đếm từ toàn bộ."
        )
    candidates = _finalise_lines(candidates)
    lines.extend(candidate.line for candidate in candidates)
    lines.append(PROGRESS_WARNING)
    return (
        ProviderAnswer(text="\n".join(lines)),
        [candidate.citation for candidate in candidates],
        [PROGRESS_WARNING],
        False,
        0.7,
    )


def _pending_stage_answer(
    db: Session,
    project_id: str,
    message: str,
    query: _ProgressQuery,
    components: List[StructuralComponent],
    segments: Dict[str, Segment],
    definitions: Dict[str, StageDefinition],
    stages: List[ComponentStage],
    events: List[ProgressEvent],
) -> Optional[Tuple[ProviderAnswer, List[CitationOut], List[str], bool, float]]:
    folded = fold_text(message)
    hints = [hint for hint in _STAGE_HINTS if hint in folded]
    definitions_in_use = {
        stage.stage_definition_id
        for stage in stages
        if stage.stage_definition_id in definitions
    }
    chosen = [
        definition
        for definition in definitions.values()
        if definition.id in definitions_in_use
        and any(
            hint in fold_text(f"{definition.code} {definition.name}")
            for hint in hints
        )
    ]
    if not chosen and hints:
        chosen = [
            definition
            for definition in definitions.values()
            if definition.id in definitions_in_use
        ]
    if not chosen:
        return None
    definition_ids = {definition.id for definition in chosen}

    component_type = (
        "pile" if re.search(r"\b(?:coc|pile)\b", folded)
        else "beam" if re.search(r"\b(?:dam|beam)\b", folded)
        else None
    )
    scoped = [
        component
        for component in components
        if (component_type is None or component.type == component_type)
        and (
            query.segment is None
            or (
                component.segment_id in segments
                and str(segments[component.segment_id].number) == query.segment
            )
        )
    ]
    if not scoped:
        return None
    stage_by_component: Dict[str, List[ComponentStage]] = {}
    for stage in stages:
        if stage.stage_definition_id in definition_ids:
            stage_by_component.setdefault(stage.component_id, []).append(stage)
    stage_ids = {stage.id for stage in stages if stage.stage_definition_id in definition_ids}
    completed_stage_ids = {
        event.component_stage_id
        for event in events
        if event.component_stage_id in stage_ids and event.status == "COMPLETED"
    }
    with_stage = [component for component in scoped if stage_by_component.get(component.id)]
    done = [component for component in with_stage if any(
        stage.id in completed_stage_ids for stage in stage_by_component[component.id]
    )]
    pending = [component for component in with_stage if component not in done]
    if not with_stage:
        return None
    t_by_component = load_t_values(db, [component.id for component in with_stage])
    definition_names = ", ".join(
        display_stage_name(
            f"{item.code} {item.name}".strip(),
            [t_by_component.get(component.id) for component in with_stage],
        )
        for item in chosen[:3]
    )

    noun = "cọc" if component_type == "pile" else "dầm" if component_type == "beam" else "cấu kiện"
    scope_label = f"PD{query.segment}" if query.segment else "công trình"
    header = (
        f'Công đoạn "{definition_names}" tại {scope_label} '
        f"(không phải nghiệm thu): còn {len(pending)}/{len(with_stage)} {noun} chưa hoàn thành."
    )
    lines = [header]
    if len(done) == len(with_stage):
        lines.append(f"- Đã ghi COMPLETED cho toàn bộ {len(with_stage)} {noun} có công đoạn này.")
    citations = [
        _row_candidate(
            "structural_components",
            component,
            f"{'Cọc' if component.type == 'pile' else 'Dầm'} {component.canonical_code} "
            f"— chưa COMPLETED — bản ghi {component.id}",
            component.verification == "verified",
        )
        for component in pending[:10]
    ]
    if not citations:
        citations = [
            _row_candidate(
                "structural_components",
                component,
                f"{'Cọc' if component.type == 'pile' else 'Dầm'} {component.canonical_code} "
                f"— đã COMPLETED — bản ghi {component.id}",
                component.verification == "verified",
            )
            for component in done[:5]
        ]
    citations = _finalise_lines(citations)
    lines.extend(candidate.line for candidate in citations)
    lines.append(PROGRESS_WARNING)
    return (
        ProviderAnswer(text="\n".join(lines)),
        [candidate.citation for candidate in citations],
        [PROGRESS_WARNING],
        False,
        0.7,
    )


def _component_stage_answer(
    db: Session,
    message: str,
    components: List[StructuralComponent],
    segments: Dict[str, Segment],
    definitions: Dict[str, StageDefinition],
    stages: List[ComponentStage],
    events: List[ProgressEvent],
) -> Optional[Tuple[ProviderAnswer, List[CitationOut], List[str], bool, float]]:
    matched = _matched_components(components, {}, message)
    if not matched:
        return None
    component = matched[0]
    t_value = load_t_values(db, [component.id]).get(component.id)
    component_stages = [stage for stage in stages if stage.component_id == component.id]
    stage_by_id = {stage.id: stage for stage in component_stages}
    component_events = [
        event for event in events if event.component_id == component.id
    ]
    component_events.sort(
        key=lambda event: (event.event_date, event.created_at or event.event_date),
        reverse=True,
    )
    noun = "Cọc" if component.type == "pile" else "Dầm"
    lines = []
    citations: List[_Candidate] = []
    if component_events:
        latest = component_events[0]
        stage = stage_by_id.get(latest.component_stage_id)
        definition = _stage_for_component(stage, definitions) if stage else None
        lines.append(
            f'{noun} {component.canonical_code} đang ở bước "{_stage_label(definition, t_value)}": '
            f"{latest.status}, ngày {latest.event_date:%d/%m/%Y} (không phải nghiệm thu)."
        )
        citations.append(
            _event_candidate(
                latest,
                f"{noun} {component.canonical_code} · {_stage_label(definition, t_value)}: "
                f"{latest.status}, ngày {latest.event_date:%d/%m/%Y} — bản ghi {latest.id}",
            )
        )
    elif component_stages:
        labels = ", ".join(
            _stage_label(_stage_for_component(stage, definitions), t_value)
            for stage in component_stages[:5]
        )
        lines.append(
            f"{noun} {component.canonical_code} có công đoạn ({labels}) "
            "nhưng chưa có sự kiện tiến độ."
        )
        citations.extend(
            _row_candidate(
                "component_stages",
                stage,
                f"{noun} {component.canonical_code} · "
                f"{_stage_label(_stage_for_component(stage, definitions), t_value)} "
                f"— bản ghi {stage.id}",
                True,
            )
            for stage in component_stages[:5]
        )
    else:
        lines.append(
            f"{noun} {component.canonical_code} chưa được gắn công đoạn trong database."
        )
    citations.append(
        _row_candidate(
            "structural_components",
            component,
            f"{noun} {component.canonical_code} — bản ghi {component.id}",
            component.verification == "verified",
        )
    )
    citations = _finalise_lines(citations)
    lines.extend(candidate.line for candidate in citations)
    lines.append(PROGRESS_WARNING)
    return (
        ProviderAnswer(text="\n".join(lines)),
        [candidate.citation for candidate in citations],
        [PROGRESS_WARNING],
        False,
        0.7,
    )


def answer_progress_question(
    db: Session,
    project_id: str,
    message: str,
) -> Optional[Tuple[ProviderAnswer, List[CitationOut], List[str], bool, float]]:
    """Answer daily progress, pending stage and current-stage questions from DB rows."""

    if not _component_tables_available(db) or not is_progress_question(message):
        return None
    (
        components,
        _component_by_id,
        _zones,
        segments,
        definitions,
        stages,
        events,
    ) = _project_rows(db, project_id)
    if not components:
        return None
    query = _parse_progress_query(message)
    folded = fold_text(message)
    if _code_tokens(message) and ("buoc nao" in folded or "dang o buoc" in folded):
        return _component_stage_answer(
            db, message, components, segments, definitions, stages, events
        )
    if "chua" in folded and any(hint in folded for hint in _STAGE_HINTS):
        answer = _pending_stage_answer(
            db, project_id, message, query, components, segments, definitions, stages, events
        )
        if answer is not None:
            return answer
    if "tien do" in folded or query.latest or (
        query.day is not None and query.month is not None
    ):
        return _daily_progress_answer(
            db, project_id, message, query, components, segments, definitions, stages, events
        )
    return None


def answer_database_question(
    db: Session,
    project_id: str,
    message: str,
) -> Optional[Tuple[ProviderAnswer, List[CitationOut], List[str], bool, float]]:
    """Exact-code or aggregate answer from the component database, never OCR."""
    if not _component_tables_available(db):
        return None
    components = _load_components(db, project_id)
    if not components:
        return None
    aliases = _related_rows(db, ComponentAlias, [component.id for component in components])
    aliases_by_component: Dict[str, List[str]] = {}
    for alias in aliases:
        aliases_by_component.setdefault(alias.component_id, []).append(alias.alias)

    codes = _code_tokens(message)
    if codes:
        matched = _matched_components(components, aliases_by_component, message)
        if not matched:
            notice = (
                "Không tìm thấy mã "
                + ", ".join(sorted(codes))
                + " trong database cấu kiện; hãy nêu một mã cấu kiện cụ thể."
            )
            return ProviderAnswer(text=NO_SOURCE_ANSWER), [], [notice], True, 0.0
        if len(matched) > MAX_MATCHED_COMPONENTS:
            notice = (
                f"{len(matched)} cấu kiện cùng khớp; cần nêu một mã cụ thể. "
            )
            citations, text, warnings = _aggregate_candidates(db, project_id, components, notice)
            return ProviderAnswer(text=text), [c.citation for c in citations], warnings, False, 0.5
        candidates, warnings = _component_detail(db, project_id, matched)
        if not candidates:
            citations, text, warnings = _aggregate_candidates(db, project_id, components)
            return ProviderAnswer(text=text), [c.citation for c in citations], warnings, False, 0.5
        text = "\n".join(
            [
                "Bản ghi database cấu kiện của công trình:",
                *[candidate.line for candidate in candidates],
                "",
                STRUCTURED_FOOTER,
            ]
        )
        return (
            ProviderAnswer(text=text),
            [candidate.citation for candidate in candidates],
            warnings,
            False,
            0.7,
        )

    if not _DB_INTENT_RE.search(fold_text(message)):
        return None
    citations, text, warnings = _aggregate_candidates(db, project_id, components)
    return ProviderAnswer(text=text), [c.citation for c in citations], warnings, False, 0.5


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def answer_structured_question(
    db: Session,
    project_id: str,
    message: str,
    top_k: int,
    provider,
    scope: str = "effective",
) -> Tuple[ProviderAnswer, List[CitationOut], List[str], bool, float]:
    """Answer from AI extractions, else the component database, never OCR text."""

    extraction_candidates, warnings = _extraction_candidates(
        db, project_id, message, scope, top_k
    )
    if extraction_candidates:
        return _answer_from_extractions(message, provider, extraction_candidates, warnings)

    database = answer_database_question(db, project_id, message)
    if database is not None:
        answer, citations, db_warnings, no_source, confidence = database
        return answer, citations, [*warnings, *db_warnings], no_source, confidence

    return (
        ProviderAnswer(text=NO_SOURCE_ANSWER),
        [],
        [*warnings, UNVERIFIED_KB_NOTE],
        True,
        0.0,
    )
