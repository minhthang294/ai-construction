# Shared core report: repair scope review, stages, progress (2026-11-18)

## Phạm vi

Chỉ sửa shared core, migration và hợp đồng API. Không sửa `backend/app/site/`, `backend/app/acceptance/`, frontend, workbook, DB thật; không commit/push.

| File | Thay đổi |
| --- | --- |
| `backend/app/core/component_models.py` | Thêm `StageDefinition`, `ComponentStage`, `ProgressEvent`; bảng tiến độ không có cột nghiệm thu |
| `backend/app/core/component_router.py` | Thêm đề xuất/duyệt `RepairScope`, định nghĩa bước, gắn bước, append/đọc `ProgressEvent`; detail trả stages + progress; kiểm quyền và audit |
| `backend/alembic/versions/b3e5f7a9c1d2_component_repair_progress.py` | Tạo `component_stage_definitions`, `component_stages`, `component_progress_events`, `component_progress_batches`; downgrade đầy đủ |
| `backend/alembic/versions/c4f6a8b0d2e3_component_acceptance_links.py` | Tạo `component_acceptance_links` theo yêu cầu acceptance; có check constraint và unique index biểu thức |
| `backend/tests/test_component_progress.py` | Test quyền, project scope, revision/duyệt scope, stage, append-only, validation, audit, tách nghiệm thu |
| `backend/tests/test_component_migration.py` | Test migration mới: upgrade → dữ liệu cũ còn nguyên → downgrade → upgrade |
| `docs/API_CONTRACTS.md` | Công bố route và ngữ nghĩa trước khi tích hợp |

## Hợp đồng đã công bố

- `GET/POST /projects/{p}/stage-definitions?type=`: member đọc, `project_manager|engineer` tạo; mã chuẩn hóa hoa, unique theo project + loại + mã.
- `POST /projects/{p}/components/{id}/repair-scopes`: tạo `NEEDS_REVIEW`, `revision` tự tăng riêng theo component + kind.
- `POST .../repair-scopes/{scope_id}/review`: chỉ `project_manager`, chỉ scope `NEEDS_REVIEW`; `VERIFIED` bắt buộc `approval_reference` với `ADDITIONAL_SCOPE`; ghi `reviewed_by/reviewed_at` + audit.
- `POST .../stages`: gắn một định nghĩa bước với cấu kiện và một `RepairScope` cùng cấu kiện; không có bước mặc định.
- `GET/POST .../progress-events`: append-only, không có `PATCH`/`DELETE`; `event_date` do người dùng nhập; `IN_PROGRESS|COMPLETED|BLOCKED`; `evidence_refs[]` là chuỗi tham chiếu.
- `ProgressEvent` dùng chung bảng `component_progress_events` với bulk endpoint của site; site giữ idempotency bulk ở `component_progress_batches`.
- Tiến độ và nghiệm thu tách biệt: core không đọc/ghi `AcceptanceRequest/Record`, không suy ra nghiệm thu từ status thi công.

## Kiểm thử

- `pytest tests/test_component_progress.py tests/test_component_migration.py -q` → **4 passed**.
- Bộ component + site_report + acceptance links:
  `pytest tests/test_component_import.py tests/test_component_conflicts.py tests/test_component_seed_preview.py tests/test_component_migration.py tests/test_component_synthetic_e2e.py tests/test_component_progress.py tests/site_report tests/acceptance/test_component_links.py -q`
  → **91 passed**.
- Toàn bộ backend: `pytest -q` → **332 passed, 7 skipped**.
- `alembic upgrade head` trên SQLite tạm: OK. `alembic check` chỉ còn 2 lệch có sẵn từ trước, ngoài sprint này: index unique `acceptance_records` và index `engineering_ai_documents`; index biểu thức `uq_component_acceptance_link` bị SQLite bỏ qua khi reflection (đã tạo trong migration).
- Không chạm `data/app.db`; mọi test/migration dùng DB tạm.

## Chưa xử lý / cần review thủ công

| Vấn đề | Ghi chú |
| --- | --- |
| Append đơn lẻ không có idempotency | Site bulk có `idempotency_key`; endpoint theo cấu kiện chưa có. Thêm nếu mobile retry là yêu cầu. |
| Một định nghĩa bước gắn nhiều phạm vi | Đã cho phép (`component_id + stage_definition_id + repair_scope_id`). Site bulk đã yêu cầu `stage_selections[]` và không tự chọn bước đầu tiên. |
| `ProgressEvent.created_by` nullable | Site bulk đang truyền `""` khi thiếu actor; nếu bật FK enforcement cần sửa phía site. |
| `evidence_refs[]` | Core kiểm project + ảnh/document/page; site bulk đã gọi validator ở preview và commit. |
| `component_acceptance_links` | Migration đã thêm theo yêu cầu acceptance; core không đọc/ghi bảng này. |
| Chưa có UI cho summary/reconciliation | Hai route shared đã có; frontend thuộc site/app shell. |

## Đề nghị review

1. `approval_reference` bắt buộc khi duyệt `VERIFIED` cho `ADDITIONAL_SCOPE` có đúng quy trình không.
2. Chỉ `project_manager` được duyệt phạm vi (kỹ sư chỉ đề xuất) có đúng không.
3. Tên audit: `stage_definition_created`, `repair_scope_proposed`, `repair_scope_reviewed`, `component_stage_created`, `component_progress_recorded`.
4. Từ vựng status `IN_PROGRESS|COMPLETED|BLOCKED` (không dùng `DONE`) đã thống nhất với site.
