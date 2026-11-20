# Integration gate — 2026-11-18

Phạm vi: chạy gate toàn bộ, chỉ sửa shared core/migration/contract và app shell. Không sửa module site/acceptance/engineering, không commit/push, không chạm `data/app.db`.

## Kết quả gate

| Gate | Lệnh | Kết quả |
| --- | --- | --- |
| Backend | `pytest -q` với `DATABASE_URL` SQLite tạm | **345 passed, 7 skipped** |
| Frontend test | `npm test` | **25 file, 146 test passed** |
| Frontend build | `npm run build` | **exit 0**; cảnh báo chunk 544 kB (>500 kB), không lỗi |
| Alembic round trip | `upgrade head → downgrade base → upgrade head` trên DB tạm | **pass**, `current = c4f6a8b0d2e3 (head)` |
| Migration mới | `upgrade → giữ dữ liệu cũ → downgrade → upgrade` | **2 passed** |
| `alembic check` | so metadata với DB tạm | còn **2 lệch có sẵn từ trước**: unique index `acceptance_records` và index `engineering_ai_documents`; không do sprint này |

## App shell

Không cần sửa `frontend/src/app/App.tsx`: trang **Cấu kiện** đã mount `ComponentCatalogImport`, và component này đã có tab **Tiến độ** dùng `ComponentProgressPanel`. Không có UI cho summary/reconciliation; hai route này là backend contract.

## Route shared bổ sung

- `GET /projects/{p}/progress/summary`: đếm trên cấu kiện `VERIFIED`; 4 trạng thái thi công theo event mới nhất; liên kết/xác nhận nghiệm thu; hai tỷ lệ độc lập.
- `GET /projects/{p}/reconciliation/issues`: `ACCEPTANCE_WITHOUT_PROGRESS`, `WORK_WITHOUT_ACCEPTANCE`, `MISSING_SOURCE`, `UNVERIFIED_COMPONENT`, `DUPLICATE_OR_AMBIGUOUS_CODE`, `ACCEPTANCE_BEFORE_PROGRESS`; trả `issues[]` + `counts`.
- Test: `backend/tests/test_component_insights.py` → **2 passed** (project scope, member read, đúng counts/ratios).

## Sửa theo review

| Vấn đề | Cách sửa | Test |
| --- | --- | --- |
| Cùng một stage definition phải dùng lại được cho scope khác | Unique đổi thành `(component_id, stage_definition_id, repair_scope_id)` ở model + migration | `test_component_progress` tạo 2 scope, cùng definition, 2 stage id khác nhau; trùng cùng scope vẫn `409`; migration test chèn 2 scope và chặn trùng |
| Evidence phải thuộc project | Thêm `app/core/evidence.py`: ảnh `<id>`/`photo:`, `document:`, `page:`; sai project/không tồn tại `404`, ảnh chưa xác nhận/sai định dạng `422` | test ảnh hợp lệ, ảnh project khác `404`, ảnh chưa xác nhận `422`, ref rác `422` |

## DoD Sprint 1–5

| # | Hạng mục | Trạng thái | Bằng chứng |
| --- | --- | --- | --- |
| 1 | Import 2 lần: 130 cấu kiện, không trùng | Pass | `test_component_import` |
| 2 | 45 Nhóm 2, 39 Nhóm 3, 26 cọc + 8 dầm phát sinh chưa gán nhóm | Pass | Assertion mới trong `test_component_import`; 110 cọc, 20 dầm, 34 phát sinh |
| 3 | 949 mapping, giữ raw string + dòng | Pass | `test_component_import`, `test_component_seed_preview` |
| 4 | `I40-42` và `I-40-42` cùng cấu kiện, giữ raw | Pass | `test_component_import` |
| 5 | Phân đoạn 2–18 không sinh cấu kiện giả | Pass | `test_component_import`, `test_component_synthetic_e2e` |
| 6 | Thi công không đổi nghiệm thu; PYC/BBNT không tự "đã nghiệm thu" | Pass | `test_component_progress` (không ghi `AcceptanceRequest/Record`), acceptance suite |
| 7 | Một BBNT nhiều cấu kiện, một cấu kiện nhiều BBNT | Pass | `tests/acceptance/test_component_links.py` trong full suite |
| 8 | Journal chỉ dùng event đã duyệt, không tạo nghiệm thu giả | Pass | `tests/site_report` trong full suite |
| 9 | Audit, permission, E2E, migration/backup, không phá template | Pass | Full suite + round trip; test audit `repair_scope_*`, `stage_*`, `component_progress_recorded` |
| 10 | Report changed files/tests/unresolved | Pass | Report này + `component-progress-core.md` |

## Lỗi module khác

Không còn failure trong lần chạy cuối. Hai lỗi tạm thời trước đó ở `tests/site_report` (thứ tự component và quyền route journal) đã được module site sửa; gate không can thiệp.

## Tồn đọng / rủi ro

1. `alembic check` còn 2 lệch schema có sẵn (acceptance/engineering), ngoài phạm vi sprint.
2. Chưa có UI summary/reconciliation; chưa có test render/E2E trình duyệt cho tab tiến độ.
3. Frontend bundle 543 kB, chỉ là cảnh báo build.

## Bulk progress remediation

- `backend/app/site/progress.py`: thêm `stage_selections[]`; preview trả `stage_options`, `stage_ambiguous`, `ambiguous_stage_component_ids`, `invalid_stage_component_ids`; không tự chọn bước đầu tiên khi một định nghĩa gắn nhiều phạm vi. Commit thiếu lựa chọn hoặc lựa chọn sai trả `409`; preview/commit dùng cùng selection. Audit ghi `stage_ids`.
- Evidence: gọi `app.core.evidence.validate_evidence_refs` ở cả preview và commit; ref sai project/không tồn tại `404`, ảnh chưa xác nhận/sai định dạng `422`.
- Frontend: `ComponentProgressPanel` hiện select phạm vi cho từng cấu kiện mơ hồ, chặn preview khi chưa chọn, đổi lựa chọn thì huỷ preview; preview và lưu dùng chung `stage_selections`.
- Test: `tests/site_report/test_component_progress.py` **8 passed** (thêm repeated scope + foreign/unconfirmed evidence); full backend **345 passed, 7 skipped**; frontend **25 file / 146 test**, build exit 0.
