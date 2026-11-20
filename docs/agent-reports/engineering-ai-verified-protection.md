# Bảo vệ extraction đã xác minh

Ngày: 18/11/2026. Phạm vi: `backend/app/engineering_ai/` và test engineering_ai.

## Xác minh

`save_page_extraction` upsert theo `(page_id, model, prompt_version, mode)` và trước khi sửa luôn đặt
`status="proposed"`, xoá `verified_by`/`verified_at`/`verify_note`, ghi đè `extraction_json`.
Vì vậy chạy lại cùng key sẽ ghi đè và xoá dấu duyệt: giả thuyết đúng.

## Files

- `backend/app/engineering_ai/service.py`: thêm `PageExtractionConflict`; trong
  `save_page_extraction`, nếu row cùng key đang `verified` thì trả conflict, không ghi đè.
- `backend/app/engineering_ai/router.py`: route save map `PageExtractionConflict` thành HTTP 409.
- `backend/tests/engineering_ai/test_page_extraction_api.py`: thêm
  `test_verified_extraction_is_not_overwritten_by_same_version`.

## Giữ nguyên

- Quyền `project_editor_access`, project scope, `LookupError` → 404, validation → 422.
- Bản `proposed`/`rejected` vẫn upsert như cũ.
- Reingest vẫn reset về `proposed` khi text/bảng/render của trang thực sự thay đổi.
- Muốn ghi bản mới sau khi verified: dùng `model`, `prompt_version` hoặc `mode` khác.

## Test

Chạy trong `backend/`, với `DATABASE_URL` trỏ SQLite tạm trong `%TEMP%`; storage dùng
`tmp_path` của `conftest.py` (không chạm `data/app.db`).

- `..\.venv\Scripts\python.exe -m pytest tests\engineering_ai\test_page_extraction_api.py -q`
  → 9 passed, 1 warning (Starlette/httpx deprecation)
- `..\.venv\Scripts\python.exe -m pytest tests\engineering_ai -q`
  → 139 passed, 1 warning

Test hồi quy kiểm: POST lại cùng key sau verify → 409; bản gốc vẫn `verified`, giữ confidence,
extraction, `verified_by`, `verify_note`; `prompt_version` mới tạo bản ghi mới và không đổi bản cũ.

## Giới hạn

- Retry y hệt nội dung trên bản đã verified cũng trả 409 (đúng yêu cầu, khác hành vi cũ).
- Chưa chặn ghi đè bản `rejected`; cần quyết định nếu muốn.
- Chưa chạy full suite ngoài `tests/engineering_ai`; không kiểm tra UI.
- Chưa commit/push.
