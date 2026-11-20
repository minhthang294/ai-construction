# Thiết kế tích hợp: liên kết N–N cấu kiện/bước/phạm vi với PYC và BBNT

Ngày: 18/11/2026. Phạm vi: acceptance. Trạng thái: **đã triển khai phía acceptance; chờ migration do coordinator**.

## Hợp đồng shared đã landed

Trong lúc làm, shared core đã thêm:

- `StageDefinition`: `project_id`, `component_type`, `code`, `name`, `position`; unique theo project + loại + mã.
- `ComponentStage`: `component_id`, `stage_definition_id`, `repair_scope_id`, `created_by`, `created_at`; unique theo component + định nghĩa; bước luôn gắn đúng một `RepairScope` của cấu kiện.
- `RepairScope`: đã có sẵn; `ComponentStage.repair_scope_id` là nguồn xác định phạm vi của bước.

`ComponentAcceptanceLink` do acceptance sở hữu trong `backend/app/acceptance/models.py`, không sửa core.

## Model đã thêm

`ComponentAcceptanceLink` (`component_acceptance_links`):

| Cột | Ghi chú |
| --- | --- |
| `id` | UUID |
| `project_id` | Bắt buộc, index |
| `component_id` | FK `structural_components.id`, bắt buộc, index |
| `stage_id` | FK `component_stages.id`, nullable, index |
| `scope_id` | FK `component_repair_scopes.id`, nullable, index |
| `request_id` | FK `acceptance_requests.id`, nullable, index |
| `record_id` | FK `acceptance_records.id`, nullable, index |
| `created_by`, `created_at` | Người duyệt và thời điểm |

Ràng buộc:

- `CHECK (request_id IS NULL) <> (record_id IS NULL)`: một dòng chỉ thuộc PYC **hoặc** một BBNT revision.
- Unique index biểu thức `(project_id, component_id, coalesce(stage_id,''), coalesce(scope_id,''), coalesce(request_id,''), coalesce(record_id,''))`. Dùng `text("coalesce(...)")` vì SQLite coi NULL là khác nhau; không dùng `UniqueConstraint` thường cho các cột nullable.
- Không lưu bản sao nội dung PYC/BBNT hay kết luận nghiệm thu trong bảng liên kết.

## API đã thêm

| Method | Path | Quyền |
| --- | --- | --- |
| `GET` | `/projects/{p}/acceptance-requests/{id}/component-links` | member |
| `PUT` | `/projects/{p}/acceptance-requests/{id}/component-links` | editor |
| `GET` | `/projects/{p}/acceptance-records/{id}/component-links` | member |
| `PUT` | `/projects/{p}/acceptance-records/{id}/component-links` | editor |

Body của `PUT` (thay thế toàn bộ, không cộng dồn):

```json
{
  "reviewed": true,
  "links": [
    {"component_id": "...", "stage_id": "...", "scope_id": "..."}
  ]
}
```

- `reviewed` là `Literal[True]`; thiếu hoặc `false` trả `422`.
- Response là mảng link đã lưu, sắp xếp theo `(component.canonical_code, stage.position, scope.revision, link.id)`.
- `stage_id` và `scope_id` tùy chọn, nhưng nếu có thì phải thuộc đúng `component_id`; nếu cả hai có thì `stage.repair_scope_id` phải bằng `scope_id`.

## Kiểm tra trước khi ghi

Toàn bộ payload được kiểm tra trước khi thay đổi dữ liệu; một dòng sai thì không ghi dòng nào:

