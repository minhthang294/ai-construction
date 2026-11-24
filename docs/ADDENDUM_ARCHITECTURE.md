# Kiến trúc bổ sung — trạng thái 24/11/2026

Tài liệu này thay thế phần “vòng 2” cũ. Nguồn sự thật là code trong `backend/app` và route thực tế.

## 1. Hai hệ thống

- **System A — Engineering AI**: chat trên dữ liệu trang do AI trích xuất và DB cấu kiện/tiến độ; citation theo trang; conversation CRUD; provider tùy chọn.
- **System B — Acceptance**: PYC/BBNT tất định từ DB + template Excel; không gọi LLM, Vision hay Embedding. Checklist BBNT vẫn là dữ liệu nghiệm thu do người dùng nhập.

## 2. AI chat

- Nguồn: `engineering_ai_documents`, `engineering_ai_document_pages`, `engineering_ai_page_extractions` và DB cấu kiện/tiến độ.
- Không upload/ingest trong app, không OCR/Tesseract, không embedding/sqlite-vec ingest, không tìm kiếm tài liệu, không cross-reference.
- Câu trả lời phải có citation `document_id`, `page_number`, `quote`. Thiếu nguồn trả: “Không tìm thấy thông tin này trong hồ sơ công trình hiện có.”
- Trang/extraction `proposed` được cảnh báo chưa xác minh; chỉ extraction `verified` nên dùng làm thông tin tin cậy.
- Provider lỗi thì fallback trích xuất trực tiếp. Không đưa API key xuống frontend.
- Conversation: tạo, đọc, đổi tên, xóa; `q` chỉ lọc tiêu đề hội thoại.

## 3. Tiến độ từ tin nhắn Zalo

`POST /projects/{p}/ai/progress-parse` là parser tất định, không gọi LLM và không ghi DB:

- Trả ngày thi công, dòng công tác, mã cấu kiện, công đoạn ứng viên, cảnh báo và câu hỏi cần kỹ sư quyết định.
- Xử lý mã lạ/trùng, nhiều công đoạn, đã hoàn thành trước đó, trạng thái mặc định, ngoài phạm vi và ngày tương lai.
- UI chỉ ghi qua API tiến độ sau khi người dùng xem lại; tiến độ không tạo nghiệm thu.

## 4. Acceptance

- Hàng chờ `GET /acceptance/pending` lấy từ cấu kiện/công đoạn đã hoàn thành; tạo PYC nháp từ cấu kiện.
- PYC/BBNT dùng numbering theo project; BBNT tái sử dụng PYC, có checklist 7 mục `yes|no|unconfirmed`, revision/stale và preview/export.
- Liên kết cấu kiện là tường minh qua `component_acceptance_links`; không suy ra nghiệm thu từ tiến độ.
- Import lịch sử từ workbook bằng `scripts/import_acceptance_workbook.py`: preview mặc định, `--commit`, idempotent, không sửa workbook; chỉ xác nhận khi workbook có số/ngày hợp lệ.
- Không có AI trong package `backend/app/acceptance/`.

## 5. Site và core

- **Đợt thi công**: `construction_batches` + `construction_batch_components`; nhóm thi công, không đổi zone/segment thiết kế. Batch áp dụng cho danh mục, tiến độ, bản đồ, overview.
- **Tiến độ**: append-only; bulk preview/commit, daily preview/commit, undo theo đợt, correct sự kiện; sự kiện void bị bỏ qua ở mọi truy vấn đọc.
- **Tham số thiết kế**: `component_design_parameters` cho từng cấu kiện (`t_cm`, `L1_m`…); tên bước render `t = … cm`.
- **Ảnh**: `site_photos`, `site_photo_components`, `photo_work_item_links`; caption do người dùng nhập/xác nhận.
- **Bản đồ**: nhiều sheet từ `data/storage/dap-maps/<key>/manifest.json`; `component_map_positions` lưu vị trí nháp/duyệt, DB thắng manifest khi cùng component + sheet.
- **Nhật ký**: preview, snapshot bất biến, export từ snapshot đã duyệt.
- **Overview**: `latest-day`, `in-progress`, `segments`; chỉ đọc dữ liệu thật.

## 6. Đã bỏ (23-24/11/2026)

- Upload/ingest tài liệu trong ứng dụng; OCR/Tesseract; embedding/sqlite-vec ingest.
- Tìm kiếm tài liệu, cross-reference.
- Checklist tài liệu độc lập. Checklist 7 mục trong BBNT vẫn còn.
- AI report-draft.
- AI gợi ý caption ảnh; `suggested_caption` chỉ còn là trường legacy, `confirmed_caption` mới là nguồn.

Các bảng/cột `DocumentChunk`, `DocumentEmbedding`, `ocr_text`, `ocr_confidence` còn trong schema cũ nhưng không thuộc luồng ingest/retrieval hiện tại.

## 7. Kiểm chứng

- Backend suite 24/11/2026: **396 passed, 6 skipped** (DB/storage tạm).
- Route thực tế nằm trong các router: `core`, `component_router`, `batch_router`, `drawing_map_router`, `overview_router`, `insights_router`, `site`, `engineering_ai`, `acceptance`.
- Không có migration mới trong đợt docs này.
