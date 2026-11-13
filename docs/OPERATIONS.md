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

Có thể đổi mật khẩu ngay trong giao diện: nút **Đổi mật khẩu** ở header. Backend thu hồi toàn bộ token cũ và buộc đăng nhập lại.

## 3. Dữ liệu thật đã nạp

- Project: `THI CÔNG SỬA CHỮA VẾT NỨT CỌC VÀ DẦM CẦU CẢNG NHÀ MÁY DAP`
- 42 work item lấy từ sheet `DM` của workbook (một số bổ sung trong quá trình dùng).
- Hồ sơ:
  - `bản vẽ scan_1.pdf` — 133 trang, trạng thái `ready`
  - `Tập 1 - thuyết minh báo cáo KTKT sửa chữa nứt cọc dầm cầu cảng_0001.pdf` — 108 trang, trạng thái `ready`
- Storage: `data/storage/engineering-ai` (khoảng 450 MB render + file gốc).
- Search/chat theo project đã trả citation và mở đúng trang render.
- Chat backend dùng **OpenCode DeepSeek V4.1 Flash** (`ENGINEERING_AI_PROVIDER=opencode_deepseek`); nếu OpenCode service lỗi thì tự fallback extractive, vẫn giữ citation.
- Ví dụ đã kiểm tra: “Chiều dài cầu cảng là bao nhiêu?” → `165m [2]`, citation trang 10 hồ sơ thuyết minh.

## 4. Page extraction

- **Đã extraction toàn bộ 241/241 trang**: 108 trang thuyết minh + 133 trang bản vẽ.
- 241 bản ghi extraction, **7.664 key values**, **4.303 warnings**; tất cả đang `proposed`.
- Chế độ: 117 trang bản vẽ dùng tile, 124 trang còn lại dùng direct.
- Dữ liệu extraction nằm trong `engineering_ai_page_extractions`, mặc định `proposed`.
- Review trong `AI hồ sơ kỹ thuật → Hồ sơ & trang → chọn trang`: panel hiển thị summary/key values/warnings/confidence, nút Xác nhận/Từ chối.
- Chỉ dữ liệu `verified` mới nên dùng làm thông tin tin cậy; `proposed` phải đối chiếu trang gốc.
- Import kết quả extraction hàng loạt:

```bash
.venv/bin/python scripts/import_page_extractions.py \
  /tmp/opencode/full-drawings-a \
  /tmp/opencode/full-drawings-b \
  /tmp/opencode/full-drawings-c \
  /tmp/opencode/full-drawings-d \
  --prompt-version batch-v1
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

Đã có bản sao lưu sau khi extraction đầy đủ:

```bash
python3 scripts/backup.py /tmp/opencode/backup-ready-20261113.tar.gz
```

Kích thước khoảng 510 MB. Sao lưu định kỳ ra ngoài `data/`; archive chứa hồ sơ công trình, không commit.

## 7. Kiểm tra

```bash
scripts/verify_all.sh
```

Kết quả hiện tại:

- Backend: **292 passed**
- Frontend: **115 passed**
- Production build: pass
- Migration head: `e2f6a1c9d430`

## 8. Giới hạn cần biết

1. **AI trả lời dùng OpenCode DeepSeek V4.1 Flash** ở backend (`ENGINEERING_AI_PROVIDER=opencode_deepseek`). Nếu OpenCode service không khả dụng, tự fallback extractive. Câu trả lời vẫn có citation và kiểm tra grounding.
2. **OCR bản vẽ có lỗi**; không dùng số OCR/model làm kết luận kỹ thuật khi chưa kiểm tra trang gốc.
3. **Page extraction đã đủ 241 trang** nhưng toàn bộ đang `proposed`; cần kỹ sư review/verify trước khi dùng làm dữ liệu tin cậy.
4. **PWA/camera trên điện thoại** cần HTTPS và kiểm tra thiết bị thật.
5. SQLite một file; phù hợp một máy/công trường nhỏ, chưa phải multi-worker.