1. Resolve PYC/BBNT theo `project_id`; sai project trả `404` như các route hiện có.
2. BBNT đã `confirmed` trả `409 record_confirmed`.
3. Resolve toàn bộ `component_id` theo `project_id`. Thiếu hoặc khác project trả `404`.
4. Nếu có `stage_id`: phải tồn tại và `stage.component_id == component_id`; sai trả `409 stage_component_mismatch`.
5. Nếu có `scope_id`: phải tồn tại và `scope.component_id == component_id`; sai trả `409 scope_component_mismatch`.
6. Nếu có cả hai: `stage.repair_scope_id == scope_id`; sai trả `409 stage_scope_mismatch`.
7. Link trùng khóa được giữ nguyên, không tạo dòng mới; link không còn trong payload bị xóa.
8. Ghi audit `component_links_replaced` với target, số link và danh sách khóa đã sắp xếp.

Không nhận `component_code` tự do. Không tự tạo `ComponentStage`, `RepairScope`, cấu kiện hay BBNT.

## Bất biến nghiệp vụ

### Kết quả tất định

- `PUT` cùng payload là idempotent: cùng tập link, cùng thứ tự, cùng `id`, không nhân đôi.
- Link **không** đi vào cell Excel, không đổi preview/export PYC/BBNT, không gọi AI, không ghi workbook DM. Export tiếp tục chỉ phụ thuộc dữ liệu PYC/BBNT đã lưu.
- Không backfill từ `ComponentWorkLink`, `WorkItem`, dòng DM, ngày seed, ảnh hay chat.

### Xác nhận của con người

- Chỉ editor gọi `PUT` với `reviewed: true` mới tạo/thay link.
- Link không đổi `status`, `result`, `confirmer_id`, `confirmed_at`, checklist hay kết luận. BBNT vẫn `draft`/`result=null` cho đến khi gọi `/confirm` hiện có.
- BBNT đã `confirmed` là bất biến: mọi `PUT` link trả `409 record_confirmed`.
- Tạo revision BBNT **không** tự copy link. Revision cũ giữ nguyên link; revision mới cần `PUT` riêng.
- Tạo BBNT từ PYC **không** tự copy link PYC.
- Xóa PYC có `force` xóa link PYC và link của các BBNT liên quan; không để orphan.

## Test đã viết

`backend/tests/acceptance/test_component_links.py` chạy trên SQLite in-memory, dùng component/stage/scope seed tổng hợp. Các test kiểm:

1. `reviewed=false` bị `422`; link không tự xác nhận BBNT; preview không đổi.
2. `PUT` lặp lại cho cùng kết quả và cùng `id`; thứ tự theo mã cấu kiện.
3. Một BBNT nhiều cấu kiện, một cấu kiện nhiều BBNT.
4. Link PYC và link BBNT độc lập.
5. Cấu kiện/scope/stage khác project, scope/stage không thuộc cấu kiện bị từ chối và không ghi một phần.
6. Stage phải khớp đúng scope đã chọn.
7. BBNT đã xác nhận từ chối đổi link (`409 record_confirmed`).
8. Revision mới không thừa kế link; sao chép chỉ khi `reviewed: true`.
9. Work item và dòng DM không tự sinh link.
10. `PUT` thay thế đúng tập đã duyệt, không cộng dồn.
11. Record không tồn tại trả `404`.
12. Xóa PYC có `force` xóa cả link PYC và link của BBNT liên quan.
13. Một cấu kiện liên kết được nhiều `RepairScope` (`DESIGN_SCOPE` + `ADDITIONAL_SCOPE`) với đúng stage và scope từng dòng.
14. Link sống qua bước PYC `submitted` và BBNT `confirmed`; sau xác nhận BBNT bị đóng băng.
15. Link không đổi SHA-256 template; preview và export BBNT sau xác nhận vẫn dùng đúng template đó.

Kết quả: `15 passed`. Acceptance suite: `102 passed, 6 skipped` (skip do thiếu LibreOffice). Site progress đọc link: `tests/site_report/test_component_progress.py` `6 passed` (PENDING/APPROVED, count BBNT đã xác nhận). Toàn bộ backend: `338 passed, 7 skipped`. Migration `c4f6a8b0d2e3` đã chạy `upgrade -> downgrade -> upgrade` trên SQLite tạm; unique index biểu thức có mặt đúng.

