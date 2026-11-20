# Rà soát manual POST /components

Ngày: 18/11/2026. Phạm vi: `backend/app/core/component_router.py`, `component_models.py`,
migration `170f7a3596cf`, `component_seed.py`, test component. Read-only, không sửa code.

## Findings (4)

1. **Low — Revision ID đã dùng lại trong lúc phát triển; chỉ ảnh hưởng DB thử, không phải DB người dùng**
   - Vị trí: `backend/alembic/versions/170f7a3596cf_component_inventory.py:15` (vẫn `170f7a3596cf`)
     với các cột mới `name_key` (dòng 50), `record_origin`/`created_by`/`created_at` (76-78),
     `reviewed_by/at` (106-107).
   - Bối cảnh: migration chưa commit, chưa phát hành; chỉ các DB SQLite tạm tạo khi phát triển
     từng được stamp `170f7a3596cf` (thiếu `record_origin/created_by/created_at`).
     `data/app.db` vẫn ở `a7c3e9f2b641`.
   - Hệ quả: nếu ai đó dùng lại đúng DB thử đó, `alembic upgrade head` là no-op và app báo
     `no such column: structural_components.record_origin`; import thiếu `name_key`.
   - Hướng xử lý: khi chuẩn bị commit, xác nhận không có DB dùng chung nào đã stamp revision này;
     nếu có, thêm revision mới `add_column` + backfill thay vì sửa tiếp file cũ. Người phát triển
     chỉ cần bỏ DB thử của chính mình. Không xoá/tác động DB người dùng.
   - Test thiếu: migration chỉ assert bảng tồn tại (`backend/tests/test_component_migration.py:23-25`);
     nên assert các cột/constraint mới.

2. **Low — Cảnh báo UX/API: `GET ?q=` không lọc `type` nên có thể trả nhiều dòng khi alias trùng khác loại**
   - Vị trí: unique theo `project + segment + type` (`component_models.py:42,61`), kiểm trùng khi tạo
     manual cũng theo `type` (`component_router.py:276-284`); `GET /components?q=` không lọc type
     (`component_router.py:348-351`).
   - Đây là hành vi đúng theo yêu cầu: mã/alias được unique theo loại, trùng khác loại **không được
     tự ghép**. Không phải lỗi của POST.
   - Vấn đề còn lại: khi dầm `X1` và cọc alias `X1` cùng segment, `?q=X1` trả 2 dòng mà không nêu
     mơ hồ; người dùng có thể chọn sai cấu kiện.
   - Hướng xử lý: trả kèm cờ/`type` trong kết quả để UI phân biệt, hoặc gợi ý truyền `type` khi khớp
     nhiều dòng. Không đề xuất cấm hay gộp alias.
   - Test thiếu: ca `?q` trùng khác loại trả đủ 2 dòng kèm thông tin loại.

3. **Medium — Manual có `source = NULL` nhưng không có đường hoà giải với seed**
   - Vị trí: `component_models.py:50-52`; response `component_router.py:311`;
     preview so `source_hash` (`:139-140`); commit chặn (`:199-200`). Test khẳng định NULL:
     `test_component_import.py:169,187`.
   - Ca cụ thể: mã nhập tay trùng mã seed → preview "requires manual reconciliation",
     commit 409; không API gắn provenance hay thay thế.
   - Sửa: thêm bước reconcile (chọn manual/seed, ghi `record_origin` + source) hoặc trả conflict
     code riêng để UI hướng dẫn.
   - Test thiếu: manual + seed trùng mã/segment rồi thử reconcile.

4. **Medium — Không thêm được phạm vi sửa chữa thứ hai cho cấu kiện đã có**
   - Vị trí: schema cho nhiều scope (`component_models.py:72`), design nói nhiều phạm vi
     (`docs/2026-11-18-component-inventory-design.md:9`); nhưng POST trùng canonical → 409
     (`component_router.py:276-284`), import 409 khi scope khác (`:201-208`), không có endpoint scope.
   - Hệ quả: cọc đã có `DESIGN_SCOPE` không thêm được `ADDITIONAL_SCOPE` qua API.
   - Sửa: khi cấu kiện đã tồn tại và chỉ khác scope, thêm `RepairScope` revision mới (200)
     hoặc thêm endpoint scope riêng.
   - Test thiếu: ca thêm scope cho cấu kiện đã tồn tại.

## Đã kiểm tra đúng

- Project-scoped: segment ngoài project → 404 (`component_router.py:263-266`, test `:163`);
  viewer → 403 (test `:162`).
- Transaction: `IntegrityError` → rollback + 409 (`:301-303`); race canonical được DB unique chặn
  (test `:177-184`).
- Trạng thái duyệt: manual ghi `NEEDS_REVIEW`; import sau fix ghi `VERIFIED` kèm
  `reviewed_by=actor.id`, `reviewed_at=now()` trên `RepairScope` (`component_router.py:225,228-229`).
  `StructuralComponent` không có cột `reviewed_by`; người duyệt của bản import suy ra từ batch commit
  + `AuditLog` và `created_by`.
- Manual giữ audit `component_created` (`:295-299`); `source` NULL trả đúng ở cả create và detail.
