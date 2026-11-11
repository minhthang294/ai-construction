"""Deterministic inspection-checklist suggestions from retrieved page text.

Suggestions are review prompts derived from a verbatim source quote.  They never
set ``yes``/approved, never claim an inspection was performed and never invent a
technical requirement that is absent from the cited page.
"""

from __future__ import annotations

from typing import Iterable, Optional, Tuple

from .crossref import sentence_texts
from .embeddings import tokenize

_INSPECTION_HINTS = (
    "kiểm tra", "nghiệm thu", "yêu cầu", "phải", "không được", "sai số",
    "dung sai", "cao độ", "kích thước", "chiều dày", "lớp bảo vệ", "cốt thép",
    "bê tông", "mác", "cấp", "mối nối", "hàn", "bu lông", "vật liệu", "độ dốc",
    "bề mặt", "thí nghiệm", "chứng chỉ", "tiêu chuẩn", "bản vẽ", "inspection",
    "tolerance", "shall", "must", "test", "certificate", "concrete", "cover",
    "reinforcement", "welding", "bolt", "material",
)


def _compact(value: str, limit: int = 220) -> str:
    text = " ".join(value.split())
    if len(text) <= limit:
        return text
    cut = text.rfind(" ", 0, limit)
    return text[: cut if cut > limit // 2 else limit].strip()


def choose_checklist_criterion(
    text: str,
    query_tokens: Iterable[str],
    fallback_quote: Optional[str] = None,
) -> Tuple[str, str]:
    """Return ``(verbatim_criterion, review_prompt)`` from the best sentence.

    Scoring is lexical and deterministic.  If no sentence is plausible, the
    retrieval quote is used unchanged; it is still a verbatim source excerpt.
    """

    query_set = set(query_tokens)
    best: Optional[Tuple[float, str]] = None
    for sentence in sentence_texts(text):
        folded = " ".join(sentence.casefold().split())
        hint_hits = sum(1 for hint in _INSPECTION_HINTS if hint in folded)
        overlap = len(query_set & set(tokenize(sentence)))
        if hint_hits == 0 and overlap == 0:
            continue
        score = hint_hits * 2.0 + overlap + min(len(sentence), 300) / 1000.0
        if best is None or score > best[0]:
            best = (score, sentence)
    criterion = best[1] if best else (fallback_quote or text).strip()
    if not criterion:
        criterion = ""
    prompt = f"Đối chiếu yêu cầu: {_compact(criterion)}" if criterion else "Đối chiếu hồ sơ liên quan."
    return criterion, prompt
