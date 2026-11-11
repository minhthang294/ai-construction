# Kiến trúc AI

Upload PDF private → validate magic/size → SHA-256/version → PyMuPDF extract theo trang → render trang scan → OCR tiếng Việt khi thiếu text → chunk có page ID → FTS5 + vector index → hybrid retrieve → provider abstraction → trả lời chỉ theo citation.

Job ingest chạy bất đồng bộ và có trạng thái pending/running/failed/ready; retry không tạo bản ghi trùng. Provider dùng biến môi trường phía server, không có khóa trong frontend. Unit test dùng mock provider. OCR confidence thấp phải báo “Thông tin chưa đủ độ tin cậy, cần kiểm tra trực tiếp bản vẽ gốc.” Không nguồn phải trả “Không tìm thấy thông tin này trong hồ sơ công trình hiện có.”

Vision chỉ đề xuất loại ảnh/caption/vùng cần xem xét; kỹ sư xác nhận trước khi dùng làm chứng cứ. Cross-reference chỉ đánh dấu nghi vấn kèm hai citation, không kết luận thiết kế sai. Giới hạn tốc độ và kiểm quyền theo project trước khi gọi model. Chưa có bản vẽ/thuyết minh thực nên không được ghi AI knowledge base công trình đã xác minh.