## Remaining shared gaps

1. **`docs/API_CONTRACTS.md` chưa có route link.** Bảng `component_acceptance_links` được nhắc trong phần progress, nhưng chưa công bố `GET/PUT /acceptance-requests/{id}/component-links` và `.../acceptance-records/{id}/component-links`, payload `{reviewed, links[]}`, quyền editor/member và mã lỗi. Coordinator cần cập nhật shared contract.
2. **`docs/DATA_MODEL.md` chưa có `ComponentAcceptanceLink`.** Model nằm ở acceptance, migration `c4f6a8b0d2e3` đã khớp model; shared data model cần ghi nhận.
3. **Site đọc trực tiếp model acceptance.** `app.site.progress._acceptance_map` import `app.acceptance.models.ComponentAcceptanceLink`; nếu module acceptance không có, site trả `NOT_LINKED` thay vì báo lỗi. Hoạt động đúng nhưng là coupling chéo module; nên có read contract/service ổn định nếu tách deploy.
4. **Progress chỉ tổng hợp theo cấu kiện, không theo stage/scope.** Một BBNT đã xác nhận cho bất kỳ scope nào cũng làm cả cấu kiện `APPROVED`/`CONDITIONAL`/`REJECTED`. Cần quyết định nghiệp vụ nếu muốn trạng thái nghiệm thu theo từng phạm vi.
5. **BBNT đã xác nhận không thể thêm link.** Confirm payload hiện không có link; nếu người dùng quên link trước khi confirm, bản ghi vĩnh viễn không có link và progress vẫn `NOT_LINKED`. Cần quyết định: chặn confirm khi chưa link, hoặc cho phép link sau confirm với quyền confirmer + audit.
6. **Chưa chặn scope `NEEDS_REVIEW`/`REJECTED`.** API chỉ kiểm tra scope thuộc cấu kiện; không yêu cầu `RepairScope.verification == VERIFIED`. Nếu nghiệm thu chỉ được gắn với phạm vi đã duyệt, cần thêm rule và test.
7. **`stage_id`/`scope_id` đang optional.** Link chỉ có `component_id` vẫn hợp lệ; progress coi là PENDING/confirmed. Cần chốt có bắt buộc stage/scope cho từng loại PYC/BBNT hay không.
8. **Chưa có API nhìn từ phía cấu kiện.** Chỉ có route từ PYC/BBNT; component detail của core không trả link acceptance. Site đọc DB trực tiếp. Nếu UI cần hiển thị "PYC/BBNT liên quan" từ cấu kiện, cần route đọc hoặc mở rộng detail.
9. **Chưa có UI acceptance cho link.** Chưa có màn hình chọn cấu kiện/stage/scope khi lập PYC/BBNT.
10. **Unique index biểu thức bị SQLite reflection bỏ qua.** Migration `c4f6a8b0d2e3` tạo đúng `uq_component_acceptance_link`; `alembic check` không thấy index này do giới hạn reflection. Không phải lỗi runtime, nhưng cần biết khi autogenerate.
11. **Audit action chưa có trong shared contract.** Acceptance ghi `component_links_replaced`; nếu có chuẩn audit chung cần bổ sung tên này.

## Việc cần Codex / coordinator

1. Migration `component_acceptance_links` đã có (`c4f6a8b0d2e3`), khớp model. Chỉ cần xác nhận đã áp dụng cho DB đích; acceptance không sửa `backend/alembic`.
2. Bổ sung route/payload link và `ComponentAcceptanceLink` vào `docs/API_CONTRACTS.md` / `docs/DATA_MODEL.md`.
3. Chốt các quyết định ở mục Remaining shared gaps 4-7 (rollup theo scope, link sau confirm, scope phải VERIFIED, stage/scope bắt buộc).
4. Nếu shared đổi `ComponentStage` (ví dụ bỏ `repair_scope_id` hoặc đổi unique), cập nhật service và test tương ứng.
