# Rà soát DM sync — 18/11/2026

Phạm vi: chỉ đọc code và chạy test/thí nghiệm trên workbook tạm. Không sửa code, không mở workbook thật, không dùng dữ liệu riêng.

## Nhận định đã kiểm chứng

1. **Cột B là "SỐ BIÊN BẢN"** (header của `data/templates/acceptance-original.xlsx`), nhưng `dm_sync._write_request` ghi `request.number` vào đó ngay khi PYC còn `draft` (`dm_sync.py:131`, gọi từ `service.py:984`). Không có lần ghi nào khi BBNT được xác nhận.
2. Số PYC hiện bằng số BBNT **chỉ khi** project chưa cấu hình dãy BBNT riêng (`service.py:1213-1217`). Khi bật dãy BBNT (`BBNT-...`), cột B giữ số PYC vĩnh viễn và không được cập nhật.
3. **Ghi đè dòng có sẵn là thật.** Thí nghiệm trên workbook tạm: dòng có sẵn số 47 cùng nội dung cũ; đồng bộ một PYC số 47 ghi đè nội dung dòng đó, trả `synced=True`, không cảnh báo, không tạo dòng mới. Nguyên nhân: `_find_row` chỉ khớp cột B (`dm_sync.py:80-86`).
4. `ACCEPTANCE_DM_WORKBOOK` là một đường dẫn chung (`dm_sync.py:34-36`), trong khi unique số PYC là theo project (`models.py:43`). Hai project cùng số sẽ trỏ cùng một dòng.
5. Không có trường nào trên request/record trỏ tới dòng DM (không có `dm_row`/`dm_workbook_id`). `ComponentWorkLink.dm_row` thuộc core, gắn hash seed, acceptance không dùng.

Hệ quả: không thể ngăn đầy đủ hai lỗi chỉ trong `backend/app/acceptance` + tests, vì thiếu khóa dòng ổn định (project + dòng) và cần quyết định nghiệp vụ cho cột B. Mọi guard dựa trên nội dung C/D chỉ là heuristic (chặn nhầm khi lần sync trước thất bại hoặc người dùng sửa tay; không phân biệt được dòng project khác với dòng người dùng điền số trước).

## Quyết định cần

- **A. Khóa dòng ổn định (shared schema, Codex):** thêm `dm_workbook_id` + `dm_row` trên `acceptance_requests` (hoặc bảng `acceptance_dm_rows`). Create luôn append và lưu dòng; update ghi đúng dòng đã lưu, lệch số/hash thì không ghi đè mà trả cảnh báo.
- **B. Tách workbook theo project (config, Codex sửa `scripts/start.sh`):** `ACCEPTANCE_DM_DIR` + `<project_id>.xlsx`. Triệt tiêu va chạm giữa project; không giải quyết cột B.
- **C. Ý nghĩa cột B:**
  - C1: giữ số PYC làm khóa đến khi có BBNT, sau đó ghi `record.number` (cần A).
  - C2: chỉ ghi DM sau khi BBNT được xác nhận, khóa theo `record.number`.
  - C3 (tạm): nếu project có dãy BBNT riêng thì bỏ sync và trả cảnh báo thay vì ghi sai số.
- **D. Tùy chọn:** guard "create không ghi đè số đã có trong workbook" — an toàn dữ liệu nhưng chặn workflow điền số trước; cần duyệt riêng.

## Phương án an toàn trước mắt

- Chưa chốt A/B/C: **không chạy nhiều project trên cùng một workbook DM**; mỗi project dùng một bản sao workbook riêng.
- Không bật dãy số BBNT riêng cho đến khi C1/C2 được triển khai (tránh cột B sai).
- Không thêm guard D khi chưa có quyết định, để không chặn workflow hiện tại.
- Các bản sửa đã có (không xoá F/G/I khi update, không dùng lại dòng đã có dữ liệu tay, khớp số 0 đầu) vẫn giữ nguyên và đã có test.

## Test đã chạy

- `backend/tests/acceptance/test_dm_sync.py`: **8 passed** (append/update, đổi số, số 0 đầu, giữ F/G/I khi update, bỏ qua dòng có dữ liệu tay, thiếu workbook, create qua API).
- `backend/tests/acceptance`: **87 passed, 6 skipped** (skip là test PDF/LibreOffice như các lần trước). DB in-memory của conftest, workbook trong `tmp_path`; `DATABASE_URL` trỏ file tạm.
- Thí nghiệm ghi đè: workbook tạo trong thư mục tạm của hệ điều hành, dữ liệu giả; không dùng file thật.

## Thay đổi file

Chỉ thêm file báo cáo này. Không sửa code, workbook, report khác, shared/core/migration/frontend; không commit/push.
