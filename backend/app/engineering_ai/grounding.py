"""Grounding guards for provider-generated answers.

A provider may cite ``[1]`` correctly yet still invent a dimension.  This module
extracts explicit technical values (measurements, units, grades, diameters) from
the generated answer and compares them with the verbatim citation quotes.  If any
value is absent from the cited quotes, the caller must replace the answer with a
deterministic extractive answer.
"""

from __future__ import annotations

import re
from typing import Iterable, Set

# Longest units first so "kg/m3" is not partially read as "kg" + "m3".
_VALUE_RE = re.compile(
    r"(?<![\w.])(\d{1,6}(?:[.,]\d+)?)\s*"
    r"(kg/m3|kg/m³|kn/m2|kn/m²|n/mm2|n/mm²|mm|cm|m2|m²|m3|m³|kg|mpa|kn|%|độ|do|°|m|tấn|tan|t)"
    r"(?=\W|$)",
    re.IGNORECASE | re.UNICODE,
)
_GRADE_RE = re.compile(r"\bC(\d{2,3})\b", re.IGNORECASE)
_DIAMETER_RE = re.compile(r"[ØΦφ]\s*(\d{1,4})(?:\s*mm)?", re.IGNORECASE)
_CLASS_RE = re.compile(
    r"\b(?:cấp|cap|class|grade|loại|loai)\s*([IVX]{1,4})\b",
    re.IGNORECASE,
)

_UNIT_ALIASES = {
    "m²": "m2",
    "m³": "m3",
    "kg/m³": "kg/m3",
    "kn/m²": "kn/m2",
    "n/mm²": "n/mm2",
    "độ": "do",
    "tấn": "t",
    "tan": "t",
}


def _normalize_number(raw: str) -> str:
    value = raw.strip()
    if "," in value and "." in value:
        value = value.replace(".", "").replace(",", ".")
    elif "," in value:
        value = value.replace(",", ".")
    elif "." in value:
        left, right = value.split(".", 1)
        if left.isdigit() and left != "0" and len(right) == 3:
            value = left + right
    if "." in value:
        value = value.rstrip("0").rstrip(".")
    return value or "0"


def _normalize_unit(raw: str) -> str:
    value = raw.strip().lower().replace(" ", "")
    return _UNIT_ALIASES.get(value, value)


def extract_technical_values(text: str) -> Set[str]:
    """Return a normalized set of explicit technical values in ``text``.

    Examples: ``{"50|mm", "c30", "dia|12", "class|ii"}``.
    """

    values: Set[str] = set()
    for match in _VALUE_RE.finditer(text or ""):
        number = _normalize_number(match.group(1))
        unit = _normalize_unit(match.group(2))
        values.add(f"{number}|{unit}")
    for match in _GRADE_RE.finditer(text or ""):
        values.add(f"grade|c{match.group(1)}")
    for match in _DIAMETER_RE.finditer(text or ""):
        values.add(f"dia|{_normalize_number(match.group(1))}")
    for match in _CLASS_RE.finditer(text or ""):
        values.add(f"class|{match.group(1).lower()}")
    return values


def unsupported_technical_values(
    answer: str,
    cited_quotes: Iterable[str],
) -> Set[str]:
    """Return answer values not present in any cited quote."""

    allowed: Set[str] = set()
    for quote in cited_quotes:
        allowed |= extract_technical_values(quote)
    return extract_technical_values(answer) - allowed
