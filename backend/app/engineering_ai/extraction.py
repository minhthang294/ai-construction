"""Per-page PDF extraction with scan-render + OCR fallback.

Digital pages use the embedded text layer.  Pages whose text layer is empty or
implausibly sparse are rendered to PNG and passed to the injected OCR engine.
Nothing is guessed: if OCR is unavailable or fails, the page keeps empty text,
a warning and ``needs_review=True``.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from .ocr import OcrEngine, clean_ocr_text
from . import storage


class ExtractionError(RuntimeError):
    """The PDF cannot be opened, is encrypted, or exceeds configured limits."""


_DRAWING_PATTERNS = (
    re.compile(
        r"(?:B[ảa]n\s*v[ẽe]|DRAWING|DWG|B\.V\.|BV)\s*(?:NO\.?|SỐ|SO|#|:|-)"
        r"\s*([A-Z0-9][A-Z0-9._/\-]{2,48})",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:DRAWING\s*(?:NO|NUMBER)|SỐ\s*BẢN\s*VẼ)\s*[:\-]?\s*([A-Z0-9][A-Z0-9._/\-]{2,48})",
        re.IGNORECASE,
    ),
)
_REVISION_PATTERNS = (
    re.compile(
        r"(?:REV(?:ISION)?|HIỆU\s*CHỈNH|HIEU\s*CHINH)\s*[.:#\-]?\s*([A-Z0-9]{1,12})",
        re.IGNORECASE,
    ),
)


def _normalize_metadata(value: str) -> str:
    return value.strip().strip(".,;:").upper()


def parse_drawing_number(text: str) -> Optional[str]:
    for pattern in _DRAWING_PATTERNS:
        match = pattern.search(text or "")
        if match:
            value = _normalize_metadata(match.group(1))
            if len(value) >= 3:
                return value[:120]
    return None


def parse_revision(text: str) -> Optional[str]:
    for pattern in _REVISION_PATTERNS:
        match = pattern.search(text or "")
        if match:
            value = _normalize_metadata(match.group(1))
            if value:
                return value[:60]
    return None


@dataclass
class PageExtraction:
    page_number: int
    text: str
    ocr_text: Optional[str]
    ocr_confidence: Optional[float]
    extraction_method: str
    rendered_path: Optional[str]
    drawing_number: Optional[str]
    revision: Optional[str]
    width: Optional[float]
    height: Optional[float]
    needs_review: bool = False
    warnings: List[str] = field(default_factory=list)
    tables: List[dict] = field(default_factory=list)


@dataclass
class DocumentExtraction:
    page_count: int
    pages: List[PageExtraction] = field(default_factory=list)
    drawing_number: Optional[str] = None
    revision: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    ocr_languages: Optional[str] = None


def _min_native_chars() -> int:
    return int(os.getenv("ENGINEERING_AI_MIN_NATIVE_TEXT", "60"))


def _render_dpi() -> int:
    return max(72, int(os.getenv("ENGINEERING_AI_RENDER_DPI", "200")))


def _open_pdf(path: Path):
    try:
        import pymupdf  # type: ignore
    except Exception:  # pragma: no cover - older PyMuPDF
        import fitz as pymupdf  # type: ignore

    try:
        document = pymupdf.open(str(path))
    except Exception as exc:  # noqa: BLE001
        raise ExtractionError("PDF không mở được.") from exc
    if getattr(document, "needs_pass", False) or getattr(document, "is_encrypted", False):
        document.close()
        raise ExtractionError("PDF được bảo vệ bằng mật khẩu.")
    return pymupdf, document


def _render_page(pymupdf, page, dpi: int) -> bytes:
    zoom = dpi / 72.0
    pixmap = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False, colorspace=pymupdf.csRGB)
    return pixmap.tobytes("png")


def extract_document(
    path: Path,
    project_id: str,
    document_id: str,
    ocr_engine: OcrEngine,
    languages: str,
    max_pages: int,
) -> DocumentExtraction:
    if not path.exists() or not path.is_file():
        raise ExtractionError("Tệp PDF gốc không tồn tại trong kho private.")
    pymupdf, document = _open_pdf(path)
    try:
        if document.page_count < 1:
            raise ExtractionError("PDF không có trang nào.")
        if document.page_count > max_pages:
            raise ExtractionError(f"PDF vượt quá giới hạn {max_pages} trang.")
        result = DocumentExtraction(page_count=document.page_count, ocr_languages=languages)
        threshold = _min_native_chars()
        dpi = _render_dpi()
        for index in range(document.page_count):
            page = document.load_page(index)
            page_number = index + 1
            warnings: List[str] = []
            native_text = ""
            try:
                native_text = clean_ocr_text(page.get_text("text") or "")
            except Exception:  # noqa: BLE001
                warnings.append("Không đọc được lớp text của trang; đã thử OCR.")

            rect = page.rect
            width, height = float(rect.width), float(rect.height)
            tables: List[dict] = []
            try:
                finder = page.find_tables()
                for table in getattr(finder, "tables", []) or []:
                    rows = table.extract() or []
                    tables.append(
                        {
                            "bbox": [round(float(value), 2) for value in table.bbox],
                            "row_count": len(rows),
                            "col_count": max((len(row) for row in rows), default=0),
                            "rows": [
                                [None if cell is None else str(cell) for cell in row]
                                for row in rows[:500]
                            ],
                        }
                    )
            except Exception:  # noqa: BLE001 - native table extraction is best-effort
                tables = []

            image_count = 0
            try:
                image_count = len(page.get_images(full=True))
            except Exception:  # noqa: BLE001
                image_count = 0

            needs_ocr = len(native_text) < threshold or (
                image_count > 0 and len(native_text) < threshold * 4
            )
            ocr_text: Optional[str] = None
            ocr_confidence: Optional[float] = None
            rendered_path: Optional[str] = None
            method = "text" if native_text else "none"
            final_text = native_text

            if needs_ocr:
                try:
                    png = _render_page(pymupdf, page, dpi)
                    target = storage.page_render_path(project_id, document_id, page_number)
                    storage.write_render(target, png)
                    rendered_path = str(target)
                    ocr_result = ocr_engine.extract_text(png, languages)
                    ocr_text = clean_ocr_text(ocr_result.text)
                    ocr_confidence = ocr_result.confidence
                    warnings.extend(ocr_result.warnings)
                    if ocr_text and (not native_text or len(ocr_text) > len(native_text)):
                        final_text = ocr_text
                        method = "ocr"
                    elif native_text:
                        method = "text"
                except Exception:  # noqa: BLE001
                    warnings.append("Render/OCR trang thất bại; cần kiểm tra bản vẽ gốc.")

            if not final_text:
                method = "none"
                warnings.append("Trang không có text trích xuất được; cần kiểm tra trực tiếp.")
            needs_review = method == "none" or (
                ocr_confidence is not None and ocr_confidence < 0.60
            )
            drawing_number = parse_drawing_number(final_text)
            revision = parse_revision(final_text)
            if result.drawing_number is None and drawing_number:
                result.drawing_number = drawing_number
            if result.revision is None and revision:
                result.revision = revision
            result.pages.append(
                PageExtraction(
                    page_number=page_number,
                    text=final_text,
                    ocr_text=ocr_text if method == "ocr" else None,
                    ocr_confidence=ocr_confidence if method == "ocr" else None,
                    extraction_method=method,
                    rendered_path=rendered_path,
                    drawing_number=drawing_number,
                    revision=revision,
                    width=width,
                    height=height,
                    needs_review=needs_review,
                    warnings=warnings,
                    tables=tables,
                )
            )
        result.warnings = [
            f"Trang {page.page_number}: {warning}"
            for page in result.pages
            for warning in page.warnings
        ]
        return result
    finally:
        document.close()
