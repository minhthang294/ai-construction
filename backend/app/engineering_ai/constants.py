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

DOCUMENT_STATUSES = ("pending", "running", "ready", "failed")
DOCUMENT_TYPES = (
    "drawing",
    "specification",
    "technical_guideline",
    "construction_method",
    "standard",
    "material_record",
    "test_record",
    "acceptance_record",
    "instruction",
    "report",
    "other",
)

# The AI knowledge base is not verified while no source drawings/reports exist.
UNVERIFIED_KB_NOTE = (
    "Kho tri thức AI theo hồ sơ công trình chưa được kiểm chứng; "
    "câu trả lời chỉ dựa trên trang hồ sơ đã tải lên và citation tương ứng."
)

VISION_DISCLAIMER = (
    "Đây là đề xuất của AI, chưa phải chứng cứ. Kỹ sư phải kiểm tra và xác nhận "
    "loại ảnh/caption trước khi dùng trong báo cáo hoặc hồ sơ nghiệm thu."
)

CROSS_REFERENCE_DISCLAIMER = (
    "Đây chỉ là điểm nghi vấn cần kỹ sư đối chiếu bản gốc; không kết luận bản vẽ "
    "hay thuyết minh sai, không thay thế thẩm tra thiết kế."
)
CROSS_REFERENCE_NO_FINDING = (
    "Không phát hiện khác biệt văn bản rõ ràng giữa hai trang; không kết luận "
    "hồ sơ đồng nhất, đã được duyệt hoặc đúng thiết kế."
)

DAILY_REPORT_DRAFT_DISCLAIMER = (
    "Bản nháp này chỉ sao chép dữ liệu nhân lực, công việc và kế hoạch đã được ghi "
    "trong báo cáo nguồn. Không tự tạo số lượng, khối lượng, thời gian hay nội dung "
    "còn thiếu; các trường thiếu được liệt kê để người dùng bổ sung."
)
DAILY_REPORT_DRAFT_WARNING = (
    "Bản nháp hỗ trợ không thay thế báo cáo đã được người có quyền xem xét."
)

INSPECTION_CHECKLIST_DISCLAIMER = (
    "Đây chỉ là gợi ý mục kiểm tra được trích từ trang hồ sơ. Không tự đặt trạng thái "
    "yes/đạt, không tự xác nhận nghiệm thu và không thay thế kiểm tra hiện trường."
)

VERSION_COMPARE_DISCLAIMER = (
    "So sánh chỉ gồm metadata và thống kê trang/chunk. Không kết luận thay đổi thiết kế, "
    "không xác định bản nào đúng; kỹ sư phải đọc bản gốc."
)

VISION_CHAT_DISCLAIMER = (
    "Vision chỉ nhận một trang render của chunk top-1 và chỉ đề xuất nội dung cần xem; "
    "không phải kết luận kỹ thuật, không thay thế citation hoặc kiểm tra bản gốc."
)

