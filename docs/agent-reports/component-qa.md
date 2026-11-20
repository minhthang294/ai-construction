# QA độc lập — nhập danh mục cấu kiện

## Phạm vi

- Chỉ thêm `backend/tests/test_component_synthetic_e2e.py` và báo cáo này. Không sửa test khác, product code, `data/app.db` hay workbook nguồn.
- Test dựng workbook XLSX tổng hợp trong bộ nhớ (5 cấu kiện, 3 liên kết, 18 phân đoạn; vùng `Khu A`, mã `P-01`, `P-02`, `I-40-42`, `B-01`, `B-02`). Không dùng dữ liệu công trình thật.
- Mỗi test dùng SQLite tạm riêng trong `tmp_path`; không đọc/ghi `data/app.db`, storage hay workbook private.
- Full backend suite, frontend test/build, migration round trip, `git diff --check` và kiểm SHA256 template đã chạy lại trên code ổn định sau khi shared-core sửa `reviewed_at` và thêm test. Đây là kết quả chốt QA.
- Không sửa product code, không chạy migration trên DB thật, không commit/push.
- `POST` thủ công cấu kiện đang được shared-core sửa nên QA không sửa file đó và không kiểm endpoint này.

## Kết quả kiểm thử

Lệnh: `..\.venv\Scripts\python.exe -m pytest tests/test_component_synthetic_e2e.py -q` (workdir `backend`)

```
4 passed, 1 warning in 5.31s
```

Cảnh báo duy nhất là `StarletteDeprecationWarning` về `httpx`/Starlette TestClient, không liên quan chức năng.

## Kiểm thử toàn bộ — kết quả chốt

Các lệnh dưới đây chạy trên code hiện tại sau khi shared-core hoàn tất sửa `reviewed_at` và thêm test. Full suite đã bao gồm test mới đó.

Mọi lệnh backend dùng DB và thư mục pytest tạm ngoài repo:

```powershell
$env:DATABASE_URL = "sqlite:///C:/Users/.../Temp/component-qa-.../backend-full.db"
..\.venv\Scripts\python.exe -m pytest -q -rs --basetemp "C:/Users/.../Temp/component-qa-final-.../pytest-temp"
```

Kết quả backend:

```
305 passed, 7 skipped, 1 warning in 53.55s
```

Skip và warning đúng theo output:

```
SKIPPED [1] tests\acceptance\test_exports.py:472: LibreOffice headless is not installed
SKIPPED [1] tests\acceptance\test_exports.py:489: LibreOffice headless is not installed
SKIPPED [1] tests\acceptance\test_exports.py:512: LibreOffice headless is not installed
SKIPPED [1] tests\acceptance\test_exports.py:525: LibreOffice headless is not installed
SKIPPED [1] tests\acceptance\test_exports.py:564: LibreOffice headless is not installed
SKIPPED [1] tests\acceptance\test_exports.py:669: LibreOffice headless is not installed
SKIPPED [1] tests\test_addendum_dod.py:276: Tesseract binary not installed

StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
```

Không có test fail. Bảy skip đều do thiếu công cụ hệ thống (LibreOffice headless, Tesseract), không liên quan danh mục cấu kiện.

Frontend (workdir `frontend`):

```powershell
npm test
npm run build
```

Kết quả `npm test`:

```
Test Files  23 passed (23)
     Tests  133 passed (133)
  Duration  1.40s
```

Kết quả `npm run build`:

```
tsc -b && vite build
✓ 98 modules transformed.
dist/assets/index-DHD2tQ-O.js  512.75 kB │ gzip: 140.56 kB
✓ built in 1.51s
```

Build thành công nhưng có warning chunk lớn hơn 500 kB sau minify; đây là warning, không phải fail.

Migration upgrade/downgrade/upgrade trên DB tạm (workdir `backend`, `DATABASE_URL` trỏ file mới trong thư mục tạm):

```powershell
python -m alembic upgrade head
# chèn một project 'kept' để kiểm dữ liệu còn nguyên
python -m alembic downgrade a7c3e9f2b641
python -m alembic upgrade head
# kiểm project 'kept' và hai bảng structural_components, component_import_batches
```

Output chính:

```
Running upgrade a7c3e9f2b641 -> 170f7a3596cf, component inventory
Running downgrade 170f7a3596cf -> a7c3e9f2b641, component inventory
Running upgrade a7c3e9f2b641 -> 170f7a3596cf, component inventory
roundtrip-ok
```

Project `kept` còn nguyên sau chu trình; hai bảng danh mục tồn tại sau lần upgrade thứ hai. Không chạy trên `data/app.db`.

Kiểm tra whitespace và template (workdir repo root):

```powershell
git diff --check
Get-FileHash -Algorithm SHA256 data/templates/acceptance-original.xlsx
```

Kết quả `git diff --check`:

```
warning: in the working copy of '.gitignore', LF will be replaced by CRLF the next time Git touches it
diff-check-exit=0
```

