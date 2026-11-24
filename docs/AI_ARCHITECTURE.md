# Kiến trúc AI

Ứng dụng không có upload PDF và không chạy OCR. Hồ sơ nguồn, các trang và kết quả trích xuất theo trang đã nằm trong DB/storage của công trình; kết quả trích xuất do DeepSeek V4.1 Flash tạo offline và được nạp bằng script có kiểm tra (`scripts/import_page_extractions.py`).

## Trả lời hỏi đáp

Luồng: câu hỏi trong project → xác định loại câu hỏi → tra **cơ sở dữ liệu cấu kiện/tiến độ** (cọc, dầm, công đoạn, đợt thi công, tiến độ chưa huỷ, tham số thiết kế `t`) → bổ sung **trích xuất theo trang** đã lưu (`engineering_ai_page_extractions`) → provider tùy chọn (OpenCode DeepSeek qua biến môi trường server) → kiểm tra grounding/citation → trả lời.

- Mỗi câu trả lời dựa trên dữ liệu phải có citation `document_id`, `page_number`, `quote`; quote là đoạn nguyên văn của trang.
- Không có nguồn thì trả “Không tìm thấy thông tin này trong hồ sơ công trình hiện có.”, không suy đoán số liệu.
- Trang/kết quả trích xuất `proposed` được cảnh báo là chưa xác minh; chỉ dữ liệu `verified` mới nên dùng làm thông tin tin cậy.
- Provider lỗi thì fallback trích xuất trực tiếp, vẫn giữ citation. Không có khóa API trong frontend.

## Ghi tiến độ từ tin nhắn Zalo

`POST /projects/{p}/ai/progress-parse` là parser tất định, không gọi LLM. Parser trả về ngày, dòng công tác, cấu kiện khớp, công đoạn gợi ý, cảnh báo và câu hỏi tiếng Việt cho các trường hợp cần kỹ sư quyết định: mã lạ/trùng, nhiều công đoạn, đã hoàn thành trước đó, trạng thái mặc định, ngoài phạm vi, ngày ở tương lai. UI chỉ ghi sau khi người dùng xem lại; tiến độ không tạo nghiệm thu.

## Ảnh và nghiệm thu

Vision chỉ đề xuất loại ảnh/caption/gắn cấu kiện; kỹ sư xác nhận trước khi dùng làm chứng cứ. PYC/BBNT và mọi bản xuất là tất định từ dữ liệu đã lưu; AI không tạo quyết định nghiệm thu, không tự xác nhận checklist. Giới hạn tốc độ và kiểm quyền theo project trước khi gọi model.
