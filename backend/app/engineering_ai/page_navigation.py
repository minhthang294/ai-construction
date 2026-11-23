"""Resolve "open page" questions to source pages and citations.

Navigation is deliberately separate from component lookup: a request such as
``mở trang biện pháp thi công cho cọc nhóm 2`` must open a construction-method
page, not dump the pile codes of group 2.  When a request matches several
pages with similar strength, the answer lists the candidates and asks for a
narrower group/component instead of silently picking one.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Iterable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from .constants import NO_SOURCE_ANSWER
from .embeddings import fold_text
from .models import DocumentPage, PageExtraction, SourceDocument
from .providers import ProviderAnswer
from .schemas import CitationOut, PageActionOut


_NAVIGATION = re.compile(
    r"\b(?:mo|xem)\b[^.?!]{0,50}\b(?:trang|ban ve|tai lieu|ho so)\b"
)
_PAGE_NUMBER = re.compile(r"\btrang\s*(?:so\s*)?(\d{1,4})\b")
_SEGMENT = re.compile(r"\b(?:phan\s*doan|pd|doan)\s*(\d{1,3})\b")
_GROUP = re.compile(r"\bnhom\s*(?:coc\s*)?(\d{1,3})\b")
_SECTION = re.compile(r"\b(\d{1,2}\.\d{1,2})\b")

_METHOD_TERMS = (
    "bien phap thi cong",
    "quy trinh thi cong",
    "chi dan thi cong",
    "quy trinh xu ly",
    "cong tac sua chua",
    "sua chua coc",
    "thi cong",
)
_DESIGN_TERMS = (
    "thiet ke",
    "ban ve",
    "mat bang",
    "so do",
    "ket cau",
    "hien trang",
    "giai phap",
)


@dataclass(frozen=True)
class _NavigationQuery:
    page_number: Optional[int]
    location: Optional[str]
    segment: Optional[str]
    group: Optional[str]
    component_type: Optional[str]
    method: bool
    design: bool


@dataclass
class _PageRecord:
    document: SourceDocument
    page: DocumentPage
    statuses: set[str]
    facts: list[dict]
    titles: list[str]
    summaries: list[str]
    best_data: Optional[dict]
    has_verified: bool
    has_proposed: bool
    title_text: str
    summary_text: str
    all_text: str
    score: float = 0.0


@dataclass(frozen=True)
class PageNavigationResult:
    answer: ProviderAnswer
    citations: list[CitationOut]
    warnings: list[str]
    no_source: bool
    confidence: float
    page_action: Optional[PageActionOut] = None


def parse_page_navigation_query(message: str) -> Optional[_NavigationQuery]:
    """Return a navigation query, or ``None`` for an ordinary question."""

    text = fold_text(message)
    if not _NAVIGATION.search(text):
        return None
    page_match = _PAGE_NUMBER.search(text)
    segment_match = _SEGMENT.search(text)
    group_match = _GROUP.search(text)
    location = (
        "Cầu chính"
        if "cau chinh" in text
        else "Cầu dẫn"
        if "cau dan" in text
        else None
    )
    component_type = (
        "pile"
        if re.search(r"\bcoc\b", text)
        else "beam"
        if re.search(r"\bdam\b", text)
        else None
    )
    design = any(term in text for term in _DESIGN_TERMS)
    method_explicit = any(
        term
        in text
        for term in (
            "bien phap thi cong",
            "bien phap sua chua",
            "quy trinh thi cong",
            "quy trinh xu ly",
            "chi dan thi cong",
            "thuyet minh",
        )
    )
    method = method_explicit or ("thi cong" in text and not design)
    if method_explicit:
        design = False
    page_number = int(page_match.group(1)) if page_match else None
    segment = str(int(segment_match.group(1))) if segment_match else None
    group = str(int(group_match.group(1))) if group_match else None
    if not any((page_number, location, segment, group, component_type, method, design)):
        return None
    return _NavigationQuery(
        page_number=page_number,
        location=location,
        segment=segment,
        group=group,
        component_type=component_type,
        method=method,
        design=design,
    )


def _unique(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _load_pages(
    db: Session, project_id: str, scope: str
) -> list[_PageRecord]:
    if scope not in {"effective", "history"}:
        raise ValueError("scope must be effective or history")
    document_conditions = [
        SourceDocument.project_id == project_id,
        SourceDocument.status == "ready",
    ]
    if scope == "effective":
        document_conditions.append(SourceDocument.is_effective.is_(True))
    documents = {
        document.id: document
        for document in db.scalars(
            select(SourceDocument).where(*document_conditions)
        ).all()
    }
    pages = db.scalars(
        select(DocumentPage).where(DocumentPage.project_id == project_id)
    ).all()
    extractions = db.scalars(
        select(PageExtraction).where(
            PageExtraction.project_id == project_id,
            PageExtraction.status.in_(("verified", "proposed")),
        )
    ).all()
    by_page: dict[tuple[str, int], list[PageExtraction]] = {}
    for extraction in extractions:
        by_page.setdefault(
            (extraction.document_id, extraction.page_number), []
        ).append(extraction)

    records: list[_PageRecord] = []
    for page in pages:
        document = documents.get(page.document_id)
        if document is None:
            continue
        parsed: list[tuple[str, dict]] = []
        for extraction in by_page.get((page.document_id, page.page_number), []):
            try:
                data = json.loads(extraction.extraction_json)
            except (TypeError, ValueError):
                continue
            if isinstance(data, dict):
                parsed.append((extraction.status, data))
        parsed.sort(key=lambda item: 0 if item[0] == "verified" else 1)
        statuses = {status for status, _ in parsed}
        titles = _unique(
            [str(data.get("title") or "").strip() for _, data in parsed]
        )
        summaries = _unique(
            [str(data.get("summary") or "").strip() for _, data in parsed]
        )
        facts = [
            fact
            for _, data in parsed
            for fact in (data.get("component_facts") or [])
            if isinstance(fact, dict)
        ]
        best_data = parsed[0][1] if parsed else None
        fact_text = " ".join(
            " ".join(
                part
                for part in (
                    str(fact.get("component_code") or ""),
                    str(fact.get("component_type") or ""),
                    str(fact.get("fact_name") or ""),
                    str(fact.get("value") or ""),
                    str(fact.get("unit") or ""),
                    f"nhóm {fact.get('group')}" if fact.get("group") else "",
                    f"phân đoạn {fact.get('segment')}" if fact.get("segment") else "",
                    str(fact.get("location") or ""),
                    str(fact.get("quote") or ""),
                    str(fact.get("table_column") or ""),
                    "cọc" if fact.get("component_type") == "pile" else "",
                    "dầm" if fact.get("component_type") == "beam" else "",
                )
                if part
            )
            for fact in facts
        )
        page_text = fold_text(
            " ".join(
                part
                for part in (
                    str(page.drawing_number or ""),
                    str(page.revision or ""),
                    str(document.drawing_number or ""),
                    str(document.revision or ""),
                    document.original_name,
                    document.type,
                )
                if part
            )
        )
        all_text = " ".join([page_text, *titles, *summaries, fact_text])
        records.append(
            _PageRecord(
                document=document,
                page=page,
                statuses=statuses,
                facts=facts,
                titles=titles,
                summaries=summaries,
                best_data=best_data,
                has_verified="verified" in statuses,
                has_proposed="proposed" in statuses,
                title_text=fold_text(" ".join(titles)),
                summary_text=fold_text(" ".join(summaries)),
                all_text=fold_text(all_text),
            )
        )
    return records


def _has_segment(text: str, segment: str) -> bool:
    return bool(
        re.search(
            rf"\b(?:phan\s*doan|pd|doan)\s*{re.escape(segment)}\b",
            text,
        )
    )


def _has_group(text: str, group: str) -> bool:
    return bool(
        re.search(rf"\bnhom\s*(?:coc\s*)?{re.escape(group)}\b", text)
    )


def _has_component(text: str, component_type: str) -> bool:
    return bool(
        re.search(r"\bcoc\b" if component_type == "pile" else r"\bdam\b", text)
    )


def _near_group_component(
    text: str, group: str, component_type: str
) -> bool:
    component = r"coc" if component_type == "pile" else r"dam"
    group_pattern = rf"nhom\s*{re.escape(group)}"
    return bool(
        re.search(
            rf"\b{component}\b.{{0,40}}\b{group_pattern}\b|"
            rf"\b{group_pattern}\b.{{0,40}}\b{component}\b",
            text,
        )
    )


def _section(record: _PageRecord) -> Optional[str]:
    text = " ".join([*record.titles, *record.summaries])
    match = _SECTION.search(text)
    return match.group(1) if match else None


def _status(record: _PageRecord) -> str:
    if record.has_verified and record.has_proposed:
        return "một phần đã xác minh"
    if record.has_verified:
        return "đã xác minh"
    if record.has_proposed:
        return "đề xuất, chưa xác minh"
    return "chưa có bản trích xuất"


def _display_title(
    record: _PageRecord, query: Optional[_NavigationQuery] = None
) -> str:
    if query is not None and record.titles:
        for title in record.titles:
            if _text_matches_query(title, query):
                return title
        if query.segment:
            for title in record.titles:
                if _has_segment(fold_text(title), query.segment):
                    return title
        if query.group:
            for title in record.titles:
                folded = fold_text(title)
                if "mat bang nhom coc" in folded and _has_group(
                    folded, query.group
                ):
                    return title
    if record.titles:
        return record.titles[0]
    return f"Trang {record.page.page_number}"


def _text_matches_query(text: str, query: _NavigationQuery) -> bool:
    folded = fold_text(text)
    if query.location and fold_text(query.location) not in folded:
        return False
    if query.segment and not _has_segment(folded, query.segment):
        return False
    if query.group and not _has_group(folded, query.group):
        return False
    if query.component_type and not _has_component(
        folded, query.component_type
    ):
        return False
    return True


def _matched_description(record: _PageRecord, query: _NavigationQuery) -> str:
    if query.method and (query.group or query.component_type):
        for fact in record.facts:
            if query.group and str(fact.get("group") or "") != query.group:
                continue
            if query.component_type and (
                str(fact.get("component_type") or "") != query.component_type
            ):
                continue
            description = " — ".join(
                part
                for part in (
                    str(fact.get("table_column") or "").strip(),
                    str(fact.get("quote") or fact.get("value") or "").strip(),
                )
                if part
            )
            if description:
                return description
    for summary in record.summaries:
        if _text_matches_query(summary, query):
            return summary
    for fact in record.facts:
        if query.group and str(fact.get("group") or "") != query.group:
            continue
        if query.component_type and (
            str(fact.get("component_type") or "") != query.component_type
        ):
            continue
        description = " — ".join(
            part
            for part in (
                str(fact.get("table_column") or "").strip(),
                str(fact.get("quote") or fact.get("value") or "").strip(),
            )
            if part
        )
        if description:
            return description
    return record.summaries[0] if record.summaries else ""


def _citation(record: _PageRecord, project_id: str) -> CitationOut:
    data = record.best_data or {}
    quote_parts = _unique([*record.titles, *record.summaries])
    if record.facts:
        quote_parts.append(
            " | ".join(
                f"{fact.get('component_code') or ''} "
                f"{fact.get('fact_name') or ''}: "
                f"{fact.get('value') or ''}".strip()
                for fact in record.facts[:3]
            )
        )
    quote = " | ".join(part for part in quote_parts if part)[:1200]
    return CitationOut(
        document_id=record.document.id,
        document_name=record.document.original_name,
        version=record.document.version,
        page_number=record.page.page_number,
        drawing_number=data.get("drawing_number") or record.page.drawing_number,
        revision=data.get("revision") or record.page.revision,
        quote=quote or f"Trang {record.page.page_number}",
        url=(
            f"/api/v1/projects/{project_id}/documents/"
            f"{record.document.id}/pages/{record.page.page_number}"
        ),
        page_id=record.page.id,
        section=_section(record),
    )


def _filter_label(query: _NavigationQuery) -> str:
    component = (
        "cọc" if query.component_type == "pile"
        else "dầm" if query.component_type == "beam"
        else ""
    )
    if query.method:
        head = "biện pháp thi công"
        if component:
            head += f" {component}"
        if query.group:
            head += f" nhóm {query.group}"
        extras = [
            part
            for part in (
                query.location,
                f"phân đoạn {query.segment}" if query.segment else "",
            )
            if part
        ]
        return ", ".join([head, *extras])
    parts: list[str] = ["trang thiết kế"]
    if component:
        parts.append(component)
    if query.location:
        parts.append(query.location)
    if query.segment:
        parts.append(f"phân đoạn {query.segment}")
    if query.group:
        parts.append(f"nhóm {query.group}")
    return ", ".join(parts) or "yêu cầu mở trang"


def _score(
    record: _PageRecord, query: _NavigationQuery, preferred_type: Optional[str]
) -> Optional[float]:
    if preferred_type and record.document.type != preferred_type:
        return None
    if query.page_number and record.page.page_number != query.page_number:
        return None
    if query.location and fold_text(query.location) not in record.all_text:
        return None
    if query.segment and not _has_segment(record.all_text, query.segment):
        return None
    if query.group and not _has_group(record.all_text, query.group):
        return None
    if query.component_type and not _has_component(
        record.all_text, query.component_type
    ):
        return None
    if query.method and not any(term in record.all_text for term in _METHOD_TERMS):
        return None
    if query.design and not any(term in record.all_text for term in _DESIGN_TERMS):
        return None

    title_and_summary = f"{record.title_text} {record.summary_text}"
    if query.method and query.group:
        fact_groups = {
            str(fact.get("group") or "").strip()
            for fact in record.facts
            if fact.get("group")
        }
        if fact_groups:
            if query.group not in fact_groups:
                return None
        else:
            if not _has_group(record.summary_text, query.group):
                return None
            if query.component_type and not _near_group_component(
                f"{record.title_text} {record.summary_text}",
                query.group,
                query.component_type,
            ):
                return None
    if query.method and query.component_type:
        fact_types = {
            str(fact.get("component_type") or "").strip()
            for fact in record.facts
            if fact.get("component_type")
        }
        if fact_types:
            if query.component_type not in fact_types:
                return None
        elif not _has_component(record.summary_text, query.component_type):
            return None
    score = 0.0
    if query.page_number:
        score += 100
    if preferred_type:
        score += 10
    if query.location:
        score += 12 if fold_text(query.location) in title_and_summary else 8
    if query.segment:
        score += 12 if _has_segment(title_and_summary, query.segment) else 8
    if query.group:
        score += 12 if _has_group(title_and_summary, query.group) else 8
    if query.component_type:
        score += 8 if _has_component(title_and_summary, query.component_type) else 4
    if query.method:
        score += 6
        if "bien phap thi cong" in title_and_summary:
            score += 6
        if "sua chua coc" in record.all_text:
            score += 4
    if query.design:
        score += 6
        if "mat bang" in title_and_summary:
            score += 6
        if "thiet ke" in title_and_summary:
            score += 4
    if record.has_verified:
        score += 3
    if record.has_proposed and not record.has_verified:
        score -= 1
    return score


def _is_sequence(records: list[_PageRecord]) -> bool:
    if len(records) < 2 or len({item.document.id for item in records}) != 1:
        return False
    numbers = sorted(item.page.page_number for item in records)
    return numbers == list(range(numbers[0], numbers[0] + len(numbers)))


def _line(record: _PageRecord, query: _NavigationQuery) -> str:
    title = _display_title(record, query)[:180]
    description = ""
    if query.method or not _text_matches_query(title, query):
        matched = _matched_description(record, query)
        if matched and matched not in title:
            description = f" — {matched[:220]}"
    return (
        f"- Trang {record.page.page_number} — {title}{description} "
        f"({record.document.original_name}, {_status(record)})"
    )


def answer_page_navigation(
    db: Session, project_id: str, message: str, scope: str
) -> Optional[PageNavigationResult]:
    query = parse_page_navigation_query(message)
    if query is None:
        return None
    preferred_type = (
        "specification" if query.method else "drawing" if query.design else None
    )
    candidates: list[_PageRecord] = []
    for record in _load_pages(db, project_id, scope):
        score = _score(record, query, preferred_type)
        if score is None:
            continue
        record.score = score
        candidates.append(record)
    candidates.sort(key=lambda item: (-item.score, item.page.page_number))
    if not candidates:
        return PageNavigationResult(
            answer=ProviderAnswer(text=NO_SOURCE_ANSWER),
            citations=[],
            warnings=[
                f"Không tìm thấy trang phù hợp với {_filter_label(query)} "
                "trong phạm vi hồ sơ đã chọn."
            ],
            no_source=True,
            confidence=0.0,
        )

    # Keep the strongest candidates; a sequence of consecutive pages in one
    # document (for example the two-page construction method) stays together.
    top_score = candidates[0].score
    if query.method and _is_sequence(candidates[:5]):
        selected = sorted(candidates[:5], key=lambda item: item.page.page_number)
    else:
        selected = [
            item for item in candidates[:5] if item.score >= top_score - 20
        ] or candidates[:1]
    if query.method and _is_sequence(selected):
        page_action = PageActionOut(
            document_id=selected[0].document.id,
            page_id=selected[0].page.id,
            page_number=selected[0].page.page_number,
            label=_display_title(selected[0], query)[:240],
        )
    elif len(selected) == 1:
        page_action = PageActionOut(
            document_id=selected[0].document.id,
            page_id=selected[0].page.id,
            page_number=selected[0].page.page_number,
            label=_display_title(selected[0], query)[:240],
        )
    else:
        page_action = None

    citations = [_citation(item, project_id) for item in selected]
    warnings: list[str] = []
    if query.method:
        warnings.append(
            "Nội dung biện pháp thi công nằm trong tài liệu thuyết minh, "
            "không có tài liệu riêng cùng tên."
        )
    for item in selected:
        if item.has_verified and item.has_proposed:
            warnings.append(
                f"Trang {item.page.page_number} có phần đã xác minh và phần "
                "còn là bản đề xuất."
            )
        elif item.has_proposed and not item.has_verified:
            warnings.append(
                f"Trang {item.page.page_number} chưa được kỹ sư xác minh."
            )
    if len(selected) > 1 and page_action is None:
        warnings.append(
            "Chưa tự mở trang vì có nhiều trang cùng khớp; cần nêu rõ nhóm "
            "cọc hoặc cọc/dầm."
        )

    if len(selected) == 1:
        record = selected[0]
        summary = _matched_description(record, query)
        lines = [
            f"Đã xác định trang nguồn: trang {record.page.page_number} — "
            f"{_display_title(record, query)}.",
            f"Tài liệu: {record.document.original_name}; trạng thái: {_status(record)}.",
        ]
        if summary:
            lines.append(summary[:600])
    elif page_action is not None and query.method:
        lines = [
            f"Trang nguồn cho {_filter_label(query)} bắt đầu tại trang "
            f"{selected[0].page.page_number}; "
            f"trang {selected[-1].page.page_number} là phần tiếp theo:"
        ]
        lines.extend(_line(item, query) for item in selected)
    else:
        lines = [
            f"Có {len(selected)} trang cùng khớp {_filter_label(query)}:"
        ]
        lines.extend(_line(item, query) for item in selected)
        lines.append(
            "Cần nêu rõ nhóm cọc (1/2/3) hoặc cọc/dầm để mở đúng trang."
        )
    return PageNavigationResult(
        answer=ProviderAnswer(text="\n".join(lines)),
        citations=citations,
        warnings=warnings,
        no_source=False,
        confidence=0.9 if len(selected) == 1 else 0.7 if page_action else 0.55,
        page_action=page_action,
    )