Không có lỗi whitespace; warning CRLF của `.gitignore` không làm lệnh fail (exit 0).

Kết quả SHA256 template:

```
sha256=391d01c13e50b1fb9cd8c619badb2bcffdbe570eba2014962c91e3eb9c1872ed
expected=391d01c13e50b1fb9cd8c619badb2bcffdbe570eba2014962c91e3eb9c1872ed
match=True
```

Template khớp baseline; không sửa template trong quá trình QA.

## Nội dung đã kiểm

### Preview chỉ đọc

- Preview trả `source_sha256` đúng hash file, 5 candidate, 18 phân đoạn, kiểu cọc/dầm, 2 phạm vi phát sinh, trạng thái `NEEDS_REVIEW`.
- Alias `I40-42` của dầm `I-40-42` được nhận từ chuỗi vị trí; `raw_code` giữ nguyên `I40-42`.
- Sau preview, toàn bộ bảng danh mục (zone, segment, component, alias, work link, repair scope, design group, batch) vẫn rỗng.
- File không phải XLSX hoặc thiếu sheet bị từ chối 422.
- Viewer không được preview (403); engineer không thuộc công trình nhận 404.

### Commit có xác nhận và idempotent

- `reviewed=false` bị 422; preview khác workbook bị 409; base64 không phải file XLSX bị 422 và không ghi DB.
- Commit hợp lệ trả `{components: 5, work_links: 3, segments: 18}`.
- Gửi lại cùng idempotency key và gửi key mới với cùng dữ liệu đều trả cùng kết quả, không nhân đôi cấu kiện/liên kết; có 2 batch và 2 audit `import_reviewed`.
- Dùng lại một key với workbook khác bị 409 do `payload_hash` khác.
- Truy vấn theo `q`, `zone` (chuẩn hóa hoa/thường và khoảng trắng), `type`, `scope`, `segment_id` trả đúng.
- Chi tiết cấu kiện trả mã gốc/chuẩn, nguồn `DANH_MUC`, nhóm thiết kế, phạm vi và dòng DM; cọc nhóm 2 giữ `source_page=8`, dầm không có nhóm.
- Bản ghi commit có `verification=VERIFIED`, `record_origin=SEED_IMPORT`, `created_by`, scope revision 1.

### Phân đoạn 2–18

- Danh sách phân đoạn có đủ 1–18, nhưng mọi phân đoạn 2–18 trả danh sách cấu kiện rỗng. Không cấu kiện nào được tự tạo cho khung phân đoạn.

### Alias, xung đột và đối chiếu thủ công

- Workbook thay đổi nội dung sau lần nhập đầu: preview báo `Existing component requires manual reconciliation`; commit bị 409.
- Thêm dầm mã chuẩn `I40-42` trùng alias đã có: preview báo `Ambiguous component alias` và `Existing component requires manual reconciliation`; commit bị 409.
- Mã cấu kiện trùng trong cùng workbook: `Duplicate segment, component, source ID or work link`; commit bị 409.
- Liên kết trỏ cấu kiện không tồn tại: `Unknown segment or component reference`; commit bị 409.
- Liên kết dùng mã khác mã chuẩn: `Work link code does not match component`; commit bị 409.
- Sau các lần thử lỗi, DB vẫn chỉ có 5 cấu kiện và 1 batch.

### Quyền và cô lập công trình

- Viewer đọc được danh mục/phân đoạn nhưng preview và commit bị 403.
- Engineer là thành viên preview/commit được; `created_by` của cấu kiện là engineer đó.
- Engineer của công trình A không preview được công trình B (404); viewer A không đọc được B (404).
- Danh mục/phân đoạn công trình B rỗng trước khi nhập; chi tiết cấu kiện A qua đường dẫn B trả 404.
- Admin nhập cùng workbook vào B thành công; hai công trình giữ 5 cấu kiện riêng, tổng 10.

## Chưa xử lý / cần rà soát thủ công

- Seed 949 liên kết chỉ trỏ tới 78 dòng DM khác nhau (dòng 6–83), trong khi ghi chú đầu vào nêu 79 dòng công việc thuộc phân đoạn 1. Đây là điểm chưa đối chiếu được; không tạo liên kết thiếu và không sửa số liệu nguồn.
- Test synthetic chỉ kiểm `RepairScope.kind` và `revision`; `reviewed_at` do test mới của shared-core bao phủ. Full suite trên code đã sửa pass.
- Build frontend còn warning chunk `512.75 kB` lớn hơn ngưỡng 500 kB; không phải fail và không thuộc phạm vi sửa của QA.
- Chưa kiểm thử UI bằng trình duyệt hoặc chạy đồng thời nhiều tiến trình trên cùng DB.
- Test không bao phủ `POST` thủ công cấu kiện do shared-core đang thay đổi; không kết luận endpoint đó đã ổn.
- Test không kiểm lưu file nguồn vào storage, hợp nhất nhiều lần nhập có thay đổi nguồn, hay xử lý xung đột đồng thời ngoài idempotency.
