# Cài đặt

Xem [quy trình triển khai trên Google Compute Engine](GOOGLE_VM_DEPLOYMENT.md) để đóng gói, cấu hình HTTPS, sao lưu và cập nhật VM.

## Yêu cầu

Python 3.12+, Node/npm, SQLite, LibreOffice (nếu cần xuất PYC/BBNT PDF), Tesseract với dữ liệu `vie` (nếu cần OCR PDF scan tiếng Việt). AI provider bên ngoài là tùy chọn; không cần API key để chạy test và chế độ trích dẫn từ hồ sơ.

## Linux/macOS

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
cd frontend && npm install && cd ..
cd backend && ../.venv/bin/alembic upgrade head && cd ..
```

Sao chép workbook mẫu PYC/BBNT được cấp vào `data/templates/acceptance-original.xlsx` trên máy triển khai. File này có dữ liệu thực nên `.gitignore` loại khỏi Git; đặt quyền đọc giới hạn cho tài khoản chạy ứng dụng.

Khi người dùng cập nhật workbook gốc, đóng LibreOffice rồi chạy:

```bash
scripts/refresh_acceptance_template.sh "/home/thangpham/Downloads/YCNT và BBNT.19.10 - nt thuc te.xlsx"
```

Script từ chối chạy nếu workbook đang mở, kiểm tra cấu trúc PYC/BBNT trước khi thay, và lưu bản cũ vào `data/templates/archive/`. Không sửa trực tiếp file gốc.

Tạo tài khoản quản trị đầu tiên bằng `scripts/bootstrap_admin.sh`; script hỏi username/mật khẩu trực tiếp, không ghi mật khẩu vào source, biến môi trường của shell hay command history. Mật khẩu tối thiểu 12 ký tự. Có thể dùng biến `BOOTSTRAP_ADMIN_USER`/`BOOTSTRAP_ADMIN_PASSWORD` nếu chạy trong pipeline kín, nhưng không đặt chúng trong file dùng chung.

Chạy `scripts/start.sh`. Backend ở `http://localhost:8765` (đổi bằng `CONSTRUCTION_API_PORT` nếu cần), frontend ở địa chỉ Vite in trên terminal. `scripts/start.bat` là bản tương ứng trên Windows. Trên Windows cần tạo `.venv` bằng Python cho Windows và cài npm trước.

## Cấu hình

- `DATABASE_URL`: SQLite URL, mặc định `data/app.db`. Vector index dùng extension `sqlite-vec` trong cùng file DB; `scripts/backup.py` đã sao lưu cả DB nên vector đi kèm.
- `SITE_REPORT_STORAGE`, `ENGINEERING_AI_STORAGE`, `ACCEPTANCE_STORAGE`: nơi lưu file private; `scripts/start.sh` trỏ vào `data/storage/`.
- `ACCEPTANCE_TEMPLATE`: mặc định khi chạy script là `data/templates/acceptance-original.xlsx`.
- `ENGINEERING_AI_*`: cấu hình model chat, vision và embedding tương thích OpenAI ở backend; xem `backend/app/engineering_ai/providers.py` và `embeddings.py`. Không đặt key vào frontend.
- `ENGINEERING_AI_MAX_PDF_BYTES`: giới hạn PDF; `scripts/start.sh` mặc định 80 MB để nhận file thuyết minh thực tế 66 MB.
- `TESSDATA_PREFIX`: thư mục chứa `vie.traineddata` nếu gói tiếng Việt không nằm trong `/usr/share/tessdata`. Có thể cài user-space:

```bash
mkdir -p "$HOME/.local/share/tessdata"
curl -fsSL -o "$HOME/.local/share/tessdata/vie.traineddata" \
  https://raw.githubusercontent.com/tesseract-ocr/tessdata_best/main/vie.traineddata
ln -sfn /usr/share/tessdata/eng.traineddata "$HOME/.local/share/tessdata/"
ln -sfn /usr/share/tessdata/osd.traineddata "$HOME/.local/share/tessdata/"
ln -sfn /usr/share/tessdata/configs "$HOME/.local/share/tessdata/configs"
ln -sfn /usr/share/tessdata/tessconfigs "$HOME/.local/share/tessdata/tessconfigs"
```

`scripts/start.sh` tự đặt `TESSDATA_PREFIX` khi thấy file này. Kiểm tra bằng `tesseract --list-langs`.

## Kiểm tra

```bash
scripts/verify_all.sh
```

Script chạy backend test, frontend test và build với DB/storage tạm dưới `/tmp/opencode`, không đọc/ghi `data/app.db` hay workbook nguồn.

API docs ở `/docs`. Kho tài liệu chỉ trở thành tri thức công trình sau khi người dùng tải PDF thực và kiểm tra các trang OCR/citation.

Trên điện thoại, PWA/service worker và camera yêu cầu trang được phục vụ qua HTTPS (hoặc `localhost` khi thử trên chính thiết bị). URL HTTP của Vite trên mạng LAN chỉ dành để xem giao diện; khi triển khai hiện trường cần HTTPS và kiểm soát truy cập mạng.
