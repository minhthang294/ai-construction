# Construction Site Assistant

Ứng dụng quản lý công trường gồm báo cáo ngày, ảnh hiện trường, danh mục cấu kiện cọc/dầm, đợt thi công, ghi tiến độ từ tin nhắn Zalo, hồ sơ nghiệm thu PYC/BBNT và hỏi AI có dẫn nguồn. Repository này được khởi tạo từ thư mục trống ngày 11/11/2026; không có code V1 để chuyển đổi. Mẫu Excel người dùng cung cấp được sao chép nguyên vẹn tại `data/templates/acceptance-original.xlsx`.

- [Cài đặt và chạy](docs/INSTALLATION.md)
- [Hướng dẫn sử dụng](docs/USER_GUIDE.md)
- [Sao lưu và phục hồi](docs/BACKUP_RESTORE.md)
- [Kiến trúc và hợp đồng API](docs/MASTER_ARCHITECTURE.md)
- [Trạng thái hồ sơ nguồn](docs/SOURCE_DOCUMENT_STATUS.md)
- [Điều phối ba OpenCode agent](docs/CODEX_ORCHESTRATION.md)
- [Bảng điều phối và trạng thái xác minh](docs/agent-reports/COORDINATION.md)
- [Nạp dữ liệu thật và kiểm chứng](docs/REAL_DATA_INGESTION.md)
- [Kiến trúc bổ sung: Knowledge Base và Acceptance tất định](docs/ADDENDUM_ARCHITECTURE.md)
- [Vận hành và bàn giao](docs/OPERATIONS.md)

Backend dùng FastAPI, SQLAlchemy, Alembic và SQLite. Frontend dùng React, TypeScript, Vite, Tailwind và IndexedDB. Tất cả file gốc được lưu ngoài DB trong thư mục private; API kiểm quyền trước khi tải.

AI hiện trả lời trên **dữ liệu đã được AI trích xuất theo trang** (lưu trong DB, có citation) và **cơ sở dữ liệu cấu kiện/tiến độ**; không có chức năng upload PDF hay OCR trong ứng dụng. Mọi câu trả lời đều có nguồn hoặc từ chối khi thiếu nguồn, và AI không bao giờ tự xác nhận nghiệm thu.

## Chạy nhanh trên Windows

```powershell
# Backend (dùng database/storage demo đã chuẩn bị)
data/storage/demo-live/run-backend.ps1
# Frontend
data/storage/demo-live/run-frontend.ps1
```

Hoặc chạy toàn bộ bằng `scripts/start.bat` (Windows) / `scripts/start.sh` (Linux/macOS). Không đặt mật khẩu, API key hay token trong tài liệu.
