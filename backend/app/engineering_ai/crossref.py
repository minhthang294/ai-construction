"""Conservative cross-reference suggestions between two document pages.

The comparator flags only explicit, machine-visible numeric/grade differences in
sentences that share meaningful topic tokens.  It never decides which page is
correct, never says a design is wrong, and returns an empty suggestion list when
it cannot point to two concrete quotes.

This is intentionally deterministic so a suggestion can be audited against the
two citation quotes.  It is not a substitute for engineering review.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from .embeddings import fold_text, tokenize

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?;])\s+|\n+", re.UNICODE)
_RAW_TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)

# Explicit units / grades only.  Bare numbers (dates, drawing numbers, page
# numbers) are deliberately ignored to reduce false positives.
_VALUE_RE = re.compile(
    r"(?<![\w.])(\d{1,6}(?:[.,]\d+)?)\s*(mm|cm|m2|m²|m3|m³|kg|mpa|kn|%|độ|m)(?=\W|$)",
    re.IGNORECASE | re.UNICODE,
)
_GRADE_RE = re.compile(r"\bC(\d{2,3})\b", re.IGNORECASE)

_UNITS = {
    "mm", "cm", "m2", "m²", "m3", "m³", "kg", "mpa", "kn", "%", "độ", "do",
    "m", "grade", "cấp", "cap",
}
# ``tokenize`` already removes Vietnamese/English stopwords.  Domain words such
# as "concrete"/"cover"/"bảo vệ" must remain meaningful for topic matching.
_GENERIC: Set[str] = set()
_DISPLAY_UNIT = {"m2": "m²", "m3": "m³"}


@dataclass
class _Sentence:
    text: str
    tokens: Set[str]
    values: Set[Tuple[str, str]]
    display_by_token: Dict[str, str] = field(default_factory=dict)


@dataclass
class Discrepancy:
    topic: str
    first_quote: str
    second_quote: str
    observation: str
    confidence: float
    shared_tokens: List[str] = field(default_factory=list)


def sentence_texts(text: str) -> List[str]:
    output: List[str] = []
    for chunk in _SENTENCE_SPLIT_RE.split(text or ""):
        quote = chunk.strip()
        if len(quote) < 10:
            continue
        if len(quote) > 500:
            # Keep the quote verbatim; trim to a word boundary near 500 chars.
            head = quote[:500]
            boundary = head.rfind(" ")
            quote = head[:boundary].strip() if boundary > 100 else head
        output.append(quote)
        if len(output) >= 80:
            break
    return output


def _sentences(text: str) -> List[_Sentence]:
    rows: List[_Sentence] = []
    seen: Set[str] = set()
    for quote in sentence_texts(text):
        if not quote or quote in seen:
            continue
        seen.add(quote)
        folded_tokens = tokenize(quote)
        raw_display: Dict[str, str] = {}
        for raw in _RAW_TOKEN_RE.finditer(quote):
            folded = fold_text(raw.group(0))
            if folded and folded not in raw_display and folded not in _UNITS:
                raw_display[folded] = raw.group(0)
        meaningful = {
            token
            for token in folded_tokens
            if not token.isdigit()
            and token not in _UNITS
            and token not in _GENERIC
            and len(token) > 1
        }
        values = _values(quote)
        rows.append(
            _Sentence(
                text=quote,
                tokens=meaningful,
                values=values,
                display_by_token=raw_display,
            )
        )
        if len(rows) >= 80:
            break
    return rows


def _format_value(number: str, unit: str) -> str:
    if unit == "grade":
        return f"C{number}"
    display_unit = _DISPLAY_UNIT.get(unit, unit)
    return f"{number} {display_unit}".strip()


def _normalize_number(raw: str) -> str:
    value = raw.strip()
    if "," in value and "." in value:
        value = value.replace(".", "").replace(",", ".")
    elif "," in value:
        value = value.replace(",", ".")
    elif "." in value:
        left, right = value.split(".", 1)
        # Vietnamese drawings commonly use a dot as a thousands separator.  A
        # lone 0.x value remains decimal; other 3-digit groups are thousands.
        if left.isdigit() and left != "0" and len(right) == 3:
            value = left + right
        else:
            value = f"{left}.{right}"
    if "." in value:
        value = value.rstrip("0").rstrip(".")
    return value


def _values(sentence: str) -> Set[Tuple[str, str]]:
    values: Set[Tuple[str, str]] = set()
    for match in _VALUE_RE.finditer(sentence):
        number = _normalize_number(match.group(1))
        unit = match.group(2).lower().replace("m²", "m2").replace("m³", "m3")
        values.add((number or "0", unit))
    for match in _GRADE_RE.finditer(sentence):
        values.add((match.group(1), "grade"))
    return values


def _topic_label(shared: Set[str], first: _Sentence, requested: Optional[str]) -> str:
    if requested and requested.strip():
        return requested.strip()[:200]
    display = [
        first.display_by_token.get(token, token)
        for token in sorted(shared)
        if first.display_by_token.get(token, token) not in _GENERIC
    ][:6]
    return "Cùng nội dung: " + ", ".join(display) if display else "Nội dung cùng chủ đề"


def suggest_discrepancies(
    first_text: str,
    second_text: str,
    first_page_number: int,
    second_page_number: int,
    topic: Optional[str] = None,
) -> List[Discrepancy]:
    """Return review-only candidates, ordered by textual overlap.

    A candidate requires two verbatim sentences, at least two meaningful shared
    topic tokens, and at least one explicit unit/grade value on each side with
    different values.  If those conditions are not met, no suggestion is made.
    """

    first_sentences = _sentences(first_text)
    second_sentences = _sentences(second_text)
    requested = (topic or "").strip()
    requested_tokens = [token for token in tokenize(requested) if token not in _UNITS]
    requested_set = set(requested_tokens)

    candidates: List[tuple[float, Discrepancy]] = []
    seen: Set[Tuple[str, str]] = set()
    for first in first_sentences:
        if not first.values:
            continue
        for second in second_sentences:
            if not second.values:
                continue
            shared = first.tokens & second.tokens
            if len(shared) < 2:
                continue
            if requested_set and not (requested_set & shared):
                continue
            # Identical or overlapping values are not evidence of a difference.
            if first.values == second.values or (first.values & second.values):
                continue
            if (first.text, second.text) in seen:
                continue
            seen.add((first.text, second.text))

            overlap = len(shared) / max(1, min(len(first.tokens), len(second.tokens)))
            confidence = min(0.72, 0.35 + 0.08 * len(shared) + 0.10 * overlap)
            first_values = ", ".join(
                _format_value(number, unit) for number, unit in sorted(first.values)
            )
            second_values = ", ".join(
                _format_value(number, unit) for number, unit in sorted(second.values)
            )
            observation = (
                f"Trang {first_page_number} ghi {first_values}; trang "
                f"{second_page_number} ghi {second_values} trong ngữ cảnh có cùng "
                "chủ đề. Đây là điểm cần kỹ sư đối chiếu bản gốc; không kết luận "
                "trang nào đúng hay thiết kế sai."
            )
            candidate = Discrepancy(
                topic=_topic_label(shared, first, requested),
                first_quote=first.text,
                second_quote=second.text,
                observation=observation,
                confidence=round(confidence, 2),
                shared_tokens=sorted(shared)[:8],
            )
            candidates.append((confidence + 0.02 * len(shared), candidate))

    candidates.sort(key=lambda item: item[0], reverse=True)
    return [candidate for _, candidate in candidates[:5]]


def has_values(text: str) -> bool:
    return any(sentence.values for sentence in _sentences(text))
