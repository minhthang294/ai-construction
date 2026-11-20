# Site — UI danh mục cấu kiện

Cập nhật: 18/11/2026. Phạm vi: `frontend/src/features/site/` và test tương ứng.

## Changed files

- `frontend/src/features/site/components/ComponentCatalogImport.tsx` (mới)
  - Chọn workbook XLSX, tạo preview, hiển thị counts/conflicts/candidate/work links/segments.
  - Lọc preview theo text, khu, loại, phân đoạn, phạm vi, xác minh danh mục.
  - Component list và work links có phân trang “Hiển thị thêm”/“Hiển thị tất cả”.
  - Xác nhận rõ trước commit; preview gửi nguyên object, không rebuild.
  - Form tạo cấu kiện thủ công: chỉ chọn phân đoạn đã có; loại và phạm vi mặc định trống, bắt buộc chọn.
- `frontend/src/features/site/lib/componentImport.ts` (mới)
  - Type contract preview/list/segment/manual create.
  - Helper filter, gate commit, payload commit, base64, idempotency key.
  - Validate manual create; không tự gán loại/phạm vi, không thêm nguồn/nghiệm thu.
- `frontend/src/features/site/lib/componentImport.test.ts` (mới)
  - 18 test cho filter, conflict gate, payload/`raw_code`, 949 work links, base64, manual create.
- `frontend/src/features/site/lib/api.ts`
  - Thêm `previewComponentImport`, `commitComponentImport`, `createComponent`, `listComponents`, `listSegments` theo `apiFetch`/`ApiError`.
- `frontend/src/features/site/index.ts`
  - Export `ComponentCatalogImport` và type liên quan để app shell gắn.

Agent site không sửa `frontend/src/app`; app shell do Codex cập nhật. Không sửa backend, shared contract, Excel nguồn. Không commit/push.

## Tích hợp

- App shell đã mount `ComponentCatalogImport` ở trang **Cấu kiện** trong `frontend/src/app/App.tsx` (page `components`), truyền `projectId`; key đổi theo project.
- Backend components đã triển khai; đang chờ báo cáo QA trước khi dùng với dữ liệu thật.

## Test và kết quả

```bash
npx tsc --noEmit -p tsconfig.json   # OK
npx vitest run                      # 23 files, 133 tests passed
```

Đã chạy đỏ trước khi implement cho helper filter/commit, `raw_code`, `seed_row`, work-link pagination và validation loại/phạm vi; sau đó xanh.

## Unresolved mappings

- Backend `POST /projects/{p}/components` và các field `raw_code`, `work_links[].seed_row` đã có trong contract; đang chờ báo cáo QA. UI phụ thuộc đúng contract này.
- UI đã được app shell mount tại trang Cấu kiện; không còn là việc cần Codex gắn.
- UI không phân quyền theo role; viewer vẫn thấy form nhưng backend trả 403.
- Chưa có React Testing Library/E2E; chưa test render thực tế.
- Form thủ công chỉ dùng phân đoạn từ `GET /segments`; nếu chưa import workbook có phân đoạn thì form bị khoá.
- Preview chỉ hiển thị/duyệt components; work links không có bộ lọc riêng, chỉ phân trang.
- Preview hiển thị `verification` như trạng thái xác minh danh mục; không phải tiến độ hay nghiệm thu.
- Không ghi `AcceptanceRequest/Record`, `WorkItem.status` hay tiến độ từ màn này.

## Manual review

1. Import workbook thật (130 cấu kiện / 949 liên kết / 18 phân đoạn): counts, conflicts và filter khớp.
2. Bấm “Hiển thị tất cả” work links, đối chiếu dòng cuối và `seed_row` trước khi commit.
3. Commit thử khi còn conflict phải bị chặn; retry lỗi mạng phải dùng lại idempotency key.
4. Form thủ công: chưa chọn loại/phạm vi phải báo lỗi; tạo trùng mã phải hiện lỗi 409; bản ghi mới hiện “Chờ duyệt”, không có nguồn/bản vẽ.
5. Kiểm tra mobile-first: chọn file, bảng preview, nút phân trang và form nhập tay.
6. Kiểm tra viewer nhận 403 khi commit/tạo, nhưng vẫn đọc được danh mục.
