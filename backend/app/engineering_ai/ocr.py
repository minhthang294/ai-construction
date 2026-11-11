"""OCR fallback for scanned PDF pages.

The OCR engine is an injectable protocol so tests never depend on a system
binary.  The default engine shells out to Tesseract, which is optional; when it
is missing the page is marked for manual review instead of inventing text.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Protocol


@dataclass
class OcrResult:
    text: str
    confidence: Optional[float] = None
    engine: str = "none"
    warnings: List[str] = field(default_factory=list)


class OcrEngine(Protocol):
    name: str

    def extract_text(self, image_bytes: bytes, languages: str) -> OcrResult:
        ...


class NullOcrEngine:
    """Explicit no-OCR fallback: never fabricates page text."""

    name = "none"

    def extract_text(self, image_bytes: bytes, languages: str) -> OcrResult:
        return OcrResult(
            text="",
            confidence=None,
            engine=self.name,
            warnings=[
                "Không có OCR engine khả dụng; trang scan cần được kiểm tra trực tiếp."
            ],
        )


class TesseractOcrEngine:
    name = "tesseract"

    def __init__(self, command: Optional[str] = None, timeout: float = 90.0) -> None:
        self.command = command or os.getenv("ENGINEERING_AI_OCR_CMD", "tesseract")
        self.timeout = timeout

    def _run(self, image_path: str, languages: str) -> tuple[int, str, str]:
        proc = subprocess.run(
            [self.command, image_path, "stdout", "-l", languages, "--psm", "3", "tsv"],
            capture_output=True,
            timeout=self.timeout,
            check=False,
        )
        return proc.returncode, proc.stdout.decode("utf-8", "replace"), proc.stderr.decode("utf-8", "replace")

    @staticmethod
    def _parse_tsv(tsv: str) -> OcrResult:
        lines: dict[tuple[int, int, int], list[str]] = {}
        confidences: list[float] = []
        for row in tsv.splitlines()[1:]:
            columns = row.split("\t")
            if len(columns) < 12:
                continue
            try:
                conf = float(columns[10])
                key = (int(columns[2]), int(columns[3]), int(columns[4]))
            except ValueError:
                continue
            word = columns[11].strip()
            if not word or conf < 0:
                continue
            confidences.append(conf / 100.0)
            lines.setdefault(key, []).append(word)
        text = "\n".join(" ".join(words) for _, words in sorted(lines.items())).strip()
        confidence = round(sum(confidences) / len(confidences), 4) if confidences else None
        return OcrResult(
            text=text,
            confidence=confidence,
            engine="tesseract",
            warnings=[] if text else ["OCR không nhận được văn bản từ trang scan."],
        )

    def extract_text(self, image_bytes: bytes, languages: str) -> OcrResult:
        if shutil.which(self.command) is None and not Path(self.command).exists():
            return NullOcrEngine().extract_text(image_bytes, languages)
        temp_dir = Path(
            tempfile.mkdtemp(
                prefix="eng-ai-ocr-",
                dir="/tmp/opencode" if Path("/tmp/opencode").is_dir() else None,
            )
        )
        image_path = temp_dir / "page.png"
        try:
            image_path.write_bytes(image_bytes)
            warnings: List[str] = []
            returncode, stdout, stderr = self._run(str(image_path), languages)
            if returncode != 0 and "vie" in languages:
                # A Vietnamese traineddata pack may be absent.  Retry with the
                # installed base language rather than losing the page entirely.
                warnings.append(
                    "Không nạp được gói ngôn ngữ OCR tiếng Việt; đã thử lại với eng."
                )
                returncode, stdout, stderr = self._run(str(image_path), "eng")
            if returncode != 0:
                return OcrResult(
                    text="",
                    confidence=None,
                    engine=self.name,
                    warnings=[
                        "OCR lỗi; trang cần được kiểm tra trực tiếp bản vẽ gốc."
                    ],
                )
            result = self._parse_tsv(stdout)
            if warnings:
                result.warnings.extend(warnings)
            if stderr and not result.text:
                result.warnings.append("OCR không trả về nội dung.")
            return result
        except (OSError, subprocess.SubprocessError):
            return OcrResult(
                text="",
                confidence=None,
                engine=self.name,
                warnings=["OCR lỗi; trang cần được kiểm tra trực tiếp bản vẽ gốc."],
            )
        finally:
            try:
                image_path.unlink(missing_ok=True)
            except OSError:
                pass
            try:
                temp_dir.rmdir()
            except OSError:
                pass


_TYPO_SPACE = re.compile(r"[ \t]+")


def clean_ocr_text(text: str) -> str:
    value = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    value = "\n".join(_TYPO_SPACE.sub(" ", line).strip() for line in value.split("\n"))
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def ocr_engine_from_env() -> OcrEngine:
    name = (os.getenv("ENGINEERING_AI_OCR_ENGINE") or "tesseract").strip().lower()
    if name in {"none", "null", "off", "disabled"}:
        return NullOcrEngine()
    return TesseractOcrEngine()


def ocr_languages_from_env() -> str:
    return (os.getenv("ENGINEERING_AI_OCR_LANGUAGES") or "vie+eng").strip()
