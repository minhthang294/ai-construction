"""Shared constants for the Engineering AI module.

The refusal and low-confidence sentences are fixed by
``docs/AI_ARCHITECTURE.md`` and must be returned verbatim.
"""

from __future__ import annotations

NO_SOURCE_ANSWER = "Không tìm thấy thông tin này trong hồ sơ công trình hiện có."
LOW_OCR_WARNING = "Thông tin chưa đủ độ tin cậy, cần kiểm tra trực tiếp bản vẽ gốc."
LOW_OCR_THRESHOLD = 0.60
GROUNDING_WARNING = (
    "Câu trả lời của provider chứa giá trị kỹ thuật không có trong citation; "
    "đã thay bằng trích dẫn trực tiếp."
)

# The AI knowledge base is not verified while no source drawings/reports exist.
UNVERIFIED_KB_NOTE = (
    "Kho tri thức AI theo hồ sơ công trình chưa được kiểm chứng; "
    "câu trả lời chỉ dựa trên dữ kiện AI trích xuất và citation tương ứng."
)
