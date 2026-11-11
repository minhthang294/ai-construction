# Kiến trúc tổng thể

## Trạng thái khởi đầu

Repository trống ngày 11/11/2026. Không có V1 để giữ nguyên. Excel người dùng cung cấp là mẫu thực tế duy nhất, nằm ngoài repository. Bản vẽ/thuyết minh sẽ tải lên sau.

## Thiết kế

- Backend FastAPI + SQLAlchemy 2 + Alembic + SQLite ban đầu. Một DB và một chủ sở hữu migration là Codex. Vector index bền vững dùng sqlite-vec trong cùng file DB; file gốc và page render vẫn ở storage private.
- Frontend React/TypeScript/Vite/Tailwind, PWA mobile-first. IndexedDB lưu bản nháp và hàng đợi upload; API trả id để đồng bộ idempotent.
- File gốc ở thư mục private theo project và hash, DB chỉ giữ metadata. Tải file qua API đã kiểm quyền, không mở static mount.
- `project_id` là phạm vi mọi entity và API. `work_item_id` là tham chiếu dùng chung, có thể null khi chưa xác định.
- Vai trò: admin, project_manager, engineer, viewer. Hiện chỉ admin/project_manager xác nhận kết quả; AI chỉ đề xuất. Cấp quyền nghiệm thu riêng chưa có trong shared auth.
- Thời gian lưu UTC trong DB, xuất và hiển thị theo Asia/Ho_Chi_Minh. Ngày báo cáo là ngày địa phương.
- Audit log ghi actor, project, entity, action, timestamp và chi tiết JSON; backup DB cùng thư mục file private và template version.

## Hai hệ thống độc lập

- **System A — Engineering AI**: upload một lần, ingest nền, lưu bền vững original/page/text/OCR/chunk/embedding/FTS/vector, retrieval project-scoped, citation theo trang, conversation history, versioning với revision hiệu lực do người quản lý xác nhận.
- **System B — Acceptance**: PYC/BBNT sinh tất định từ DB + template Excel + cấu hình numbering. Không gọi LLM/Vision/Embedding; không tự tạo kết luận hoặc chữ ký. BBNT tái sử dụng PYC và cảnh báo stale nếu PYC đổi sau khi phát hành.
- Chi tiết quyết định và schema: `docs/ADDENDUM_ARCHITECTURE.md`.

## Phân luồng

`Project → WorkItem → DailyWorkLog / SitePhoto / AcceptanceRequest → AcceptanceRecord`. `SourceDocument → DocumentPage → DocumentChunk → Citation` thuộc cùng Project. Báo cáo ngày gom manpower, log, plan, ảnh đã chọn; xuất file từ snapshot đã được người dùng duyệt.

## Nguyên tắc an toàn

Không dùng dữ liệu demo làm bản ghi thực. Không tự xác nhận nghiệm thu, GPS, kích thước hoặc khối lượng từ ảnh. RAG thiếu nguồn trả đúng câu từ chối. Template Excel chỉ đọc và sao chép khi xuất. Không tự động gửi Zalo.
