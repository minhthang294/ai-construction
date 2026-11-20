# Shared-core report: tạo cấu kiện thủ công (2026-11-18)

## Phạm vi thay đổi

| File | Thay đổi |
| --- | --- |
| `backend/app/core/component_models.py` | Cho phép null `source_id`, `source_hash`, `source_row`; cho phép null `RepairScope.reviewed_by`, `reviewed_at` |
| `backend/app/core/component_router.py` | Thêm `POST /projects/{p}/components`; kiểm quyền/segment/trùng mã; ghi `NEEDS_REVIEW`, `MANUAL_ENTRY`, audit; detail không gán cứng sheet cho cấu kiện thủ công |
| `backend/alembic/versions/170f7a3596cf_component_inventory.py` | Đồng bộ nullable với model (migration chưa commit) |
| `backend/tests/test_component_import.py` | Thêm test quyền, project scope, provenance, trùng canonical/raw/alias và tạo đồng thời |
| `docs/API_CONTRACTS.md` | Ghi hợp đồng endpoint thủ công và quy tắc provenance/định danh |

Không sửa `component_seed.py`, module acceptance/site/engineering, frontend, workbook, DB thật, `test_component_synthetic_e2e.py`, `component-qa.md` hay report khác. Không commit/push.

## Test đã chạy

- `pytest tests/test_component_import.py tests/test_component_conflicts.py tests/test_component_seed_preview.py tests/test_component_migration.py tests/test_component_synthetic_e2e.py -q` → **11 passed**.
- Test tạo đồng thời cùng mã chạy lặp 5 lần → **5/5 passed**, kết quả `[201, 409]`.
- Toàn bộ `backend/tests` → **302 passed, 7 skipped**; 3 lỗi tạm thời trong `test_component_synthetic_e2e.py` khi qa-integration đang sửa file. Chạy riêng e2e sau đó → **4/4 passed**.
- Regression sau review: import-commit set `RepairScope.reviewed_at=now()` cho scope `VERIFIED`; test khẳng định scope import có `reviewed_by` + `reviewed_at`, scope thủ công `NEEDS_REVIEW` có cả hai `NULL`. Bộ component test → **11 passed**.

## QA handoff

- Đã sửa bug mất timestamp duyệt ở `import-commit`; không đổi schema hay hợp đồng API.
- Test hồi quy nằm trong `backend/tests/test_component_import.py`; QA có thể chạy full suite lại từ trạng thái này.

## Unresolved / mapping

| Vấn đề | Owner | Ghi chú |
| --- | --- | --- |
| Migration `170f7a3596cf` vừa đổi nullable | Coordinator / Codex | Dev DB đã apply bản cũ cần downgrade/upgrade lại; không chạm DB thật |
| `test_component_synthetic_e2e.py` đang được hoàn thiện | qa-integration | Full-suite có thể dao động đến khi QA chốt |
| Endpoint thủ công không có idempotency key | Thiết kế hiện tại | Tạo trùng mã trả `409`, không trả lại bản ghi cũ |
| `DesignGroup` đọc qua FK chưa lọc lại project | Shared-core tương lai | Không tạo được tham chiếu chéo project qua API; chỉ rủi ro nếu DB bị can thiệp ngoài API |

## Cần review thủ công

- Xác nhận response `201` và audit action `component_created`.
- Xác nhận quyết định lưu `raw_code` như một alias trong cùng không gian định danh `project + segment + type`.
- Xác nhận migration nullable trước khi commit.
