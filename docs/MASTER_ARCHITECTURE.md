# Kiến trúc tổng thể

Cập nhật: 24/11/2026. Ứng dụng hiện tại; không còn V1.

## Nền tảng

- Backend FastAPI + SQLAlchemy 2 + Alembic + SQLite. Frontend React/TypeScript/Vite/Tailwind, PWA mobile-first.
- Một DB, một migration chain. File gốc/ảnh render nằm ở storage private; DB chỉ giữ metadata, hash và đường dẫn.
- `project_id` là phạm vi mọi entity/API. Audit log ghi actor, project, entity, action, thời gian và JSON chi tiết.
- Vai trò: `admin`, `project_manager`, `engineer`, `viewer`. AI chỉ đề xuất; nghiệm thu do người có quyền xác nhận.
- Thời gian lưu UTC; hiển thị/ngày báo cáo theo `Asia/Ho_Chi_Minh`.

## System A — Engineering AI

- Không upload/ingest trong ứng dụng. Hồ sơ nguồn, trang và kết quả AI trích xuất được nạp offline bằng script có kiểm tra (`scripts/import_page_extractions.py`).
- Chat trả lời trên `engineering_ai_page_extractions` đã lưu + DB cấu kiện/tiến độ. Mỗi câu trả lời có citation `document_id`, `page_number`, `quote`; thiếu nguồn trả câu từ chối chuẩn.
- Provider LLM tùy chọn (OpenCode DeepSeek qua biến môi trường server). Lỗi provider thì fallback trích xuất trực tiếp, vẫn giữ citation.
- `POST /ai/progress-parse` là parser tất định cho tin nhắn Zalo: ngày, dòng công tác, mã cấu kiện, công đoạn gợi ý, cảnh báo/câu hỏi; không gọi LLM, không ghi DB. UI chỉ ghi tiến độ sau khi người dùng duyệt.
- Conversation CRUD; `q` chỉ lọc tiêu đề hội thoại, không phải tìm kiếm tài liệu.
- Đã bỏ 23-24/11/2026: upload/ingest tài liệu, OCR/Tesseract, embedding/sqlite-vec ingest, tìm kiếm tài liệu, cross-reference, checklist tài liệu độc lập, AI report-draft và AI gợi ý caption ảnh. Checklist 7 mục trong BBNT vẫn còn; caption ảnh do người dùng nhập/xác nhận.

## System B — Acceptance

- PYC/BBNT sinh tất định từ DB + template Excel; không gọi LLM/Vision/Embedding.
- Hàng chờ nghiệm thu lấy từ cấu kiện/công đoạn đã hoàn thành; tạo PYC nháp từ cấu kiện; BBNT tái sử dụng PYC.
- BBNT có checklist 7 mục tri-state, numbering PYC/BBNT, revision/stale, preview và export Excel/PDF.
- Liên kết nghiệm thu là tường minh qua `component_acceptance_links`; không suy ra nghiệm thu từ tiến độ.
- Import lịch sử PYC/BBNT từ workbook: `scripts/import_acceptance_workbook.py` (preview mặc định, `--commit`, idempotent, không sửa workbook).

## Site và core

- Báo cáo ngày, manpower/preset, work log, next-day plan; ảnh công trường + liên kết cấu kiện/work item; export Zalo/PDF/DOCX/ZIP.
- Tiến độ append-only; nhập hàng loạt/theo ngày; void/correct; gắn `batch_id`.
- Đợt thi công (`construction_batches`) nhóm cấu kiện thi công cùng đợt, không đổi zone/segment thiết kế.
- Cấu kiện: zone/segment, alias, repair scope, bước thi công, design parameters (`t`, `L1`…), vị trí bản đồ. Bản đồ nhiều sheet đọc từ `data/storage/dap-maps/<key>/manifest.json`.
- Overview: `latest-day`, `in-progress`, `segments`; chỉ đọc dữ liệu thật, không suy ra nghiệm thu.

## Phân luồng

`Project → WorkItem → DailyReport/SitePhoto/ProgressEvent → AcceptanceRequest → AcceptanceRecord`.

`SourceDocument → DocumentPage → PageExtraction → AICitation`.

`ConstructionBatch → components`; `ComponentMapPosition` gắn cấu kiện với sheet công khai.

## An toàn

Không dùng dữ liệu demo làm bản ghi thật. Không tự xác nhận nghiệm thu, GPS, kích thước hoặc khối lượng từ ảnh/AI. Thiếu nguồn trả đúng câu từ chối. Template Excel chỉ đọc và sao chép khi xuất. Không tự động gửi Zalo.
