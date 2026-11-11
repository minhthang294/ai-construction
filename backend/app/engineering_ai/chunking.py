"""Page text chunking with exact character offsets for citations.

Chunks never cross a detected heading/section boundary.  Offsets remain relative
to the original page text so citation quotes can be verified as substrings.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional

DEFAULT_CHUNK_SIZE = 1400
DEFAULT_OVERLAP = 200
_BOUNDARY = ("\n\n", "\n", ". ", "; ", ", ")
_NUMBERED_HEADING = re.compile(
    r"^\s*(?:CHƯƠNG|PHẦN|MỤC|ĐIỀU|CHAPTER|SECTION|PART|\d+(?:\.\d+)*|[IVX]+)"
    r"[.)]?\s+\S",
    re.IGNORECASE,
)
_KEYWORD_HEADING = re.compile(
    r"^\s*(?:CHƯƠNG|PHẦN|MỤC|ĐIỀU|CHAPTER|SECTION|PART)\b",
    re.IGNORECASE,
)


@dataclass
class TextChunk:
    index: int
    text: str
    start_offset: int
    end_offset: int
    section: Optional[str] = None


def _find_break(text: str, start: int, target: int) -> int:
    minimum = start + int((target - start) * 0.55)
    best = -1
    for marker in _BOUNDARY:
        position = text.rfind(marker, minimum, target)
        if position > best:
            best = position + len(marker)
    return best if best > start else target


def chunk_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_OVERLAP,
) -> List[TextChunk]:
    if not text or not text.strip():
        return []
    if chunk_size < 100:
        raise ValueError("chunk_size must be >= 100")
    overlap = max(0, min(overlap, chunk_size // 2))
    chunks: List[TextChunk] = []
    start = 0
    length = len(text)
    while start < length:
        while start < length and text[start].isspace():
            start += 1
        if start >= length:
            break
        target = min(length, start + chunk_size)
        end = target if target >= length else _find_break(text, start, target)
        while end > start and text[end - 1].isspace():
            end -= 1
        # A short page/section (for example an OCR label under 20 characters)
        # must still produce one searchable chunk; otherwise it is invisible to
        # retrieval even though the page text exists.
        if end - start >= 20 or (not chunks and end - start >= 3):
            chunks.append(
                TextChunk(
                    index=len(chunks),
                    text=text[start:end],
                    start_offset=start,
                    end_offset=end,
                )
            )
        if end >= length:
            break
        next_start = end - overlap
        start = next_start if next_start > start else end
    return chunks


def _is_heading(line: str) -> bool:
    value = line.strip()
    if not (3 <= len(value) <= 160):
        return False
    if value.startswith(("...", "…")) or "...." in value:
        return False
    if _KEYWORD_HEADING.match(value):
        return True
    # Numbered headings such as "2.1. Vật liệu" or "III. Thi công".
    if _NUMBERED_HEADING.match(value):
        return True
    letters = [ch for ch in value if ch.isalpha()]
    if len(letters) < 3:
        return False
    upper_ratio = sum(1 for ch in letters if ch.isupper()) / len(letters)
    return upper_ratio >= 0.85 and not value.endswith((",", ";"))


def _section_ranges(text: str) -> List[tuple[Optional[str], int, int]]:
    lines = text.splitlines(keepends=True)
    headings = []
    position = 0
    for line in lines:
        if _is_heading(line):
            headings.append((position, line.strip()[:255]))
        position += len(line)
    if not headings:
        return [(None, 0, len(text))]
    ranges: List[tuple[Optional[str], int, int]] = []
    if headings[0][0] > 0:
        ranges.append((None, 0, headings[0][0]))
    for index, (start, title) in enumerate(headings):
        end = headings[index + 1][0] if index + 1 < len(headings) else len(text)
        ranges.append((title, start, end))
    return ranges


def chunk_text_with_sections(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_OVERLAP,
) -> List[TextChunk]:
    """Chunk within detected sections, never across heading boundaries."""

    if not text or not text.strip():
        return []
    output: List[TextChunk] = []
    for section, start, end in _section_ranges(text):
        piece = text[start:end]
        for chunk in chunk_text(piece, chunk_size=chunk_size, overlap=overlap):
            output.append(
                TextChunk(
                    index=len(output),
                    text=chunk.text,
                    start_offset=start + chunk.start_offset,
                    end_offset=start + chunk.end_offset,
                    section=section,
                )
            )
    return output
