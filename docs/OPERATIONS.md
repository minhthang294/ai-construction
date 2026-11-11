# Vận hành và bàn giao

Cập nhật: 12/11/2026. Đây là trạng thái đang chạy trên máy hiện tại.

## 1. Địa chỉ

- Giao diện: `http://localhost:5173`
- API: `http://127.0.0.1:8765`
- Health: `http://127.0.0.1:8765/health`

Chạy lại:

```bash
ENGINEERING_AI_MAX_PDF_BYTES=80000000 CONSTRUCTION_API_PORT=8765 scripts/start.sh
```

## 2. Tài khoản

- Username: `admin`
- Mật khẩu ban đầu: `data/.admin-initial-password` (quyền `600`, đã ignore khỏi Git)
- Đọc mật khẩu một lần, lưu an toàn, sau đó xoá file:

```bash
cat data/.admin-initial-password
rm data/.admin-initial-password
```

Chưa có màn hình đổi mật khẩu; nếu cần đổi, tạo user admin mới hoặc cập nhật `users.password_hash` qua script quản trị.

## 3. Dữ liệu thật đã nạp

- Project: `THI CÔNG SỬA CHỮA VẾT NỨT CỌC VÀ DẦM CẦU CẢNG NHÀ MÁY DAP`
- 41 work item lấy từ sheet `DM` của workbook.
- Hồ sơ:
  - `bản vẽ scan_1.pdf` — 133 trang, trạng thái `ready`
  - `Tập 1 - thuyết minh báo cáo KTKT sửa chữa nứt cọc dầm cầu cảng_0001.pdf` — 108 trang, trạng thái `ready`
- Storage: `data/storage/engineering-ai` (khoảng 450 MB render + file gốc).
- Search/chat theo project đã trả citation và mở đúng trang render.

## 4. Page extraction

- 20 trang đã import vào bảng `engineering_ai_page_extractions`:
  - 10 trang bản vẽ: mode `tile`, 594 key values
  - 10 trang thuyết minh: mode `direct`, 75 key values
- Tất cả đang ở trạng thái `proposed`; **chưa có trang nào được kỹ sư xác nhận**.
- Review trong `AI hồ sơ kỹ thuật → Hồ sơ & trang → chọn trang`: panel hiển thị summary/key values/warnings/confidence, nút Xác nhận/Từ chối.
- Chỉ dữ liệu `verified` mới nên dùng làm thông tin tin cậy; `proposed` phải đối chiếu trang gốc.
- Chạy thêm extraction:

```bash
scripts/deepseek_page_extract.py \
  --pdf "/path/to/file.pdf" \
  --pages 1-20 \
  --out /tmp/opencode/extract \
  --mode direct
```

Với bản vẽ dùng `--tile-grid 2 --tile-workers 4`. Script chỉ dùng DeepSeek V4.1 Flash.

## 5. Nghiệm thu

Đã kiểm tra end-to-end với dữ liệu thật:

- Tạo PYC `PYC-001` từ work item.
- Preview đúng số phiếu.
- Tạo BBNT, checklist, xác nhận `approved`.
- Xuất PYC và BBNT ra Excel và PDF thành công, mở được bằng OpenPyXL.
- Numbering mặc định `PYC-001`; cấu hình tại `Nghiệm thu → Cấu hình số`.

## 6. Sao lưu

Đã có bản sao lưu trước khi bàn giao:

```bash
python3 scripts/backup.py /tmp/opencode/backup-ready-20261112.tar.gz
```

Kích thước khoảng 508 MB. Sao lưu định kỳ ra ngoài `data/`; archive chứa hồ sơ công trình, không commit.

## 7. Kiểm tra

```bash
scripts/verify_all.sh
```

Kết quả hiện tại:

- Backend: **185 passed**
- Frontend: **34 passed**
- Production build: pass
- Migration head: `e2f6a1c9d430`

## 8. Giới hạn cần biết

1. **AI trả lời mặc định là offline extractive**, chưa cấu hình LLM provider. Câu trả lời có citation nhưng có thể chỉ liệt kê đoạn liên quan, chưa diễn giải tốt.
2. **OCR bản vẽ có lỗi**; không dùng số OCR/model làm kết luận kỹ thuật khi chưa kiểm tra trang gốc.
3. **Page extraction 20 trang mới là proposed**, chưa verified; chưa chạy toàn bộ 241 trang.
4. **PWA/camera trên điện thoại** cần HTTPS và kiểm tra thiết bị thật.
5. **Chưa có màn hình đổi mật khẩu**; xử lý file mật khẩu ban đầu cẩn thận.
6. SQLite một file; phù hợp một máy/công trường nhỏ, chưa phải multi-worker.
