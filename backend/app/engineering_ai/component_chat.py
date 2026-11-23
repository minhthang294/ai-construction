"""Verified component-fact answers for the chat path.

Only rows marked ``verified`` on ready, effective documents are used.  Queries
are deliberately narrow: an exact pile/beam code or a component type + segment.
Missing evidence is refused instead of falling back to generic page retrieval.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import component_search
from .beam_table_lookup import find_proposed_beam_table_facts
from .beam_plan_lookup import find_proposed_beam_plan
from .pile_table_lookup import find_proposed_pile_measurements
from .pile_group_lookup import (
    PileGroupEntry,
    find_proposed_pile_group,
    find_proposed_pile_locations,
)
from .component_search import ComponentFactMatch
from .constants import NO_SOURCE_ANSWER
from .embeddings import fold_text
from .models import DocumentPage, SourceDocument
from .providers import ProviderAnswer
from .quantity_calc import (
    Dimension,
    QuantityCalculationError,
    rectangular_area,
    rectangular_volume,
)
from .schemas import CitationOut


def _page_url(project_id: str, document_id: str, page_number: int) -> str:
    return f"/api/v1/projects/{project_id}/documents/{document_id}/pages/{page_number}"


def _get_page(
    db: Session, project_id: str, document_id: str, page_number: int
) -> Optional[DocumentPage]:
    return db.scalar(
        select(DocumentPage).where(
            DocumentPage.project_id == project_id,
            DocumentPage.document_id == document_id,
            DocumentPage.page_number == page_number,
        )
    )


@dataclass(frozen=True)
class _ComponentQuery:
    code: Optional[str] = None
    location: Optional[str] = None
    segment: Optional[str] = None
    group: Optional[str] = None
    component_type: Optional[str] = None
    missing_code: bool = False


_COMPONENT_LOCATIONS = (("cau chinh", "Cầu chính"), ("cau dan", "Cầu dẫn"))
_COMPONENT_CODE_RE = re.compile(r"(?<![\w-])([a-z]{1,3}(?:-?\d{1,4}){1,3})(?![\w-])")
_BEAM_CODE_RE = re.compile(r"(?<![\w-])([a-z]-[a-z]\.\d{1,4})(?![\w-])")
_COMPONENT_QUESTION_RE = re.compile(
    r"bao nhieu|chieu|do sau|duc|dien tich|the tich|khoi luong|"
    r"hu hong|hong|nut|sua chua|thong tin|du lieu|quy trinh"
)
_DIMENSION_ROLES = (
    ("length", ("chieu dai", "do dai")),
    ("width", ("chieu rong", "do rong")),
    ("depth", ("chieu sau", "do sau", "chieu day", "do day")),
)
_WORK_TERMS = ("duc", "quet", "keo", "mai", "phang", "dan", "soi", "cat", "tram", "son")


def _small_number(value: str) -> str:
    text = (value or "").strip().lower()
    if text.isdigit():
        return str(int(text))
    return {"i": "1", "ii": "2", "iii": "3", "iv": "4", "v": "5", "mot": "1", "hai": "2", "ba": "3"}.get(text, text)


def parse_component_query(message: str) -> Optional[_ComponentQuery]:
    text = fold_text(message)
    beam_code = _BEAM_CODE_RE.search(text) if re.search(r"\b(?:dam|beam)\b", text) else None
    code = beam_code.group(1) if beam_code else None
    for match in _COMPONENT_CODE_RE.finditer(text):
        if code:
            break
        token = match.group(1)
        before = text[max(0, match.start() - 24) : match.start()]
        if re.search(r"(?:be tong|mac|cap|grade|rev|tcvn|qcvn)\s*$", before):
            continue
        if re.fullmatch(r"[tl]\d{1,2}", token) and re.search(
            r"\b(?:coc|dam|pile|beam)\b", text
        ):
            continue
        code = token
        break
    component_type = None
    if re.search(r"\b(?:coc|pile)\b", text):
        component_type = "pile"
    elif re.search(r"\b(?:dam|beam)\b", text):
        component_type = "beam"
    location = next(
        (display for folded, display in _COMPONENT_LOCATIONS if folded in text),
        None,
    )
    segment = re.search(
        r"\b(?:phan\s*doan|pd|doan)\s*([0-9]{1,3}|mot|hai|ba|i{1,3}|iv|v)\b", text
    )
    group = re.search(r"\bnhom\s*([0-9]{1,3}|mot|hai|ba|i{1,3}|iv|v)\b", text)
    values = dict(
        location=location,
        segment=_small_number(segment.group(1)) if segment else None,
        group=_small_number(group.group(1)) if group else None,
        component_type=component_type,
    )
    if code:
        return _ComponentQuery(code=code, **values)
    if (values["segment"] or values["group"]) and component_type:
        return _ComponentQuery(**values)
    if re.search(r"\b(?:coc|dam|pile|beam)\s+(?:nay|do|kia|this)\b", text) and (
        _COMPONENT_QUESTION_RE.search(text)
    ):
        return _ComponentQuery(component_type=component_type, missing_code=True)
    return None


def _normalise_fact(value: object) -> str:
    return fold_text(str(value or "")).strip()


def _segment_number(value: object) -> str | None:
    match = re.search(r"\d+", _normalise_fact(value))
    return str(int(match.group())) if match else None


def _place_label(place: tuple[str, str]) -> str:
    return ", ".join(part for part in place if part)


def _requested_quantities(message: str) -> List[tuple[str, str, str]]:
    text = fold_text(message)
    if "khoi luong" in text and re.search(r"\bduc\b", text):
        return [("volume", "the tich", "thể tích đục")]
    return [
        item
        for item in (
            ("mass", "khoi luong", "khối lượng"),
            ("volume", "the tich", "thể tích"),
            ("area", "dien tich", "diện tích"),
        )
        if item[1] in text
    ]


def _work_terms(message: str) -> set[str]:
    text = fold_text(message)
    return {
        term for term in _WORK_TERMS if re.search(rf"\b{re.escape(term)}\b", text)
    }


def _detail_terms(message: str) -> tuple[str, ...]:
    text = fold_text(message)
    if re.search(r"quy trinh|trinh tu|bien phap", text):
        return ("quy trinh", "trinh tu", "bien phap")
    if re.search(r"chieu sau|do sau|duc sau", text):
        return ("chieu sau duc", "do sau duc", "duc sau")
    if "vet nut" in text and re.search(r"chieu dai|do dai", text):
        return ("chieu dai vet nut", "do dai vet nut")
    if re.search(r"chieu dai|do dai", text):
        return ("chieu dai", "do dai")
    return ()


def _display_group(fact: dict) -> str:
    raw = str(fact.get("group") or "").strip()
    match = re.search(r"\d+", fold_text(raw))
    return f"Nhóm {int(match.group())}" if match else raw or "Không ghi nhóm"


def _display_segment(value: str) -> str:
    value = value.strip()
    match = re.fullmatch(r"(?:pd|pđ)\s*(\d+)", fold_text(value))
    if match:
        return f"Phân đoạn {int(match.group(1))}"
    return f"Phân đoạn {value}" if value and not fold_text(value).startswith("phan doan") else value


def _fact_marker(index: dict[tuple[str, int], int], match: ComponentFactMatch) -> str:
    number = index.get((match.document_id, match.page_number))
    return f"[{number}]" if number else ""


def _component_citations(
    db: Session, project_id: str, matches: List[ComponentFactMatch]
) -> Tuple[List[CitationOut], dict[tuple[str, int], int]]:
    pages: dict[tuple[str, int], List[ComponentFactMatch]] = {}
    for match in matches:
        pages.setdefault((match.document_id, match.page_number), []).append(match)
    citations: List[CitationOut] = []
    index: dict[tuple[str, int], int] = {}
    for (document_id, page_number), page_matches in pages.items():
        document = db.get(SourceDocument, document_id)
        page = _get_page(db, project_id, document_id, page_number)
        quotes = " | ".join(
            dict.fromkeys(
                str(match.fact.get("quote") or "").strip()
                for match in page_matches
                if str(match.fact.get("quote") or "").strip()
            )
        )
        citations.append(
            CitationOut(
                document_id=document_id,
                document_name=(
                    document.original_name if document else page_matches[0].document_name
                ),
                version=document.version if document else 1,
                page_number=page_number,
                drawing_number=page_matches[0].drawing_number,
                revision=page_matches[0].revision,
                quote=quotes[:1200],
                url=_page_url(project_id, document_id, page_number),
                ocr_confidence=(
                    page.ocr_confidence
                    if page is not None and page.extraction_method == "ocr"
                    else None
                ),
                page_id=page.id if page else None,
                extraction_method=page.extraction_method if page else None,
            )
        )
        index[(document_id, page_number)] = len(citations)
    return citations, index


def _dimension_value(value: object) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value or "").strip().replace(" ", "")
    if not re.fullmatch(r"\d{1,12}(?:[.,]\d+)?", text):
        return None
    for separator in (".", ","):
        if separator not in text:
            continue
        left, right = text.split(separator, 1)
        # "1.280" / "1,280" may be a decimal or a thousands-grouped integer.
        # Do not guess; require an explicit canonical value instead.
        if len(right) == 3 and left.lstrip("0"):
            return None
        break
    return float(text.replace(",", "."))


def _compute_quantity(
    kind: str,
    matches: List[ComponentFactMatch],
    index: dict[tuple[str, int], int],
) -> Optional[str]:
    if kind not in {"area", "volume"}:
        return None
    roles: dict[str, ComponentFactMatch] = {}
    for match in matches:
        name = _normalise_fact(match.fact.get("fact_name"))
        role = next(
            (role for role, needles in _DIMENSION_ROLES if any(n in name for n in needles)),
            None,
        )
        if role:
            if role in roles:
                return None
            roles[role] = match
    required = ("length", "width") if kind == "area" else (
        "length", "width", "depth",
    )
    if any(role not in roles for role in required):
        return None
    chosen = [roles[role] for role in required]
    if len(
        {
            (
                _normalise_fact(match.fact.get("group")),
                _normalise_fact(match.fact.get("segment")),
                _normalise_fact(match.fact.get("location")),
            )
            for match in chosen
        }
    ) != 1:
        return None
    dimensions = []
    for match in chosen:
        fact = match.fact
        number = _dimension_value(fact.get("value"))
        unit = str(fact.get("unit") or "").strip().lower()
        code = str(fact.get("component_code") or "").strip()
        if number is None or not unit or not code:
            return None
        dimensions.append(
            Dimension(
                value=number,
                unit=unit,
                component_code=code,
                citation=f"{match.document_name} trang {match.page_number}",
                revision=match.revision,
            )
        )
    try:
        result = (
            rectangular_area(*dimensions)
            if kind == "area"
            else rectangular_volume(*dimensions)
        )
    except QuantityCalculationError:
        return None
    markers = " ".join(dict.fromkeys(_fact_marker(index, match) for match in chosen))
    label = "Diện tích" if kind == "area" else "Thể tích"
    return (
        f"- {label} (hệ thống tính): {result.formula}; "
        f"{result.substituted_formula} {markers}"
    ).rstrip()


def _beam_fiber_area_check(
    matches: List[ComponentFactMatch], index: dict[tuple[str, int], int]
) -> Optional[str]:
    panels = ("T1", "T2", "T3")
    parts = []
    total = 0
    for panel in panels:
        def one(prefix: str) -> Optional[ComponentFactMatch]:
            found = [
                match for match in matches
                if _normalise_fact(match.fact.get("fact_name")).startswith(
                    f"{prefix} {panel.lower()}"
                )
            ]
            return found[0] if len(found) == 1 else None

        length = one("chieu dai tam")
        width = one("chieu rong tam")
        count = one("so tam")
        if not all((length, width, count)):
            return None
        number = _dimension_value(count.fact.get("value"))
        if number is None or not number.is_integer() or number <= 0:
            return None
        dimensions = []
        for match in (length, width):
            value = _dimension_value(match.fact.get("value"))
            if value is None:
                return None
            dimensions.append(Dimension(
                value=value,
                unit=str(match.fact.get("unit") or ""),
                component_code=str(match.fact.get("component_code") or ""),
                citation=f"{match.document_name} trang {match.page_number}",
                revision=match.revision,
            ))
        try:
            area = rectangular_area(*dimensions).value
        except QuantityCalculationError:
            return None
        total += area * int(number)
        parts.append(
            f"{panel} ({dimensions[0].value} m × {dimensions[1].value} m × {int(number)})"
        )
    marker = _fact_marker(index, matches[0])
    return (
        "- Diện tích dán sợi (hệ thống tính): "
        f"A = Σ(L × W × số tấm) = {' + '.join(parts)} = {total} m² {marker}"
    )


def _format_component_details(
    query: _ComponentQuery,
    matches: List[ComponentFactMatch],
    message: str,
    index: dict[tuple[str, int], int],
) -> Tuple[str, List[str]]:
    code = str(query.code or matches[0].fact.get("component_code") or "").upper()
    label = {"pile": "cọc", "beam": "dầm"}.get(query.component_type, "cấu kiện")
    lines = [f"Dữ kiện đã đối chiếu với trang hồ sơ cho {label} {code}:"]
    for match in matches:
        fact = match.fact
        name = str(fact.get("fact_name") or "").strip()
        value = str(fact.get("value") or "").strip()
        unit = str(fact.get("unit") or "").strip()
        if not name or not value:
            continue
        context = " / ".join(
            part
            for part in (
                _display_group(fact) if fact.get("group") else "",
                str(fact.get("segment") or "").strip(),
                str(fact.get("location") or "").strip(),
            )
            if part
        )
        line = f"- {name}: {value}{f' {unit}' if unit else ''}"
        line += f" ({context})" if context else ""
        evidence = (
            "đối chiếu các bảng trong hồ sơ"
            if fact.get("evidence_kind") == "joined"
            else "hồ sơ ghi sẵn (trực tiếp)"
        )
        line += f" — {evidence} {_fact_marker(index, match)}"
        lines.append(line.rstrip())
    warnings: List[str] = []
    for kind, word, label in _requested_quantities(message):
        if any(word in _normalise_fact(match.fact.get("fact_name")) for match in matches):
            continue
        computed = _compute_quantity(kind, matches, index)
        if computed:
            lines.append(computed)
            warnings.append(
                "Giá trị tính được tách khỏi dữ kiện hồ sơ ghi sẵn; "
                "cần kiểm tra công thức và kích thước nguồn."
            )
        else:
            lines.append(
                f"Chưa đủ dữ kiện đã xác minh để trả lời {label}; "
                "không tự suy ra từ một kích thước hoặc quy trình chung."
            )
    if query.component_type == "beam" and "dien tich" in fold_text(message) and "dan soi" in fold_text(message):
        computed = _beam_fiber_area_check(matches, index)
        if computed:
            lines.append(computed)
    return "\n".join(lines), warnings


def _format_component_groups(
    query: _ComponentQuery,
    matches: List[ComponentFactMatch],
    index: dict[tuple[str, int], int],
) -> str:
    groups: dict[tuple[str, str], List[ComponentFactMatch]] = {}
    for match in matches:
        groups.setdefault(
            (str(match.fact.get("location") or "Không rõ vị trí").strip(), _display_group(match.fact)),
            [],
        ).append(match)
    header = (
        f"Dữ kiện đã đối chiếu với trang hồ sơ cho {query.location or 'hồ sơ'}, "
        f"phân đoạn {query.segment}"
    )
    if query.group:
        header += f", nhóm {query.group}"
    lines = [header + ":"]
    codes_all = set()
    for (location, group), group_matches in sorted(
        groups.items(),
        key=lambda item: (
            item[0],
        ),
    ):
        codes = list(
            dict.fromkeys(
                str(match.fact.get("component_code") or "").strip()
                for match in group_matches
                if str(match.fact.get("component_code") or "").strip()
            )
        )
        codes_all.update((location, code) for code in codes)
        markers = list(
            dict.fromkeys(
                marker
                for marker in (_fact_marker(index, match) for match in group_matches)
                if marker
            )
        )
        if codes:
            lines.append(
                f"- {location + ', ' if not query.location else ''}{group}: "
                f"{len(codes)} cấu kiện — {', '.join(codes)} "
                + " ".join(markers)
            )
    if len({location for location, _ in groups}) > 1 and not query.location:
        lines.append("Câu hỏi không nêu vị trí nên đã nêu riêng từng vị trí đã xác minh.")
    if len({group for _, group in groups}) > 1 and not query.group:
        lines.append(
            "Câu hỏi không nêu nhóm nên đã nêu các nhóm đã xác minh; "
            "không tự chọn một nhóm."
        )
    lines.append(f"Đã xác minh: {len(codes_all)} cấu kiện trong {len(groups)} nhóm.")
    lines.append(
        "Danh sách chỉ gồm dữ kiện đã xác minh và có thể chưa đầy đủ."
    )
    return "\n".join(line.rstrip() for line in lines)


def answer_component_query(
    db: Session,
    project_id: str,
    message: str,
    query: _ComponentQuery,
    scope: str,
) -> Tuple[ProviderAnswer, List[CitationOut], List[str], bool, float]:
    if query.missing_code:
        return (
            ProviderAnswer(
                text=(
                    "Cần mã cọc/dầm cụ thể (ví dụ H77) để tra dữ kiện đã xác minh; "
                    "không tự chọn cấu kiện."
                )
            ),
            [],
            ["Câu hỏi dùng “cọc/dầm này” nhưng không có mã; không tự chọn cấu kiện."],
            True,
            0.0,
        )

    folded_message = fold_text(message)
    location_question = bool(query.code and query.component_type == "pile" and re.search(
        r"\b(?:nhom may|thuoc nhom|nhom nao|o dau|vi tri|phan doan nao|thuoc phan doan|mat bang)\b",
        folded_message,
    ) and not re.search(r"\b(?:do sau|duc sau|chieu dai|dien tich|the tich|khoi luong|quy trinh)\b", folded_message))
    if location_question:
        verified = component_search.find_component_facts(
            db, project_id, component_code=query.code, location=query.location,
            segment=query.segment, group=query.group, scope=scope,
        )
        verified = [m for m in verified if _normalise_fact(m.fact.get("component_type")) == "pile"]
        if verified:
            places = {(str(m.fact.get("group") or "").strip(),
                       str(m.fact.get("segment") or "").strip(),
                       str(m.fact.get("location") or "").strip()) for m in verified}
            if len(places) == 1:
                group, segment, location = places.pop()
                citations, index = _component_citations(db, project_id, verified[:1])
                parts = [part for part in (_display_group({"group": group}) if group else "",
                                           _display_segment(segment), location) if part]
                warning = "Trang nguồn chưa ghi rõ vị trí cọc." if not location else None
                answer = f"Cọc {query.code.upper()}: {', '.join(parts)} {_fact_marker(index, verified[0])}".strip()
                return (ProviderAnswer(text=answer), citations,
                        [warning] if warning else [], False, 0.83)
            return (ProviderAnswer(text=NO_SOURCE_ANSWER), [],
                    ["Hồ sơ đã xác minh ghi nhiều vị trí/nhóm cho cùng mã cọc; cần đối chiếu bản vẽ."], True, 0.0)
        proposed = [
            (group, entry) for group, entry in find_proposed_pile_locations(
                db, project_id, query.code, scope=scope,
            )
            if (not query.group or group == query.group)
            and (not query.location or _normalise_fact(entry.location) == _normalise_fact(query.location))
            and (not query.segment or re.search(r"\d+", _normalise_fact(entry.segment))
                 and str(int(re.search(r"\d+", _normalise_fact(entry.segment)).group())) == query.segment)
        ]
        places = {(group, entry.segment or "", entry.location or "") for group, entry in proposed}
        if len(places) == 1:
            group, segment, location = places.pop()
            matches = [ComponentFactMatch(
                fact={"quote": f"Nhóm {group} | {entry.code} | {entry.segment or ''} | {entry.location or ''}"},
                document_id=entry.document_id, document_name="", page_number=entry.page_number,
                drawing_number=None, revision=None, table_row=entry.table_row,
                table_column="Tên cọc", url=entry.url,
            ) for _, entry in proposed]
            citations, index = _component_citations(db, project_id, matches)
            markers = " ".join(dict.fromkeys(_fact_marker(index, m) for m in matches))
            warning = "Vị trí/nhóm do AI trích xuất từ mặt bằng, chưa được kỹ sư xác minh."
            parts = [part for part in (f"Nhóm {group}", _display_segment(segment), location) if part]
            location_warning = "Trang nguồn chưa ghi rõ vị trí cọc." if not location else None
            return (ProviderAnswer(text=f"Cọc {query.code.upper()}: {', '.join(parts)} {markers}\n{warning}".strip()),
                    citations, [warning, location_warning] if location_warning else [warning], False, 0.4)
        if proposed:
            return (ProviderAnswer(text=NO_SOURCE_ANSWER), [],
                    ["Mặt bằng AI trích xuất ghi nhiều vị trí/nhóm cho cùng mã cọc; cần đối chiếu trang gốc."], True, 0.0)
        return (ProviderAnswer(text=NO_SOURCE_ANSWER), [],
                ["Không tìm thấy mã cọc trên mặt bằng nhóm cọc thuộc phạm vi hồ sơ đã chọn."], True, 0.0)

    beam_location_question = bool(query.code and query.component_type == "beam" and re.search(
        r"\b(?:nhom may|thuoc nhom|nhom nao|o dau|vi tri|phan doan nao|thuoc phan doan|mat bang)\b",
        folded_message,
    ) and not re.search(r"\b(?:do sau|duc sau|chieu dai|dien tich|the tich|khoi luong|quy trinh)\b", folded_message))
    if beam_location_question:
        verified = component_search.find_component_facts(
            db, project_id, component_code=query.code, location=query.location,
            segment=query.segment, group=query.group, scope=scope,
        )
        verified = [m for m in verified if _normalise_fact(m.fact.get("component_type")) == "beam"]
        if verified:
            places = {(str(m.fact.get("group") or "").strip(),
                       str(m.fact.get("segment") or "").strip(),
                       str(m.fact.get("location") or "").strip()) for m in verified}
            if len(places) == 1:
                group, segment, location = places.pop()
                citations, index = _component_citations(db, project_id, verified[:1])
                parts = [part for part in (_display_group({"group": group}) if group else "",
                                           _display_segment(segment), location) if part]
                return (ProviderAnswer(text=f"Dầm {query.code.upper()}: {', '.join(parts)} {_fact_marker(index, verified[0])}".strip()),
                        citations, [], False, 0.83)
            return (ProviderAnswer(text=NO_SOURCE_ANSWER), [],
                    ["Hồ sơ đã xác minh ghi nhiều vị trí/nhóm cho cùng mã dầm."], True, 0.0)
        proposed = [entry for entry in find_proposed_beam_plan(db, project_id, query.code, scope)
                    if (not query.group or entry.group == query.group)
                    and (not query.segment or re.search(r"\d+", entry.segment or "")
                         and str(int(re.search(r"\d+", entry.segment or "").group())) == query.segment)
                    and (not query.location or _normalise_fact(entry.location) == _normalise_fact(query.location))]
        places = {(entry.group, entry.segment, entry.location, entry.beam_type) for entry in proposed}
        if len(places) == 1:
            group, segment, location, beam_type = places.pop()
            matches = [ComponentFactMatch(
                fact={"quote": f"{entry.code} | Nhóm {entry.group} | {entry.segment} | {entry.beam_type or ''}"},
                document_id=entry.document_id, document_name="", page_number=entry.page_number,
                drawing_number=None, revision=None, table_row=entry.table_row,
                table_column="Ký hiệu dầm", url=entry.url,
            ) for entry in proposed]
            citations, index = _component_citations(db, project_id, matches)
            markers = " ".join(dict.fromkeys(_fact_marker(index, match) for match in matches))
            parts = [part for part in (f"Nhóm {group}", _display_segment(segment), location, beam_type) if part]
            warning = "Vị trí/nhóm do AI trích xuất từ mặt bằng, chưa được kỹ sư xác minh."
            return (ProviderAnswer(text=f"Dầm {query.code.upper()}: {', '.join(parts)} {markers}\n{warning}".strip()),
                    citations, [warning], False, 0.4)
        if proposed:
            return (ProviderAnswer(text=NO_SOURCE_ANSWER), [],
                    ["Mặt bằng AI trích xuất ghi nhiều vị trí/nhóm cho cùng mã dầm."], True, 0.0)
        return (ProviderAnswer(text=NO_SOURCE_ANSWER), [],
                ["Chưa xác định được vị trí dầm theo mã trên mặt bằng đã trích xuất."], True, 0.0)

    if not query.code and query.component_type == "pile" and query.group:
        verified_group = component_search.find_component_facts(
            db, project_id, location=query.location, segment=query.segment,
            group=query.group, scope=scope,
        )
        verified_group = [m for m in verified_group
                          if _normalise_fact(m.fact.get("component_type")) == "pile"]
        group_result = find_proposed_pile_group(
            db, project_id, query.group, location=query.location,
            segment=query.segment, scope=scope,
        )
        if verified_group or any(not entry.ambiguous for entry in group_result.entries):
            group_matches: List[ComponentFactMatch] = []
            verified_by_place: dict[tuple[str, str], list[str]] = {}
            proposed_by_place: dict[tuple[str, str], list[str]] = {}
            verified_codes: set[str] = set()
            verified_pages: set[tuple[str, int]] = set()
            verified_segments_by_page: dict[tuple[str, int], set[str]] = {}
            for match in verified_group:
                fact = match.fact
                code = str(fact.get("component_code") or "").strip().upper()
                if not re.fullmatch(r"[A-Z]\d{1,3}", code):
                    continue
                place = (
                    str(fact.get("location") or "").strip() or "Không rõ vị trí",
                    _display_segment(str(fact.get("segment") or ""))
                    or "Không rõ phân đoạn",
                )
                verified_by_place.setdefault(place, []).append(code)
                verified_codes.add(code)
                verified_pages.add((match.document_id, match.page_number))
                segment_number = _segment_number(fact.get("segment"))
                if segment_number:
                    verified_segments_by_page.setdefault(
                        (match.document_id, match.page_number), set()
                    ).add(segment_number)
                group_matches.append(match)

            proposed_entries: dict[str, PileGroupEntry] = {}
            proposed_places: dict[str, tuple[str, str]] = {}
            ambiguous_codes: set[str] = set()
            notes: List[str] = []
            for entry in group_result.entries:
                code = entry.code.strip().upper()
                if (
                    entry.ambiguous
                    or code in ambiguous_codes
                    or not re.fullmatch(r"[A-Z]\d{1,3}", code)
                ):
                    continue
                page_key = (entry.document_id, entry.page_number)
                if page_key in verified_pages:
                    # A verified reading already covers this table. Only a row
                    # anchored to a different known segment can add to it.
                    segments = verified_segments_by_page.get(page_key, set())
                    entry_segment = _segment_number(entry.segment)
                    if not segments or entry_segment is None or entry_segment in segments:
                        continue
                place = (
                    entry.location or "Không rõ vị trí",
                    _display_segment(entry.segment or "") or "Không rõ phân đoạn",
                )
                if code in verified_codes:
                    alternatives = [
                        candidate
                        for candidate, codes in verified_by_place.items()
                        if code in codes
                    ]
                    if alternatives and place not in alternatives:
                        notes.append(
                            f"Mã {code} đã xác minh ở {_place_label(alternatives[0])}; "
                            f"bản đề xuất ghi {_place_label(place)} nên không cộng vào danh sách."
                        )
                    continue
                previous = proposed_entries.get(code)
                if previous is not None:
                    previous_place = proposed_places[code]
                    previous_segment = _segment_number(previous.segment)
                    entry_segment = _segment_number(entry.segment)
                    if previous_place == place:
                        continue
                    if previous_place[0] == place[0] and (
                        previous_segment is None or entry_segment is None
                    ):
                        # Prefer the row that carries a known segment.
                        if entry_segment and not previous_segment:
                            proposed_entries[code] = entry
                            proposed_places[code] = place
                        continue
                    ambiguous_codes.add(code)
                    proposed_entries.pop(code, None)
                    proposed_places.pop(code, None)
                    continue
                proposed_entries[code] = entry
                proposed_places[code] = place
            for code in ambiguous_codes:
                proposed_entries.pop(code, None)
                proposed_places.pop(code, None)
            for code, entry in proposed_entries.items():
                place = proposed_places[code]
                proposed_by_place.setdefault(place, []).append(code)
                group_matches.append(
                    ComponentFactMatch(
                        fact={
                            "component_code": code,
                            "fact_name": "cọc trong nhóm",
                            "quote": entry.quote
                            or f"{code} | {_place_label(place)}",
                            "group": entry.group or query.group,
                            "segment": entry.segment,
                            "location": entry.location,
                        },
                        document_id=entry.document_id,
                        document_name="",
                        page_number=entry.page_number,
                        drawing_number=entry.drawing_number,
                        revision=entry.revision,
                        table_row=entry.table_row,
                        table_column="Tên cọc",
                        url=entry.url,
                    )
                )
            citations, index = _component_citations(db, project_id, group_matches)
            proposed_codes = set(proposed_entries)
            lines: List[str] = []
            if verified_codes and proposed_codes:
                lines.append(
                    f"Kết quả gồm {len(verified_codes)} mã đã xác minh và "
                    f"{len(proposed_codes)} mã AI trích xuất chưa xác minh; "
                    "chưa phải tổng chính thức:"
                )
            elif verified_codes:
                lines.append(f"Kết quả gồm {len(verified_codes)} mã đã xác minh:")
            elif proposed_codes:
                lines.append(
                    f"Chưa có mã nào đã xác minh; {len(proposed_codes)} mã cọc "
                    "rõ ràng do AI trích xuất, chưa xác minh "
                    "(chưa phải tổng số cọc chính thức):"
                )
            else:
                detail = (
                    ": " + ", ".join(sorted(ambiguous_codes))
                    if ambiguous_codes
                    else ""
                )
                return (
                    ProviderAnswer(text=NO_SOURCE_ANSWER),
                    [],
                    [
                        "Chỉ có mã cọc mơ hồ hoặc trùng vị trí"
                        f"{detail}; không tự chọn mã."
                    ],
                    True,
                    0.0,
                )
            count_only = "bao nhieu" in fold_text(message) and "nhung coc nao" not in fold_text(message)
            for source_label, places in (
                ("Đã xác minh", verified_by_place),
                ("AI trích xuất, chưa xác minh", proposed_by_place),
            ):
                for (location, segment), raw_codes in sorted(places.items()):
                    codes = list(dict.fromkeys(raw_codes))
                    marker = " ".join(
                        dict.fromkeys(
                            _fact_marker(index, match)
                            for match in group_matches
                            if match.fact.get("component_code") in codes
                        )
                    )
                    detail = "" if count_only else f": {', '.join(codes)}"
                    group_label = f", {_display_group({'group': query.group})}"
                    lines.append(
                        f"- {source_label} — {location}, {segment}{group_label} "
                        f"({len(codes)} cọc){detail} {marker}".rstrip()
                    )
            warning = (
                "Các mã chưa xác minh do AI trích xuất; cần đối chiếu mặt bằng "
                "gốc trước khi dùng."
            )
            if proposed_codes:
                lines.append(warning)
            for note in notes:
                lines.append(note)
            source_notes = [
                note
                for note in group_result.warnings
                if "lặp trong cùng bảng" not in note
            ]
            if source_notes:
                lines.append(
                    "Lưu ý khi đọc bảng: " + "; ".join(source_notes[:8])
                )
            if ambiguous_codes:
                lines.append(
                    "Mã bị loại do xuất hiện ở nhiều vị trí/phân đoạn: "
                    + ", ".join(sorted(ambiguous_codes))
                )
            extra_warnings = (
                ([warning] if proposed_codes else []) + notes + source_notes
            )
            return (
                ProviderAnswer(text="\n".join(lines)),
                citations,
                extra_warnings,
                False,
                0.45 if proposed_codes else 0.8,
            )

    def table_answer(verified: List[ComponentFactMatch]):
        if not query.code or query.component_type not in {"pile", "beam"}:
            return None
        if query.component_type == "pile":
            candidates = find_proposed_pile_measurements(db, project_id, query.code, scope)
        else:
            candidates = find_proposed_beam_table_facts(db, project_id, query.code, scope)
        if query.location:
            candidates = [m for m in candidates if _normalise_fact(m.fact.get("location")) == _normalise_fact(query.location)]
        if query.group:
            candidates = [m for m in candidates if _normalise_fact(m.fact.get("group")) in {query.group, f"nhom {query.group}"}]
        if query.segment:
            candidates = [m for m in candidates if re.search(r"\d+", _normalise_fact(m.fact.get("segment"))) and str(int(re.search(r"\d+", _normalise_fact(m.fact.get("segment"))).group())) == query.segment]
        folded = fold_text(message)
        if re.search(r"\b(?:duc sau|do sau|chieu sau)\b", folded):
            wanted = lambda name: "chieu sau duc" in name
        elif "vet nut" in folded and "chieu dai" in folded:
            wanted = lambda name: "chieu dai vet nut" in name
        elif re.search(r"\bl[1-4]\b", folded):
            label = re.search(r"\bl[1-4]\b", folded).group()
            wanted = lambda name: name == label
        elif _requested_quantities(message):
            quantities = _requested_quantities(message)
            work = _work_terms(message)
            wanted = lambda name: any(term in name for _, term, _ in quantities) and all(term in name for term in work)
        elif re.search(r"thong tin|kich thuoc|bao nhieu|chi tiet", folded):
            wanted = lambda name: True
        else:
            return None
        selected = [m for m in candidates if wanted(_normalise_fact(m.fact.get("fact_name")))]
        selected = [m for m in selected if not any(
            _normalise_fact(v.fact.get("fact_name")) == _normalise_fact(m.fact.get("fact_name"))
            or ("chieu dai vet nut" in _normalise_fact(m.fact.get("fact_name"))
                and "chieu dai vet nut" in _normalise_fact(v.fact.get("fact_name")))
            for v in verified
        )]
        if not selected:
            return None
        values = {}
        for match in selected:
            key = _normalise_fact(match.fact.get("fact_name"))
            values.setdefault(key, set()).add(str(match.fact.get("value")).replace(",", "."))
        if any(len(item) > 1 for item in values.values()):
            return (ProviderAnswer(text=NO_SOURCE_ANSWER), [],
                    ["Bảng đề xuất có số đo mâu thuẫn cho cùng mã; cần đối chiếu trang gốc."], True, 0.0)
        seen = set()
        unique_selected = []
        for match in selected:
            key = (_normalise_fact(match.fact.get("fact_name")),
                   str(match.fact.get("value")).replace(",", "."))
            if key not in seen:
                seen.add(key)
                unique_selected.append(match)
        selected = unique_selected
        citations, index = _component_citations(db, project_id, selected)
        label = "cọc" if query.component_type == "pile" else "dầm"
        lines = [f"Bảng hồ sơ ghi cho {label} {query.code.upper()}:"]
        for match in selected:
            fact = match.fact
            lines.append(f"- {fact['fact_name']}: {fact['value']} {fact['unit']} {_fact_marker(index, match)}")
        warning = "Số liệu do AI trích xuất từ bảng, chưa được kỹ sư xác minh; cần đối chiếu bản vẽ gốc trước khi dùng thi công."
        lines.append(warning)
        return ProviderAnswer(text="\n".join(lines)), citations, [warning], False, 0.45

    matches = component_search.find_component_facts(
        db,
        project_id,
        component_code=query.code,
        location=query.location,
        segment=query.segment,
        group=query.group,
        scope=scope,
    )
    if query.component_type:
        matches = [
            match
            for match in matches
            if _normalise_fact(match.fact.get("component_type")) == query.component_type
        ]
    proposed = table_answer(matches)
    if proposed is not None:
        return proposed
    if not matches:
        return (
            ProviderAnswer(text=NO_SOURCE_ANSWER),
            [],
            [
                "Chưa có dữ kiện cấu kiện đã được xác minh trong hồ sơ hiệu lực "
                "cho truy vấn này; không dùng đề xuất trích xuất chưa xác minh."
            ],
            True,
            0.0,
        )
    unique: List[ComponentFactMatch] = []
    seen = set()
    for match in matches:
        key = (
            match.document_id,
            match.page_number,
            json.dumps(match.fact, sort_keys=True, ensure_ascii=False, default=str),
        )
        if key not in seen:
            seen.add(key)
            unique.append(match)
    unique.sort(
        key=lambda match: (
            _normalise_fact(match.fact.get("group")),
            _normalise_fact(match.fact.get("component_code")),
            _normalise_fact(match.fact.get("fact_name")),
            match.page_number,
        )
    )
    work_terms = _work_terms(message)
    detail_terms = _detail_terms(message)
    membership: Optional[ComponentFactMatch] = None
    if query.code and "quy trinh" in detail_terms and unique:
        groups = {
            re.search(r"\d+", str(match.fact.get("group") or "")).group()
            for match in unique
            if re.search(r"\d+", str(match.fact.get("group") or ""))
        }
        component_types = {match.fact.get("component_type") for match in unique}
        locations = {_normalise_fact(match.fact.get("location")) for match in unique}
        if (
            len(groups) == len(component_types) == len(locations) == 1
            and component_types <= {"pile", "beam"}
            and "" not in locations
        ):
            group = groups.pop()
            component_type = component_types.pop()
            group_code = f"{component_type.upper()}-GROUP-{group}"
            process = component_search.find_component_facts(
                db, project_id, component_code=group_code, scope=scope
            )
            process = [
                match for match in process
                if _normalise_fact(match.fact.get("location")) in locations
                and _normalise_fact(match.fact.get("group")) in {group, f"nhom {group}"}
                and _normalise_fact(match.fact.get("fact_name")).startswith("quy trinh")
            ]
            if process:
                membership = unique[0]
                unique = process
    if query.code and detail_terms and not _requested_quantities(message):
        unique = [
            match for match in unique
            if any(term in _normalise_fact(match.fact.get("fact_name")) for term in detail_terms)
        ]
        if not unique:
            return (
                ProviderAnswer(text=NO_SOURCE_ANSWER), [],
                ["Chưa có dữ kiện đã xác minh cho đúng thông tin được hỏi."],
                True, 0.0,
            )
    if query.code and work_terms and _requested_quantities(message):
        relevant = [
            match
            for match in unique
            if all(
                term in _normalise_fact(match.fact.get("fact_name"))
                for term in work_terms
            )
            or (
                {"dan", "soi"}.issubset(work_terms)
                and _normalise_fact(match.fact.get("fact_name")).startswith("so tam")
            )
        ]
        if not relevant:
            return (
                ProviderAnswer(text=NO_SOURCE_ANSWER),
                [],
                [
                    "Không có dữ kiện đã xác minh cho đúng công tác được hỏi; "
                    "không dùng dữ kiện của công tác khác."
                ],
                True,
                0.0,
            )
        unique = relevant
    revisions = sorted(
        {
            str(match.revision).strip()
            for match in unique
            if match.revision and str(match.revision).strip()
        }
    )
    if len(revisions) > 1:
        return (
            ProviderAnswer(text=NO_SOURCE_ANSWER),
            [],
            ["Không trộn dữ kiện khác revision: " + ", ".join(revisions) + "."],
            True,
            0.0,
        )
    citations, index = _component_citations(
        db, project_id, unique + ([membership] if membership else [])
    )
    if query.code:
        text, warnings = _format_component_details(query, unique, message, index)
        if membership:
            text += (
                f"\nÁp dụng theo phân loại nhóm của {query.code.upper()} "
                f"trên bản vẽ {_fact_marker(index, membership)}."
            )
    else:
        text = _format_component_groups(query, unique, index)
        warnings = []
    return (
        ProviderAnswer(text=text),
        citations,
        warnings,
        False,
        round(min(0.95, 0.8 + 0.03 * len(citations)), 2),
    )
