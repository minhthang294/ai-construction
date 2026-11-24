# Nạp dữ liệu thật và kiểm chứng

Quy trình này chỉ dùng cho dữ liệu công trình thật. Không thay thế việc kỹ sư đọc bản vẽ gốc. Ứng dụng không có upload PDF/OCR: hồ sơ, trang và kết quả trích xuất theo trang được tạo offline bằng DeepSeek V4.1 Flash rồi nạp vào DB/storage đã duyệt.

## 0. Chuẩn bị

1. Sao lưu trước khi ghi dữ liệu:

   ```bash
   python3 scripts/backup.py /tmp/opencode/backup-truoc-ingest.tar.gz
   ```

2. Tạo tài khoản quản trị nếu DB còn trống:

   ```bash
   scripts/bootstrap_admin.sh
   ```

3. Chạy ứng dụng bằng `scripts/start.sh` (hoặc `data/storage/demo-live/run-backend.ps1` trên Windows) để có storage và template canonical.

## 1. Hồ sơ và trích xuất theo trang

- File gốc, trang và kết quả trích xuất nằm trong DB (`engineering_ai_documents`, `document_pages`, `engineering_ai_page_extractions`) và storage private. Không upload lại qua giao diện.
- Với database đã duyệt, khôi phục nguyên bộ `app.db` + `storage/` + `templates/` để giữ đúng trang và citation.
- Khi đã có tài liệu/trang trong DB, nạp thêm kết quả trích xuất đã review bằng script:

```bash
.venv/bin/python scripts/import_page_extractions.py \
  /duong-dan/full-drawings-a \
  /duong-dan/full-drawings-b \
  --project DAP \
  --prompt-version batch-v1
```

Script chỉ gửi metadata extraction, không ghi đè text trang hay file gốc. Kết quả mặc định là `proposed`; kỹ sư xác nhận trong **AI hồ sơ kỹ thuật → Hồ sơ & trang**.

## 2. Tham số thiết kế `t` của cọc

Dùng CSV đã đối chiếu bản vẽ. Mặc định chỉ xem trước:

```bash
.venv/bin/python scripts/import_design_parameters.py \
  --database data/app.db \
  --project "TEN CONG TRINH" \
  --csv duong-dan/DAP-coc-thong-so.csv
```

Thêm `--commit` mới ghi. Script báo rõ số dòng khớp, cọc có `t`, dòng không khớp/mơ hồ/xung đột; không ghi đè giá trị khác đã lưu và ghi một audit entry.

## 3. Danh mục, tiến độ và nghiệm thu

1. Nhập danh mục cấu kiện trong **Cấu kiện** (xem trước Excel rồi xác nhận).
2. Ghi tiến độ bằng **Ghi tiến độ từ tin nhắn** hoặc trong **Hiện trường**; dùng đợt thi công để gom cấu kiện.
3. Tạo PYC từ danh sách **Chờ nghiệm thu** hoặc từ báo cáo ngày có liên kết work item/daily report.

## 4. Kiểm chứng bắt buộc

- Đúng số trang tài liệu và đúng tên file gốc.
- Mỗi citation có `document_id`, `page_number`, `quote`; quote phải là đoạn nguyên văn trong text trang.
- Kết quả trích xuất `proposed` hiện cảnh báo và không được coi là kết luận kỹ thuật.
- Câu hỏi không có nguồn phải trả đúng câu từ chối, không bịa số liệu.
- Đối chiếu thử một vài thông số thực (số hiệu bản vẽ, kích thước, ngày) bằng cách mở đúng trang gốc cạnh citation.
- Không dùng kết quả AI để tự xác nhận nghiệm thu; mọi checklist vẫn `unconfirmed` cho đến khi người có quyền xác nhận.

## 5. Sau khi dữ liệu sẵn sàng

1. Kiểm tra lại template canonical sau khi người dùng sửa workbook: `scripts/refresh_acceptance_template.sh`.
2. Xuất PYC/BBNT, mở file kiểm tra không còn dữ liệu nhân sự/kết luận cũ.
3. Chạy `scripts/verify_all.sh` trước khi bàn giao hoặc triển khai.
