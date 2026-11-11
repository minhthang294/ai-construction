# Construction Site Assistant

Ứng dụng quản lý công trường gồm báo cáo ngày, ảnh hiện trường, hồ sơ nghiệm thu PYC/BBNT và tra cứu tài liệu có dẫn nguồn. Repository này được khởi tạo từ thư mục trống ngày 11/11/2026; không có code V1 để chuyển đổi. Mẫu Excel người dùng cung cấp được sao chép nguyên vẹn tại `data/templates/acceptance-original.xlsx`. Bản vẽ và thuyết minh thực tế chưa được tải lên.

- [Cài đặt và chạy](docs/INSTALLATION.md)
- [Hướng dẫn sử dụng](docs/USER_GUIDE.md)
- [Sao lưu và phục hồi](docs/BACKUP_RESTORE.md)
- [Kiến trúc và hợp đồng API](docs/MASTER_ARCHITECTURE.md)
- [Trạng thái hồ sơ nguồn](docs/SOURCE_DOCUMENT_STATUS.md)
- [Điều phối ba OpenCode agent](docs/CODEX_ORCHESTRATION.md)
- [Bảng điều phối và trạng thái xác minh](docs/agent-reports/COORDINATION.md)
- [Nạp hồ sơ thật và kiểm chứng](docs/REAL_DATA_INGESTION.md)
- [Kiến trúc bổ sung: Knowledge Base và Acceptance tất định](docs/ADDENDUM_ARCHITECTURE.md)

Backend dùng FastAPI, SQLAlchemy, Alembic và SQLite. Frontend dùng React, TypeScript, Vite, Tailwind và IndexedDB. Tất cả file gốc được lưu ngoài DB trong thư mục private; API kiểm quyền trước khi tải. AI chỉ trả lời theo trang hồ sơ đã nạp, và không xác nhận nghiệm thu.
