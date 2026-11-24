# Vận hành và bàn giao

Cập nhật: 24/11/2026. Tài liệu này mô tả cách chạy và kiểm tra môi trường hiện tại; không chứa mật khẩu, token hay API key.

## 1. Địa chỉ và chạy

- Giao diện: `http://localhost:5173`
- API: `http://127.0.0.1:8765`
- Health: `http://127.0.0.1:8765/health`

Trên Windows với dữ liệu demo đã chuẩn bị:

```powershell
data/storage/demo-live/run-backend.ps1
data/storage/demo-live/run-frontend.ps1
```

Hoặc `scripts/start.sh` / `scripts/start.bat` cho môi trường `.venv` + `frontend/node_modules` của repo.

## 2. Tài khoản

Tạo tài khoản quản trị đầu tiên bằng `scripts/bootstrap_admin.sh` (script hỏi trực tiếp, không ghi mật khẩu ra file). Người dùng đổi mật khẩu trong giao diện bằng nút **Đổi mật khẩu**; backend thu hồi token cũ và buộc đăng nhập lại. Không lưu thông tin đăng nhập trong tài liệu.

## 3. Dữ liệu hiện có

- Project DAP và danh mục work item/cấu kiện đã nạp trong database đang dùng.
- Hồ sơ, trang và kết quả trích xuất theo trang nằm trong DB/storage private; phần lớn extraction đang `proposed`.
- Không có chức năng upload PDF/OCR trong ứng dụng. Hồ sơ mới được đưa vào bằng DB/storage đã duyệt và script import (xem [REAL_DATA_INGESTION.md](REAL_DATA_INGESTION.md)).
- Storage mặc định: `data/storage/engineering-ai`, `data/storage/site`, `data/storage/acceptance`.

## 4. Hỏi AI

- Chat trong **Hỏi AI** trả lời trên dữ liệu trích xuất theo trang + cơ sở dữ liệu cấu kiện/tiến độ và luôn kèm citation hoặc từ chối khi thiếu nguồn.
- Provider tùy chọn: `ENGINEERING_AI_PROVIDER`, `ENGINEERING_AI_OPENCODE_MODEL`, `ENGINEERING_AI_TIMEOUT`; không đặt key trong frontend. Provider lỗi thì fallback trích xuất trực tiếp, vẫn giữ citation.
- Kiểm tra nhanh: hỏi một thông số có trong trang đã trích xuất, mở citation đối chiếu; hỏi một thông tin không có để thấy câu từ chối.

## 5. Tiến độ, đợt thi công, sửa/hoàn tác

- **Ghi tiến độ từ tin nhắn**: dán tin nhắn Zalo → parser tất định trả về dòng/cấu kiện, cảnh báo và câu hỏi tiếng Việt (trạng thái, công đoạn, mã lạ/trùng, ngày tương lai) → xem trước → ghi.
- **Đợt thi công** gom cấu kiện ở nhiều khu; dùng để lọc khi ghi tiến độ và lập PYC.
- Sau khi ghi, có thể sửa thông tin hoặc hoàn tác cả đợt ghi (`/progress/batches/{id}/undo`) và sửa từng sự kiện (`/progress/events/{id}/correct`). Sự kiện đã huỷ không được tính vào tiến độ, nghiệm thu hay câu trả lời AI.
- Ghi tiến độ không tạo nghiệm thu.

## 6. Tham số thiết kế `t`

```bash
.venv/bin/python scripts/import_design_parameters.py \
  --database data/app.db \
  --project "TEN CONG TRINH" \
  --csv duong-dan/DAP-coc-thong-so.csv
```

Mặc định chỉ xem trước; `--commit` mới ghi. Script không ghi đè giá trị khác đã lưu, báo dòng không khớp/mơ hồ/xung đột và ghi audit. Chat trả lời chiều dày `t` của từng cọc kèm nguồn thiết kế.

## 7. Ảnh và cấu kiện

Ảnh hiện trường có thể gắn với cấu kiện; gợi ý của AI chỉ là đề xuất, kỹ sư xác nhận chú thích/loại ảnh trước khi dùng làm chứng cứ. Ảnh gốc lưu ngoài DB và tải qua API có kiểm quyền.

## 8. Nghiệm thu

- Đầu trang **Nghiệm thu** có danh sách **Chờ nghiệm thu**: cấu kiện có tiến độ hoàn thành gần nhất và chưa có BBNT xác nhận. Đi từ màn hình khác thì bộ lọc công đoạn/đợt hiển thị chip **Đang lọc** + **Xem tất cả**; tiêu đề hiển thị `đang lọc / tổng`.
- Chọn cấu kiện → **Tạo PYC nháp**: điền sẵn vị trí, công đoạn, ngày làm việc kế tiếp; liên kết cấu kiện ở trạng thái chờ, **không** tạo BBNT và không xác nhận nghiệm thu.
- BBNT/checklist Có/Không/Chưa xác nhận; chỉ người có quyền xác nhận. Xuất PYC/BBNT tất định từ template gốc, không giữ dữ liệu nhân sự/kết luận cũ.

## 9. Sao lưu

```bash
python3 scripts/backup.py /tmp/opencode/backup-$(date +%Y%m%d).tar.gz
```

Archive gồm `app.db`, `storage/`, `templates/`; giữ bản sao ngoài `data/`. Không commit archive hoặc dữ liệu công trình.

## 10. Kiểm tra

```bash
scripts/verify_all.sh
```

Script chạy backend test, frontend test và production build với DB/storage tạm. Chạy lại sau mỗi thay đổi schema/template.

## 11. Giới hạn cần biết

1. AI chỉ đáng tin khi citation trỏ đúng trang gốc; extraction `proposed` phải được kỹ sư xác nhận.
2. Không dùng kết quả AI làm kết luận kỹ thuật hoặc tự xác nhận nghiệm thu.
3. PWA/camera trên điện thoại cần HTTPS và kiểm tra trên thiết bị thật.
4. SQLite một file; phù hợp một máy/công trường nhỏ, chưa phải multi-worker.
