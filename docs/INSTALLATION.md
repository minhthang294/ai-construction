# Cài đặt

Xem [quy trình triển khai trên Google Compute Engine](GOOGLE_VM_DEPLOYMENT.md) để đóng gói, cấu hình HTTPS, sao lưu và cập nhật VM.

## Yêu cầu

Python 3.12+, Node/npm, SQLite, LibreOffice (chỉ khi cần xuất PYC/BBNT PDF). AI provider bên ngoài là tùy chọn; không cần API key để chạy test và chế độ trả lời trích xuất trực tiếp.

## Linux/macOS

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
cd frontend && npm install && cd ..
cd backend && ../.venv/bin/alembic upgrade head && cd ..
```

Trên Windows, tạo `.venv` bằng Python cho Windows rồi cài `backend/requirements.txt`, `npm install` trong `frontend`.

Sao chép workbook mẫu PYC/BBNT được cấp vào `data/templates/acceptance-original.xlsx` trên máy triển khai. File này có dữ liệu thực nên `.gitignore` loại khỏi Git; đặt quyền đọc giới hạn cho tài khoản chạy ứng dụng.

Khi người dùng cập nhật workbook gốc, đóng LibreOffice rồi chạy:

```bash
scripts/refresh_acceptance_template.sh "/duong-dan/workbook-nguoi-dung.xlsx"
```

Script từ chối chạy nếu workbook đang mở, kiểm tra cấu trúc PYC/BBNT trước khi thay, và lưu bản cũ vào `data/templates/archive/`. Không sửa trực tiếp file gốc.

Tạo tài khoản quản trị đầu tiên bằng `scripts/bootstrap_admin.sh`; script hỏi username/mật khẩu trực tiếp, không ghi mật khẩu vào source, biến môi trường của shell hay command history. Không đặt thông tin đăng nhập trong tài liệu dùng chung.

## Chạy local

Cách nhanh trên Windows với dữ liệu demo đã chuẩn bị sẵn:

```powershell
data/storage/demo-live/run-backend.ps1   # API tại http://127.0.0.1:8765
data/storage/demo-live/run-frontend.ps1  # giao diện tại http://127.0.0.1:5173
```

Hoặc chạy cả hai bằng `scripts/start.sh` (Linux/macOS) / `scripts/start.bat` (Windows). Backend ở `http://localhost:8765` (đổi bằng `CONSTRUCTION_API_PORT`), frontend ở địa chỉ Vite in trên terminal.

## Cấu hình

- `DATABASE_URL`: SQLite URL, mặc định `data/app.db`. Vector index dùng extension `sqlite-vec` trong cùng file DB; `scripts/backup.py` sao lưu cả DB nên vector đi kèm.
- `SITE_REPORT_STORAGE`, `ENGINEERING_AI_STORAGE`, `ACCEPTANCE_STORAGE`: nơi lưu file private; `scripts/start.*` trỏ vào `data/storage/`.
- `ACCEPTANCE_TEMPLATE`: mặc định khi chạy script là `data/templates/acceptance-original.xlsx`.
- `ENGINEERING_AI_PROVIDER`, `ENGINEERING_AI_OPENCODE_MODEL`, `ENGINEERING_AI_TIMEOUT`: provider/model chat tùy chọn ở backend; xem `backend/app/engineering_ai/providers.py`. Không đặt key vào frontend.

Hồ sơ PDF không upload qua giao diện. Trang và kết quả trích xuất theo trang được nạp bằng DB/storage đã duyệt hoặc bằng script import; xem [REAL_DATA_INGESTION.md](REAL_DATA_INGESTION.md).

## Kiểm tra

```bash
scripts/verify_all.sh
```

Script chạy backend test, frontend test và build với DB/storage tạm dưới `/tmp/opencode`, không đọc/ghi `data/app.db` hay workbook nguồn.

API docs ở `/docs`.

Trên điện thoại, PWA/service worker và camera yêu cầu trang được phục vụ qua HTTPS (hoặc `localhost` khi thử trên chính thiết bị). URL HTTP của Vite trên mạng LAN chỉ dành để xem giao diện; khi triển khai hiện trường cần HTTPS và kiểm soát truy cập mạng.
