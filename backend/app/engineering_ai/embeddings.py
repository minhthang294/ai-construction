"""Accent-folded lexical helpers shared by page navigation and component chat.

No embedding provider is used: the module keeps only the deterministic text
normalisation needed to match Vietnamese accents and stopwords.
"""

from __future__ import annotations

import re
from typing import List

_TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)

_STOPWORDS = {
    "va", "và", "cua", "của", "cho", "cac", "các", "nhung", "những", "trong",
    "theo", "voi", "với", "la", "là", "co", "có", "duoc", "được", "khong",
    "không", "mot", "một", "tai", "tại", "tu", "từ", "den", "đến", "ve", "về",
    "thi", "thì", "nay", "này", "do", "đó", "de", "để", "khi", "vao", "vào",
    "ra", "tren", "trên", "duoi", "dưới", "giua", "giữa", "the", "and", "or",
    "of", "to", "in", "for", "with", "is", "are", "be", "as", "at", "by",
}


def fold_text(value: str) -> str:
    """Lowercase and strip Vietnamese diacritics for lexical matching."""

    import unicodedata

    text = unicodedata.normalize("NFD", (value or "").lower())
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return text.replace("đ", "d")


def tokenize(value: str) -> List[str]:
    return [tok for tok in _TOKEN_RE.findall(fold_text(value)) if tok not in _STOPWORDS]
