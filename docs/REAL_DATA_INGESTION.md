# Nạp hồ sơ thật và kiểm chứng

Quy trình này chỉ dùng cho dữ liệu công trình thật. Không thay thế việc kỹ sư đọc bản vẽ gốc.

## 0. Chuẩn bị

1. Sao lưu trước khi ghi dữ liệu:

   ```bash
   python3 scripts/backup.py /tmp/opencode/backup-truoc-ingest.tar.gz
   ```

2. Tạo tài khoản quản trị nếu DB còn trống:

   ```bash
   scripts/bootstrap_admin.sh
   ```

3. Cài `vie` cho OCR và kiểm tra:

   ```bash
   TESSDATA_PREFIX="$HOME/.local/share/tessdata" tesseract --list-langs
   ```

4. Chạy ứng dụng bằng `scripts/start.sh` để có storage, template canonical và `TESSDATA_PREFIX` đúng.

## 1. Nguồn thật hiện có

| Tệp | Số trang | Dung lượng | Ghi chú |
| --- | --- | --- | --- |
| `bản vẽ scan_1.pdf` | 133 | ~49 MB | scan ảnh, không có text |
| `Tập 1 - thuyết minh báo cáo KTKT sửa chữa nứt cọc dầm cầu cảng_0001.pdf` | 108 | ~66 MB | scan ảnh, không có text |

File thuyết minh vượt giới hạn mặc định 50 MB. Đặt trước khi khởi động backend:

```bash
export ENGINEERING_AI_MAX_PDF_BYTES=80000000
export TESSDATA_PREFIX="$HOME/.local/share/tessdata"
```

## 2. Tạo project và tải hồ sơ

1. Đăng nhập bằng tài khoản quản trị.
2. Tạo project đúng tên công trình trong hồ sơ; không dùng dữ liệu demo.
3. Vào `Kho tài liệu`, tải lần lượt hai PDF. Mỗi tệp trả về trạng thái `pending`/`running`, sau đó `ready`.
4. Không tải lại cùng tệp để "thử"; upload trùng hash được xử lý idempotent nhưng vẫn tốn thời gian.
5. Theo dõi trạng thái trong UI. Nếu backend restart giữa chừng, dùng chức năng ingest lại thay vì tạo bản ghi mới.

Ước tính trên máy hiện tại: OCR 1–3 giây/trang, khoảng 8–15 phút cho 241 trang, cộng thời gian render/chunk/embedding. Nên chạy khi máy rảnh và giữ backend sống đến khi cả hai tài liệu `ready`.

## 3. Kiểm chứng bắt buộc

- Đúng số trang: 133 và 108.
- Mỗi citation có `document_id`, `page_number`, `quote`; quote phải là đoạn nguyên văn trong text trang.
- Trang OCR confidence thấp phải hiện cảnh báo và không được coi là kết luận kỹ thuật.
- Câu hỏi không có nguồn phải trả đúng câu từ chối, không bịa số liệu.
- Đối chiếu thử một vài thông số thực (số hiệu bản vẽ, kích thước, ngày) bằng cách mở đúng trang gốc cạnh citation.
- Không dùng kết quả AI để tự xác nhận nghiệm thu; mọi checklist vẫn `unconfirmed` cho đến khi người có quyền xác nhận.

## 4. Sau khi hồ sơ `ready`

1. Tạo PYC từ báo cáo ngày có liên kết work item/daily report.
2. Kiểm tra lại template canonical sau khi người dùng sửa workbook:
   `scripts/refresh_acceptance_template.sh`.
3. Xuất PYC/BBNT, mở file kiểm tra không còn dữ liệu nhân sự/kết luận cũ.
4. Chạy `scripts/verify_all.sh` trước khi bàn giao hoặc triển khai.
