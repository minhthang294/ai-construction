# Site Report Agent Report

## Vòng 13 — ghi tiến độ nhiều công tác trong ngày (backend)

Cập nhật: 20/11/2026. Phạm vi thay đổi: `backend/app/site/progress.py`, `backend/tests/site_report/test_component_progress.py` và file báo cáo này. Không sửa shared core, migration, module agent khác, frontend, `data/app.db`, dữ liệu dùng chung hay Excel nguồn. Không commit/push/deploy. Giữ nguyên các thay đổi suy luận tiến độ (`progress_inference.py`, import và lời gọi `apply_inferred_progress`) đã có trong `progress.py`.

### Chức năng đã hoàn thành

- **`POST /api/v1/projects/{p}/progress/daily-preview`** nhận `{event_date, lines:[...]}`. Mỗi dòng được kiểm bằng chính `preview_bulk` hiện có, trả đúng dữ liệu xem trước theo dòng (`components`, `stage_options`, `stage_id`, `missing_*`, `warnings`, `can_commit`, `count`, `ready_count`) kèm `line_index`, `group_quantity`, `group_unit`. Endpoint chỉ đọc, không ghi DB.
- **`POST /api/v1/projects/{p}/progress/daily`** nhận thêm `reviewed: true` và `idempotency_key`. Trả `{created, lines}`; `created` là tổng số event, mỗi dòng là kết quả ghi của dòng đó.
- **Một transaction thật sự**: toàn bộ dòng được xem trước/kiểm tra trước khi ghi; sau đó mỗi dòng gọi `commit_bulk(..., commit=False)` để dùng lại đúng logic kiểm/ghi cũ. Chỉ một `db.commit()` ở cuối. Mọi lỗi giữa các dòng (kể cả lỗi giả lập ở dòng thứ hai) đều `rollback`, không còn event/batch/audit dở dang.
- **Chống trùng bước giữa các dòng**: tập `stage_id` đã phân giải được gom qua tất cả các dòng. Trùng ở preview làm `can_commit=false` và thêm cảnh báo; trùng ở commit trả `409`. Kiểm tra lại ngay sau khi mỗi dòng ghi để chặn trường hợp dữ liệu đổi giữa preview và commit.
- **Khối lượng cấp nhóm không nhân bản**: `group_quantity`/`group_unit` chỉ nằm trong `result_json` của batch ngày và audit `component_progress_daily_recorded`; event của từng cấu kiện luôn có `quantity=null`, `unit=null`. Giá trị `0` được giữ là `0`, không bị đổi thành `null`.
- **Idempotency theo cả yêu cầu**: hash toàn bộ payload (trừ `reviewed`/`idempotency_key`) lưu ở batch ngày. Retry cùng payload trả nguyên kết quả đã lưu, không tạo thêm event; cùng key nhưng payload khác trả `409`.
- **Strict date**: `event_date` là ngày lịch sử dụng chung cho mọi dòng, từ chối ngày tương lai theo `Asia/Ho_Chi_Minh` và từ chối định dạng không phải `YYYY-MM-DD` (422).
- **Giới hạn tải**: tối đa 50 dòng mỗi lần và 500 cấu kiện cộng dồn; vượt trả 422. Mỗi dòng vẫn giữ giới hạn 500 `component_ids`/`stage_selections` và tối đa 500 lựa chọn bước.
- **Project-scoped**: dependency `require_site_editor` cho cả preview/commit; component, stage definition và stage selection được kiểm trong project qua `preview_bulk`/`commit_bulk`. Cấu kiện ngoài project làm preview `can_commit=false`, commit `409`, không ghi dữ liệu.
- **Không đổi hành vi API cũ**: `preview_bulk`/`commit_bulk` vẫn như trước; `commit_bulk` chỉ thêm tham số keyword `commit=True` mặc định. `bulk-preview`/`bulk` giữ nguyên route, payload, mã lỗi và kết quả.
- Không tạo/sửa acceptance, không suy ra nghiệm thu, không ghi đè ảnh gốc, không tự gửi Zalo.

### File thay đổi

- `backend/app/site/progress.py`: model daily, helper dùng chung cho validate `component_ids`/`stage_selections`, `preview_daily`, `commit_daily`, hai route mới, tham số `commit` của `commit_bulk`.
- `backend/tests/site_report/test_component_progress.py`: thêm 6 test daily (preview/scoping, trùng bước, ghi + nhóm + retry, rollback, stage selection, date/cap).
- `docs/agent-reports/site-report.md`: mục này.

### API / model cần dùng

- `POST /projects/{p}/progress/daily-preview` → `{can_commit, lines:[ProgressPreview + line_index/group_quantity/group_unit], warnings}`.
- `POST /projects/{p}/progress/daily` → `{created, lines:[ProgressSaveResult + line_index/stage_definition_id/group_quantity/group_unit]}`.
- Dùng lại bảng hiện có `component_progress_events` và `component_progress_batches` (`SiteProgressBulkBatch`). Batch ngày dùng đúng `idempotency_key` của người gọi; các batch nội bộ của từng dòng dùng key dẫn xuất `daily-<hash>-<line_index>`.
- Đọc `StageDefinition`, `ComponentStage`, `StructuralComponent`, `ProgressEvent` từ shared core; ghi audit qua `AuditLog`. **Không cần model hay migration mới**.
- Frontend mobile cho luồng này: xem **Vòng 13b** bên dưới (`DailyProgressPanel` + helper/tests).

### Kiểm thử đã chạy

Tất cả lệnh đặt `DATABASE_URL` trỏ SQLite tạm; không chạy migration, không mở/ghi `data/app.db`.

```bash
cd backend
$env:DATABASE_URL="sqlite:///$env:TEMP/site-report-daily2.db"
..\.venv\Scripts\python.exe -m pytest tests/site_report/test_component_progress.py -q
# 15 passed

$env:DATABASE_URL="sqlite:///$env:TEMP/site-report-full.db"
..\.venv\Scripts\python.exe -m pytest tests/site_report -q
# 92 passed

$env:DATABASE_URL="sqlite:///$env:TEMP/site-report-root.db"
..\.venv\Scripts\python.exe -m pytest tests/test_component_progress.py tests/test_dap_stage_order.py -q
# 4 passed
```

Test daily bao phủ: preview không ghi DB và cấu kiện ngoài project; trùng `stage_id` giữa hai dòng bị chặn ở preview và commit; `group_quantity` 12.5 và `0` chỉ nằm ở batch/audit, event null; retry cùng key trả cùng kết quả, key cũ payload đổi trả 409; rollback toàn bộ khi dòng thứ hai lỗi sau khi dòng đầu đã ghi tạm; `stage_selections` mơ hồ được dùng đúng; ngày tương lai/định dạng sai và vượt 50 dòng/500 cấu kiện trả 422.

**Chưa kiểm**: DB production/shared, dữ liệu DAP thật, đồng thời nhiều request trên nhiều process, UI mobile và E2E frontend. Test dùng SQLite in-memory qua fixture và SQLite tạm qua `DATABASE_URL`.

### Phụ thuộc / tích hợp

- Dùng FastAPI, Pydantic v2, SQLAlchemy sẵn có; không thêm dependency.
- `app/site/router.py` tự gắn `progress.router`; không cần sửa shared router.
- Idempotency key dùng chung không gian `project_id + idempotency_key` với `/progress/bulk` (ràng buộc cũ của `component_progress_batches`). Dùng lại cùng key cho hai endpoint khác payload sẽ trả 409; client nên tạo key riêng cho từng thao tác.
- Nếu frontend cần hiển thị “khối lượng nhóm”, đọc `group_quantity`/`group_unit` từ response dòng hoặc từ batch ngày; không lấy từ event cấu kiện.

### Unresolved

- UI mobile-first cho nhập nhiều công tác trong một ngày nằm ở **Vòng 13b** (agent frontend); vòng backend này không chạy test DOM/E2E với UI đó.
- Chặn ngày tương lai là quyết định của endpoint daily. Nếu nghiệp vụ cần ghi kế hoạch ngày tương lai, dùng `next_day_plans`, không nới validator này khi chưa có yêu cầu.
- Giới hạn 50 dòng/500 cấu kiện là hằng số trong `progress.py`; cần điều chỉnh nếu công trình thực tế vượt.
- Trên SQLite, hai request ghi đồng thời có thể nhận 409; client cần preview lại rồi thử lại. Chưa có retry tự động.
- `_audit` hiện bỏ qua khi không có `actor_id` (hành vi có sẵn); endpoint production luôn có user qua dependency.
- Chưa xác minh hiệu năng với 500 cấu kiện thật; mỗi dòng được tải/kiểm hai lần (preview trước, commit sau) để đổi lấy tính nguyên tử.

### Cách chạy kiểm tra

```bash
cd backend
$env:DATABASE_URL="sqlite:///$env:TEMP/site-report-daily.db"
..\.venv\Scripts\python.exe -m pytest tests/site_report/test_component_progress.py -q
..\.venv\Scripts\python.exe -m pytest tests/site_report -q
```

## Vòng 13b — nhập tiến độ theo ngày, nhiều dòng (frontend)

Cập nhật: 20/11/2026. Phạm vi thay đổi: chỉ `frontend/src/features/site/components/DailyProgressPanel.tsx` (mới), `frontend/src/features/site/lib/dailyProgress.ts` (mới), `frontend/src/features/site/lib/dailyProgress.test.ts` (mới) và file báo cáo này. Không sửa `frontend/src/features/site/lib/api.ts`, catalog, `frontend/src/app`, `frontend/src/features/site/index.ts`, backend, shared core, migration, module agent khác, `data/app.db` hay Excel nguồn. Không commit/push/deploy. Không chạy migration.

### Chức năng đã hoàn thành

- **Component độc lập**: default export `DailyProgressPanel({ projectId })`; Codex tự gắn import/tab. Không phụ thuộc page shell.
- **Ngày mặc định hôm nay**: `createDailyProgressDraft()` dùng `todayISO()` (Asia/Ho_Chi_Minh); input `type=date` có `max` hôm nay; helper từ chối ngày tương lai.
- **Khu/phân đoạn từ dữ liệu thật**: tải `listSegments(projectId)` và `listComponentProgress(projectId)` qua `apiFetch`; phân đoạn lọc theo khu, fallback dựng từ `ProgressRow.segment_id/segment_number` nếu danh sách segment trống.
- **Chọn công tác có thật**: select lấy từ `listStageDefinitions` (fallback từ stage đã gắn trên cấu kiện), chỉ hiện định nghĩa đang có cấu kiện khả dụng theo khu/phân đoạn; nhãn gồm loại, tên bước, nhóm thiết kế và số cấu kiện.
- **Chọn cấu kiện bằng checkbox**: mỗi dòng có danh sách cấu kiện thực sự gắn bước đã chọn, checkbox, số đã chọn/tổng, “Chọn tất cả”, “Bỏ chọn”. Không có ô nhập tự do hay chọn theo chuỗi văn bản.
- **Sao chép dòng trước**: chỉ sao chép các `component_ids` của dòng trước còn khả dụng cho bước/definition và khu/phân đoạn hiện tại; giữ `stage_id` đã chọn nếu vẫn khớp, bỏ các lựa chọn không còn hợp lệ.
- **Bước cụ thể khi mơ hồ**: nếu một cấu kiện có nhiều `ComponentStage` cùng `stage_definition_id`, bắt buộc chọn đúng `stage_id`; không tự chọn bước đầu tiên. `stage_selections` được gửi đúng component.
- **Mỗi dòng**: trạng thái `IN_PROGRESS|COMPLETED|BLOCKED`, khối lượng nhóm và đơn vị tùy chọn. Khối lượng/đơn vị nhóm chỉ nằm ở dòng, không tự gán vào từng event; helper bỏ field rỗng thay vì gửi chuỗi rỗng.
- **Giới hạn khớp backend**: tối đa 50 dòng và 500 cấu kiện mỗi lần ghi; nút “Thêm công tác” dừng ở 50 dòng.
- **Preview chỉ đọc**: `POST /progress/daily-preview` trả `{can_commit, lines, warnings}`. UI hiển thị đúng danh sách component server trả, `line_index`, bước đã chọn, cảnh báo từng dòng/cả request; không ghi DB và không cho sửa trong màn preview.
- **Lưu tất cả sau khi duyệt**: `POST /progress/daily` chỉ gọi khi đã tick xác nhận và mọi dòng `can_commit`; body có `reviewed: true` + `idempotency_key`. Nếu lưu lỗi, preview và key được giữ nguyên để retry đúng cùng payload; thành công mới xóa preview/key và tải lại danh sách.
- **Cảnh báo trùng bước giữa các dòng**: backend trả `can_commit: false` và warning khi nhiều dòng cùng resolve một `stage_id`; UI hiển thị warning và khóa nút lưu, không tự sửa dữ liệu.
- **An toàn dữ liệu**: mọi lời gọi đều project-scoped qua `projectId` và `apiFetch` có bearer; không sửa ảnh gốc, không gửi Zalo tự động, không ghi nhân lực. Panel không đụng `manpower`, nên quy ước `0` khác `null` của màn báo cáo hiện có không bị thay đổi.

### File thay đổi

- `frontend/src/features/site/lib/dailyProgress.ts` (mới): type hợp đồng ngày, state/selection helpers, validation 50 dòng/500 cấu kiện/ngày tương lai, build payload, preview/save qua `apiFetch`.
- `frontend/src/features/site/lib/dailyProgress.test.ts` (mới): 15 test helper/state thuần + API client.
- `frontend/src/features/site/components/DailyProgressPanel.tsx` (mới): UI mobile-first nhiều dòng, checkbox, chọn bước cụ thể, preview read-only, lưu có xác nhận.
- `docs/agent-reports/site-report.md`: mục này.

### API / model cần dùng

- `POST /api/v1/projects/{p}/progress/daily-preview`
  - Body: `{event_date, lines:[{stage_definition_id, component_ids, stage_selections?, status, group_quantity?, group_unit?}]}`.
  - Response: `{can_commit, lines:[ProgressPreview & {line_index, group_quantity, group_unit}], warnings}`.
  - Quyền backend: `require_site_editor`; chỉ đọc, không ghi DB.
- `POST /api/v1/projects/{p}/progress/daily`
  - Body: như preview + `reviewed: true`, `idempotency_key`.
  - Response: `{created, lines:[ProgressSaveResult & {line_index, stage_definition_id, group_quantity, group_unit}]}`.
  - Backend lưu batch idempotency; retry cùng key/payload trả cùng kết quả; khác payload trả `409`.
- Dùng lại API sẵn có qua `apiFetch`: `GET /projects/{p}/progress`, `GET /projects/{p}/segments`, `GET /projects/{p}/stage-definitions`.
- Type frontend dùng lại `ProgressRow`, `ProgressStage`, `StageDefinition`, `ProgressPreview`, `ProgressSaveResult`; thêm type dòng ngày trong `dailyProgress.ts`.
- **Không cần model/migration mới**. Backend dùng `component_progress_events` và `component_progress_batches` sẵn có; `group_quantity/group_unit` chỉ nằm trong kết quả batch/audit, không copy vào từng event.

### Kiểm thử đã chạy

```bash
cd frontend
npx vitest run src/features/site/lib/dailyProgress.test.ts   # 15 passed
npx vitest run                                              # 31 files, 194 tests passed
npm run build                                               # tsc -b OK; Vite build OK (cảnh báo chunk > 500 kB có sẵn)
```

```powershell
# DB tạm, không dùng data/app.db
$env:DATABASE_URL = "sqlite:///<temp>/site-report-daily-<guid>.db"
..\.venv\Scripts\python.exe -m pytest tests/site_report/test_component_progress.py -q
# 15 passed
```

Test helper bao phủ: lọc cấu kiện khả dụng theo definition/khu/phân đoạn; sao chép id hợp lệ và giữ `stage_id` khớp; xóa lựa chọn/bước khi đổi definition hoặc bộ lọc; toggle checkbox; validation ngày/trạng thái/khối lượng/đơn vị/khu/phân đoạn/50 dòng/500 cấu kiện/ngày tương lai; payload giữ đúng `component_ids` + `stage_selections` và bỏ group field rỗng; preview chỉ commit khi mọi dòng sẵn sàng; key idempotency có prefix và ≤120 ký tự. Test API client kiểm đúng route/project scope, body preview, `reviewed: true` + `idempotency_key` khi lưu, và map lỗi 409 từ `detail` thay vì báo thành công.

Backend test hiện có xác nhận: preview không ghi DB; `line_index`/group quantity đúng; cấu kiện project khác bị cảnh báo; trùng stage giữa dòng bị chặn; commit idempotent; group quantity không lọt vào event.

**Chưa chạy**: test render/DOM hoặc thao tác trình duyệt cho `DailyProgressPanel`; chưa bấm thử UI với backend/DB thật; chưa test trên điện thoại thật. Không có E2E frontend → API thật trong vòng này; phần API được xác nhận bằng backend test hiện có + typecheck, không phải bằng thao tác UI.

### Phụ thuộc / tích hợp

- Backend hai route daily đã có trong working tree (agent/Codex sở hữu backend); frontend chỉ gọi qua `apiFetch`, không sửa backend.
- Codex cần import `./features/site/components/DailyProgressPanel` và gắn tab/nút; chưa export trong `index.ts` để giữ ranh giới chỉ-file-mới.
- Dùng React 19, Vitest và các helper site sẵn có; không thêm dependency, không sửa `api.ts`/catalog.
- `line_index` được dùng để ghép preview với dòng biểu mẫu; UI vẫn kiểm tra số dòng server trả.

### Unresolved / cần theo dõi

- Chưa có test render/DOM/trình duyệt hay E2E UI → backend thật; chưa xác nhận trực quan trên mobile.
- Trùng `stage_id` giữa các dòng chỉ được phát hiện sau khi gọi preview (backend warning + khóa lưu); UI chưa chặn trước khi bấm “Xem lại”.
- Nếu backend đổi shape `ProgressPreview`/`line_index`, UI sẽ báo lệch số dòng nhưng cần cập nhật type theo hợp đồng mới.
- Panel này chỉ ghi tiến độ; không chọn ảnh chứng cứ, không sửa nhân lực/báo cáo ngày và không tự gửi Zalo.
- Không commit/push/deploy; không ghi `data/app.db`.

### Cách chạy kiểm tra

```bash
cd frontend
npx vitest run src/features/site/lib/dailyProgress.test.ts
npx vitest run
npm run build
```

## Vòng 12 — mặt bằng cấu kiện trên bản vẽ (pilot, frontend)

Cập nhật: 20/11/2026. Phạm vi thay đổi: chỉ `frontend/src/features/site/components/DrawingMapPanel.tsx` (mới), `frontend/src/features/site/lib/drawingMap.ts` (mới), `frontend/src/features/site/lib/drawingMap.test.ts` (mới) và file báo cáo này. Không sửa backend, shared core, migration, module agent khác, `frontend/src/app`, `frontend/src/features/site/index.ts`, DB dùng chung hay Excel nguồn. Không commit/push/deploy.

### Chức năng đã hoàn thành

- **Component độc lập**: `DrawingMapPanel({ projectId })` tự tải dữ liệu, không phụ thuộc toggle hay page shell. Codex tự gắn import/nút bật/tắt khi tích hợp.
- **Tải dữ liệu project-scoped**: `GET /api/v1/projects/{p}/drawing-map` qua `apiFetch` có bearer. Hiển thị số trang, tổng vị trí và `review_count`; các mục cần rà soát được cảnh báo là không hiển thị trên bản đồ.
- **Ảnh bản vẽ private**: tải `image_url` bằng `apiFetch` có bearer rồi dùng blob URL; thu hồi object URL khi đổi trang/unmount. Không chép ảnh nguồn vào repo, không tạo static mount, không sửa ảnh gốc.
- **SVG overlay đúng tỉ lệ**: đo `naturalWidth/naturalHeight` và kích thước hiển thị của ảnh `object-fit: contain`, tính hộp ảnh thực tế (kể cả letterbox), rồi vẽ điểm/đoạn theo tọa độ chuẩn hóa `[0,1]` trong hộp đó. Điểm được làm tròn theo cả hai trục pixel; dầm nhiều nhịp vẽ polyline; phạm vi phát sinh có viền/nét đứt màu vàng.
- **Tìm và lọc**: tìm theo mã cấu kiện hoặc mã/tên/trang bản vẽ; lọc loại (cọc/dầm), trạng thái thi công (`NOT_STARTED|IN_PROGRESS|COMPLETED|BLOCKED`) và phạm vi (`DESIGN_SCOPE|ADDITIONAL_SCOPE`). Xóa lọc một chạm. Bộ lọc chỉ thay đổi hiển thị, không ghi dữ liệu.
- **Thu phóng/kéo trên di động**: nút +/− (giới hạn 1×–4×), “Vừa khung”, lăn chuột có `preventDefault`, kéo một ngón và chụm hai ngón. Pan bị giới hạn để ảnh không bị kéo khỏi khung nhìn. `touch-action: none` chỉ đặt trên vùng bản đồ.
- **Mở chi tiết cấu kiện**: chạm marker hoặc chọn trong danh sách gọi `GET /api/v1/projects/{p}/components/{id}`; hiển thị mã gốc/chuẩn, bí danh, trạng thái duyệt, nguồn bản ghi, nhóm thiết kế, phạm vi sửa chữa, bước thi công, dòng DM và nguồn seed. Có đóng, thử lại, Escape và focus vào tiêu đề chi tiết.
- **Danh sách thay thế truy cập được**: danh sách cấu kiện theo từng trang bản vẽ, cùng bộ lọc, mỗi mục là button mở chi tiết; không phụ thuộc thao tác chạm/zoom trên ảnh.
- **Trạng thái rỗng/chờ/lỗi**: endpoint 404/405/501 hiển thị “đang được chuẩn bị”; mảng `sheets` rỗng hiển thị chưa có bản đồ; lỗi khác có thông báo và nút thử lại; ảnh lỗi có nút thử lại riêng.
- **Không tự gửi Zalo, không sửa dữ liệu**: toàn bộ màn hình chỉ đọc.

### File thay đổi

- `frontend/src/features/site/lib/drawingMap.ts` (mới): type hợp đồng, hàm lọc, đo hộp ảnh contain, clamp zoom/pan, pinch zoom, chuẩn hóa điểm, `fetchDrawingMap`, `fetchDrawingSheetImageUrl`, `fetchComponentDetail`.
- `frontend/src/features/site/lib/drawingMap.test.ts` (mới): 10 test helper thuần.
- `frontend/src/features/site/components/DrawingMapPanel.tsx` (mới): UI mobile-first, SVG overlay, zoom/pan/pinch, chi tiết và danh sách thay thế.
- `docs/agent-reports/site-report.md`: mục này.

### API / model cần dùng

- `GET /api/v1/projects/{p}/drawing-map` → `{sheets:[{id,title,drawing,page,image_url,markers:[{component_id,code,type,points,origin,construction_status}]}],review_count}`.
- `image_url` được gọi qua `apiFetch` với bearer; helper chấp nhận cả dạng `/projects/...` và `/api/v1/projects/...`. Backend hiện trả route ảnh riêng tư `/projects/{p}/drawing-map/{sheet_id}/image`.
- `GET /api/v1/projects/{p}/components/{id}` cho chi tiết cấu kiện.
- Không cần model hay migration mới ở frontend. Không cần thay đổi shared core. Điểm chuẩn hóa do backend cung cấp; frontend chỉ kẹp giá trị phòng thủ.

### Kiểm thử đã chạy

```bash
cd frontend
npx vitest run src/features/site/lib/drawingMap.test.ts   # 10 passed
npm test                                                   # 30 files, 179 tests passed
npx tsc --noEmit                                           # OK
npm run build                                              # OK (Vite báo chunk > 500 kB, không phải lỗi)
```

Test bao phủ: lọc theo mã/loại/trạng thái/phạm vi và tổ hợp tìm kiếm; giữ trang khi không có bộ lọc; bỏ trang không còn marker khớp; letterbox `object-contain`; kẹp/loại điểm sai; giới hạn zoom 1–4; clamp pan; pinch zoom; chuẩn hóa tiền tố `/api/v1` của `image_url`.

**Chưa chạy**: test DOM/tương tác trình duyệt, test trên điện thoại thật, E2E với backend/DB thật hoặc ảnh pilot thật. Không chạy migration hay test backend trong vòng này, nên không xác nhận trực tiếp dữ liệu `drawing-map` thực tế ngoài việc đọc router hiện có.

### Phụ thuộc / tích hợp

- Dùng React 19, `apiFetch`/`ApiError` sẵn có của site và Vitest; không thêm dependency.
- Chưa export `DrawingMapPanel` trong `frontend/src/features/site/index.ts` để giữ đúng ranh giới “chỉ file mới”. Codex có thể import trực tiếp `./features/site/components/DrawingMapPanel` khi làm toggle.
- Không thay đổi `frontend/src/app`, không tự thêm route hay nút vào page.

### Unresolved

- Chưa xác minh trực quan trên thiết bị thật: vị trí marker, thao tác chụm/kéo và vùng chạm 44 px mới được kiểm bằng code/type/build, chưa bằng trình duyệt.
- Marker chồng nhau ở mức zoom thấp có thể che nhau; chưa có clustering. Danh sách thay thế là cách mở các marker bị che.
- Pinch zoom neo theo tâm khung nhìn, không neo theo điểm giữa hai ngón; chưa có double-tap zoom.
- Chưa hỗ trợ `image_url` tuyệt đối (`http(s)://`); hợp đồng hiện tại là đường dẫn API-relative và helper xử lý đúng hợp đồng đó.
- `review_count` chỉ được hiển thị theo số backend trả; frontend không tự tính lại hoặc sửa dữ liệu rà soát.

### Cách chạy kiểm tra

```bash
cd frontend
npx vitest run src/features/site/lib/drawingMap.test.ts
npm test
npx tsc --noEmit
```

## Vòng 11 — màu trạng thái từng bước và thứ tự bước theo `position`

Cập nhật: 20/11/2026. Phạm vi: chỉ `frontend/src/features/site/components/ComponentProgressPanel.tsx`, `frontend/src/features/site/lib/componentProgress.ts`, `frontend/src/features/site/lib/componentProgress.test.ts` và file báo cáo này. Không sửa backend, shared core, migration, module agent khác, `data/app.db` hay Excel nguồn. Không stage/commit/deploy.

### Chức năng đã hoàn thành

- **Màu trạng thái từng bước**: danh sách “Bước thi công” trong mỗi thẻ cấu kiện hiển thị chip trạng thái thay cho chữ thường: `COMPLETED` xanh lá (emerald), `IN_PROGRESS` vàng (amber), `NOT_STARTED` đỏ (red), `BLOCKED` tím (violet) để phân biệt với `NOT_STARTED`. Chip `Thi công` ở cấp cấu kiện dùng cùng bảng màu nên không mâu thuẫn.
- **Không đổi style nghiệm thu**: `AcceptanceChip` và các màu `APPROVED|PENDING|CONDITIONAL|REJECTED|NOT_LINKED` giữ nguyên.
- **Thứ tự bước**: helper thuần `sortStagesByPosition` sắp theo `position` của server, tie-break bằng `code` rồi `id`; không sửa mảng gốc. Áp dụng cho danh sách bước từng cấu kiện, `stageOptionsFor` (danh sách chọn phạm vi/bước trong editor) và danh sách khối lượng thiết kế; sort definition trong editor dùng lại cùng helper.

### File thay đổi

- `frontend/src/features/site/lib/componentProgress.ts`: thêm `sortStagesByPosition`; `stageOptionsFor` và `buildDesignQuantityEntries` trả theo thứ tự đã sort.
- `frontend/src/features/site/components/ComponentProgressPanel.tsx`: bảng màu trạng thái, chip từng bước, dùng helper sort.
- `frontend/src/features/site/lib/componentProgress.test.ts`: test thứ tự bước.
- `docs/agent-reports/site-report.md`: mục này.

### API / model

- Không thêm API hay model. Dùng dữ liệu sẵn có từ `GET /api/v1/projects/{p}/progress` (`stages[].position/code/id/status`) và `GET /api/v1/projects/{p}/stage-definitions`.
- Không cần migration.

### Kiểm thử đã chạy

```bash
cd frontend
npx vitest run src/features/site/lib/componentProgress.test.ts   # 14 passed
npx tsc --noEmit                                                  # OK
```

Test bao phủ: sort theo `position`; tie-break `code` rồi `id`; không thay đổi mảng đầu vào; `stageOptionsFor` giữ đúng thứ tự. **Chưa chạy** test render/E2E trình duyệt cho màu chip và **chưa chạy** full `npm test`/`npm run build` (các thay đổi đang có của agent khác trong working tree).

### Unresolved

- Chưa có ảnh chụp/kiểm tra trực quan trên thiết bị thật; màu được kiểm bằng class Tailwind, không bằng test DOM.
- Màu `NOT_STARTED` đỏ là yêu cầu nghiệp vụ của vòng này; nếu muốn quay lại xám, chỉ cần đổi `STATUS_STYLES.NOT_STARTED`.
- Không commit/push/deploy, không đọc/ghi DB thật.

### Cách chạy

```bash
cd frontend
npx vitest run src/features/site/lib/componentProgress.test.ts
npx tsc --noEmit
```

## Vòng 10 - ảnh hiện trường: camera/thư viện, watermark/nén, xóa ảnh

Cập nhật: 20/11/2026. Phạm vi thay đổi: `frontend/src/features/site/`, test tương ứng và file báo cáo này. Không sửa `backend/`, `backend/app/core`, migration, `frontend/src/app`, DB dùng chung, hay Excel nguồn.

### Chức năng đã hoàn thành

- **Camera và thư viện tách riêng**: nút `Chụp ảnh` dùng input `capture="environment"`; nút `Chọn ảnh từ máy` dùng input riêng, `multiple`, `accept="image/*"`. Cả hai nguồn đi vào cùng hàng đợi xem trước rồi mới tải lên/lưu offline.
- **Xử lý ảnh thật trước khi tải/queue**: đọc EXIF JPEG/TIFF (ngày chụp, GPS, hướng), vẽ watermark ngày giờ + vị trí lên pixel, dùng Canvas xuất JPEG. Ảnh được thu cạnh dài về tối đa 1.920 px; thử chất lượng 0,82 → 0,77 → 0,72 → 0,67 → 0,65, dừng khi ≤ 500 KB. Nếu vẫn > 500 KB ở 0,65 thì hiển thị cảnh báo, không giả vờ đã đạt.
- **Không bịa metadata**: ảnh mới chụp lấy giờ thiết bị tại lúc xử lý và GPS thiết bị nếu người dùng cấp quyền. Ảnh có sẵn chỉ dùng EXIF đọc được và vị trí người dùng nhập; thiếu dữ liệu hiển thị và in `Chưa xác định`. Không dùng vị trí hiện tại cho ảnh lịch sử, không dùng `lastModified` thay cho giờ chụp.
- **Nguồn metadata ở bước xem trước**: mỗi ảnh đã xử lý hiển thị thời gian, vị trí, nguồn (`EXIF`, `Giờ thiết bị khi chụp`, `Vị trí nhập`, `GPS thiết bị`, `GPS trong ảnh`), kích thước, dung lượng, chất lượng JPEG và cảnh báo > 500 KB. Người dùng có thể bỏ từng ảnh hoặc bỏ tất cả trước khi tải.
- **Định dạng không hỗ trợ**: chặn SVG, tệp rỗng, MIME/đuôi ngoài allowlist; HEIC/HEIF được nhận nhưng nếu trình duyệt không decode được thì báo rõ cách chọn/chuyển sang JPEG/PNG.
- **Giữ nguyên hướng ảnh**: decode bằng `createImageBitmap(..., { imageOrientation: "from-image" })` hoặc `<img>` (trình duyệt hiện đại tự áp EXIF orientation) trước khi vẽ Canvas. Ảnh đầu ra là JPEG đã chuẩn hướng.
- **Offline fallback**: ảnh đã xử lý (không phải ảnh gốc) được queue vào IndexedDB; retry dùng đúng `client_upload_id` cũ. Lỗi validate 4xx hiển thị cho người dùng, không đẩy vào queue; lỗi mạng/5xx mới queue.
- **Giữ field khi queue**: bổ sung `workItemIds` vào payload queue để ảnh offline không mất liên kết công việc. Các field `reportId/reportDate/category/location/component/stage` vẫn được giữ.
- **Xóa ảnh có xác nhận**: mỗi photo card có nút `Xóa ảnh`, hỏi xác nhận trước khi gọi `DELETE /api/v1/projects/{project_id}/photos/{photo_id}`. 204 thành công thì xóa khỏi state/UI ngay; 409 hiển thị thông báo ảnh đang là bằng chứng (tiến độ/nhật ký/nghiệm thu) và không xóa. Offline thì không gửi xóa.
- **Không tự gửi Zalo**: không thêm luồng gửi tự động nào.

### File thay đổi

- `frontend/src/features/site/lib/photoProcessing.ts` (mới): parse EXIF, quyết định nguồn thời gian/vị trí, watermark, resize, nén JPEG, kiểm tra định dạng, lấy GPS thiết bị.
- `frontend/src/features/site/lib/photoProcessing.test.ts` (mới): test helper không phụ thuộc DOM.
- `frontend/src/features/site/lib/api.ts`: thêm `deletePhoto`.
- `frontend/src/features/site/lib/api.test.ts` (mới): test route prefix `/api/v1`, 204 và 409.
- `frontend/src/features/site/lib/offlineDb.ts`: `PhotoQueuePayload.workItemIds`.
- `frontend/src/features/site/hooks/useOfflineSync.ts`: gửi `workItemIds` khi sync ảnh.
- `frontend/src/features/site/components/PhotoCapture.tsx`: tách camera/thư viện, bước xem trước ảnh đã xử lý, watermark/nén, queue ảnh đã xử lý, nút xóa ảnh.
- `frontend/src/features/site/pages/SiteReportPage.tsx`: xóa ảnh khỏi state sau khi API thành công; gọi `syncNow` khi ảnh vào queue.

### API đã dùng / cần backend đáp ứng

- `POST /api/v1/projects/{project_id}/photos` (multipart, nhiều file): upload JPEG đã xử lý; `client_upload_ids` giữ idempotency.
- `GET /api/v1/projects/{project_id}/photos` và `GET .../{photo_id}/original`: danh sách và ảnh gốc có bearer token.
- `PATCH /api/v1/projects/{project_id}/photos/{photo_id}`: giữ nguyên luồng xác nhận chú thích/loại/vị trí.
- `DELETE /api/v1/projects/{project_id}/photos/{photo_id}`: frontend gọi đúng prefix, chấp nhận 204 rỗng; map 409 thành thông báo ảnh đang là bằng chứng. Route này đã có trong `backend/app/site/router.py` của checkout (agent backend thêm, `status_code=204`, `PhotoDeleteConflict` → 409); frontend không sửa backend.
- Queue offline dùng lại `POST /photos` với cùng `client_upload_ids`.

### Phụ thuộc

- Backend `DELETE /projects/{project_id}/photos/{photo_id}` (đã có trong router của checkout, agent backend sở hữu) trả 204/409.
- Các API ảnh hiện có: upload/list/original/patch.
- Không thêm thư viện npm; dùng Canvas, File/Blob, IndexedDB và Geolocation API sẵn có của trình duyệt.

### Model / migration

- Không cần model hay migration mới. Dùng `SitePhoto`, `PhotoWorkItemLink` và các field hiện có.
- **Giữ metadata ảnh**: JPEG sau Canvas được chèn lại APP1 EXIF tối thiểu: `Orientation=1`, `DateTime`/`DateTimeOriginal`, GPS và `Model` (thiết bị) nếu có. Vì vậy backend vẫn đọc được `capture_time`/GPS của ảnh đã xử lý; không tạo EXIF giả khi nguồn không có dữ liệu. Các tag EXIF không cần cho nghiệp vụ (ống kính, ISO…) không được chép lại.

### Kiểm thử đã chạy

- `npx vitest run src/features/site/lib/photoProcessing.test.ts src/features/site/lib/api.test.ts`: **12 passed**.
- `npm test` (toàn frontend): **29 file, 169 test passed**.
- `npx tsc -b`: pass.
- `npm run build`: pass (chỉ còn cảnh báo chunk >500 kB có sẵn).
- Test đã bao phủ: scale 1.920 px, parse EXIF TIFF/JPEG APP1, ghi lại EXIF tối thiểu (orientation=1, thời gian, GPS, thiết bị), ưu tiên EXIF/GPS/giờ thiết bị, không lấy GPS cho ảnh lịch sử thiếu EXIF, format `Chưa xác định`, allowlist định dạng, thang chất lượng 0,82–0,65 và ngưỡng 500 KB, route DELETE `/api/v1`, 204, 409.
- **Chưa test thực tế trên trình duyệt/điện thoại**: camera Safari/Chrome, quyền GPS bị từ chối, HEIC, ảnh xoay EXIF, watermark pixel thật, tốc độ nén ảnh lớn, và route DELETE thật với backend. Chưa đối chiếu EXIF do frontend tạo bằng Pillow/backend thật. Không tuyên bố các phần này đã chạy.

### Unresolved / cần phối hợp

- Cần chạy kiểm thử tích hợp frontend với `DELETE /projects/{project_id}/photos/{photo_id}` thật (204/409) trong môi trường backend; hiện frontend chỉ test client với fetch mock.
- EXIF ghi lại là bộ tối thiểu (hướng, thời gian, GPS, thiết bị); các tag gốc khác không được bảo toàn.
- Chưa có E2E/render test cho component PhotoCapture; chỉ test helper và API client.
- Cần kiểm tra trên điện thoại thật (HTTPS) trước khi dùng công trường, đặc biệt camera iOS và ảnh HEIC.

### Cách chạy

```bash
cd frontend
npx vitest run src/features/site/lib/photoProcessing.test.ts src/features/site/lib/api.test.ts
npm test
npx tsc -b
npm run build
```

Không chạy migration, không ghi `data/app.db`, không commit/stage/deploy.

## Vòng 10b — xóa ảnh hiện trường (backend)

Cập nhật: 20/11/2026 (backend-only). Phạm vi chính: `backend/app/site/`, test tương ứng và file báo cáo này. Không sửa `backend/app/core`, `backend/app/models`, migration, module agent khác, Excel nguồn. Vòng này không sửa frontend (agent khác sở hữu UI).

- **API**: `DELETE /api/v1/projects/{p}/photos/{id}` dùng đúng route ảnh hiện tại; quyền `project editor` qua `require_site_editor`; ảnh khác project/không tồn tại trả `404`; thành công `204` không body.
- **Chặn mất bằng chứng (`409`)**: không xóa khi ảnh còn được tham chiếu bền vững bởi:
  - `component_progress_events.evidence_refs` (`<id>` hoặc `photo:<id>`), kể cả event cũ thiếu join cấu kiện;
  - `daily_reports.status=reviewed` mà ảnh đang gắn qua `report_id`;
  - snapshot nhật ký đã duyệt (`generated_documents.kind=journal_snapshot`, JSON `evidence[].photo_id`); snapshot hỏng/không đọc được bị coi là còn bằng chứng;
  - `acceptance_checklists.evidence_refs`;
  - PYC còn liên kết báo cáo ngày của ảnh đã xác nhận (`acceptance_requests.daily_report_id`).
  Response `409` nêu rõ nơi đang dùng ảnh; không xóa file/DB.
- **Files safety**: chỉ xóa file gốc khi path nằm trong `SITE_REPORT_STORAGE`; path ngoài storage bị từ chối (`404`) và không đụng file ngoài. File đã mất vẫn cho dọn metadata. File được đọc trước khi xóa và khôi phục nếu DB commit lỗi; link `photo_work_item_links` bị xóa tường minh.
- **Audit**: thành công ghi `delete_photo` (sha256, filename, report_id, file_removed). Bị chặn ghi `delete_photo_blocked`; lỗi file/path ghi `delete_photo_failed` trong transaction riêng sau rollback để audit còn lại dù ảnh/file được giữ. Lỗi xóa file trả `500`, ảnh vẫn còn.
- **Không cần migration shared**: dùng bảng/cột hiện có (`site_photos`, `photo_work_item_links`, `component_progress_events`, `acceptance_checklists`, `generated_documents`, `audit_logs`). Không sửa `backend/app/core`, `backend/alembic`, DB demo hay `data/app.db`.
- **Frontend**: không thay đổi trong vòng này; API client/nút xóa do agent site frontend đảm nhiệm.

### File thay đổi (vòng 10b)

- Backend: `backend/app/site/service.py` (reference checks, file safety, audit, `delete_photo`), `backend/app/site/router.py` (DELETE route + error mapping).
- Test: `backend/tests/site_report/test_photo_delete.py` (mới, 10 test).
- Tài liệu: `docs/agent-reports/site-report.md`.
- Không sửa migration, core, acceptance, frontend, Excel nguồn hay dữ liệu dùng chung.

### Kiểm thử (vòng 10b)

```bash
cd backend
DATABASE_URL="sqlite:////tmp/opencode/site-report-photo-$$.db" \
  ../.venv/bin/python -m pytest tests/site_report -q
# 82 passed (site suite, gồm 10 test xóa ảnh)
```

Bao phủ: xóa ảnh chưa liên kết (file + link + audit); lần xóa thứ hai `404`; project khác `404`; chặn theo progress (`photo:<id>` và bare id); chặn report `reviewed`, cho xóa khi report về `draft`; chặn snapshot nhật ký; chặn checklist/PYC nghiệm thu; từ chối path ngoài storage; dọn metadata khi file đã mất; lỗi khóa file trả `500`, giữ ảnh/file và audit `delete_photo_failed`.

### Unresolved / manual review (vòng 10b)

- Chưa có test trình duyệt/E2E cho nút xóa; frontend do agent khác làm.
- Ảnh đang gắn báo cáo `reviewed` bị chặn kể cả khi chưa có caption/category; đây là bảo thủ để không làm mất hồ sơ đã duyệt. Nếu nghiệp vụ muốn cho xóa ảnh chưa xác nhận trong báo cáo đã duyệt, cần quyết định lại.
- Snapshot nhật ký đã có bản sao evidence; vẫn chặn xóa ảnh gốc theo yêu cầu giữ bằng chứng, chưa có retention policy.
- Xóa file lỗi trả `500` và giữ metadata; chưa có endpoint retry dọn file riêng.
- Không commit/push, không deploy, không sửa `data/app.db`.

## Vòng 9 — snapshot nhật ký đã duyệt và xuất file

- **Preview có hash duyệt**: `GET /journals/{date}/preview` trả `preview_sha256`, `snapshot_eligible`, `blockers`, `preview_text`, danh sách chứng cứ đã xác nhận, số chứng cứ bị bỏ, số BBNT đã xác nhận. Báo cáo ngày `draft` chặn snapshot (`DAILY_REPORT_NOT_REVIEWED`).
- **Snapshot bất biến**: `POST /journals/{date}/snapshots` bắt buộc `{reviewed: true, preview_sha256}`. Server dựng lại preview, so hash; nếu dữ liệu/ảnh đổi thì trả `409` và không ghi. Snapshot gồm JSON đã duyệt + bản sao ảnh chứng cứ tại `journals/<date>/<snapshot_id>/evidence/`, lưu bằng `GeneratedDocument(kind=journal_snapshot)`; không cần bảng mới.
- **Chỉ chứng cứ đã xác nhận**: ảnh báo cáo/tiến độ chỉ vào snapshot khi có `confirmed_caption` hoặc `category`; ảnh chưa xác nhận/không phân giải bị bỏ, ghi `omitted_evidence_refs` và cảnh báo. Không tự liên kết lại ảnh.
- **Không nghiệm thu giả**: chỉ BBNT `confirmed` đúng ngày xác nhận mới vào preview/snapshot/export. Ngày không có BBNT ghi rõ “Chưa có BBNT đã xác nhận trong ngày”; không suy ra từ tiến độ.
- **Xuất từ snapshot**: `POST /journals/{date}/exports` `{snapshot_id, format: pdf|docx|zip}` đọc JSON đã đóng băng, kiểm hash file và hash ảnh; PDF/DOCX nêu danh mục chứng cứ, ZIP kèm `snapshot.json`, `journal.txt`, `journal.pdf`, `journal.docx` và bytes ảnh đã xác nhận. Không đọc lại report/progress/acceptance live.
- **UI**: tab “Nhật ký” trong màn hình Cấu kiện; xem preview, xác nhận tạo snapshot, tải JSON, xuất PDF/DOCX/ZIP, xem lịch sử. Không sửa app shell.

### File thay đổi (vòng 9)

- Backend: `backend/app/site/journal.py` (mới), `backend/app/site/progress.py` (preview evidence/text/hash), `backend/app/site/router.py` (gắn route journal).
- Test: `backend/tests/site_report/test_journal_snapshot.py` (mới).
- Frontend: `frontend/src/features/site/components/JournalPanel.tsx` (mới), `frontend/src/features/site/lib/journal.ts` + `.test.ts` (mới), `frontend/src/features/site/lib/api.ts`, `frontend/src/features/site/index.ts`, `frontend/src/features/site/components/ComponentCatalogImport.tsx` (tab Nhật ký).
- Hợp đồng: `docs/API_CONTRACTS.md` (snapshot/export + semantics).
- Không sửa `frontend/src/app`, core, migration, acceptance, Excel nguồn hay DB thật.

### Đối chiếu UI/API với hợp đồng shared-core

- Status tiến độ dùng đúng `IN_PROGRESS|COMPLETED|BLOCKED`; view thêm `NOT_STARTED` khi chưa có event và không đổi nghĩa event core.
- Bulk site nhận `stage_definition_id` rồi phân giải sang `ComponentStage` đã gắn; core per-component nhận `stage_id`. Cả hai ghi cùng `component_progress_events`, nên không lệch dữ liệu.
- `acceptance_status` đọc `component_acceptance_links` và kết quả BBNT `confirmed`; không suy ra từ tiến độ. Chưa có link thì `NOT_LINKED`.
- Hợp đồng journal trước đây chỉ có preview; vòng này bổ sung snapshot/export và đã ghi vào `docs/API_CONTRACTS.md`. Không cần sửa route core.

### Shared migration cần thiết

**Không cần migration mới cho vòng này.** Snapshot/export dùng bảng `generated_documents` sẵn có (`kind`, `format`, `path`, `sha256`, `report_date`, `metadata_json`) và bảng `component_progress_batches` sẵn có từ migration shared-core `b3e5f7a9c1d2`. Nếu shared-core muốn tách bảng `journal_snapshots` hoặc thêm cột `reviewed_by` thì đó là migration tùy chọn cho tương lai, không cần để chạy code hiện tại.

### Kiểm thử (vòng 9)

- Backend toàn bộ, DB tạm: **343 passed, 7 skipped**. Riêng site: **69 passed**.
- Frontend: **145 passed**, `tsc --noEmit` OK, production build OK.
- Test journal bao phủ: chặn snapshot khi report nháp; sai `preview_sha256` không ghi; snapshot lưu đúng ảnh đã xác nhận, bỏ ảnh chưa xác nhận; hash file; ZIP có snapshot + text + PDF + DOCX + bytes ảnh; PDF/DOCX tải được; sửa report/progress sau snapshot không lọt vào export; BBNT draft không vào text/export; project khác 404; lịch sử export.

### Unresolved / manual review (vòng 9)

- PDF/DOCX chỉ liệt kê caption chứng cứ; bytes ảnh nằm trong ZIP (theo pattern export báo cáo ngày hiện có). Nếu cần nhúng ảnh trực tiếp vào PDF/DOCX thì phải mở rộng renderer và test layout.
- Chưa có retention/xoá snapshot/export; snapshot cũ vẫn giữ khi report thay đổi (đúng chủ đích), cần chính sách lưu trữ riêng.
- Snapshot không yêu cầu report ngày nếu chỉ có tiến độ/BBNT; preview ghi rõ mục báo cáo trống. Đây là chủ ý để không bịa dữ liệu, nhưng cần người dùng xác nhận nghiệp vụ.
- Chưa có render/E2E trình duyệt cho tab Nhật ký; đã test helper, API, typecheck, build.
- Không commit/push.

## Vòng 8 — tiến độ cấu kiện và nhật ký đã duyệt

- **Xem/lọc tiến độ**: `GET /projects/{p}/progress` gom cấu kiện + stages + sự kiện mới nhất; lọc theo mã/alias, khu, phân đoạn, loại, nhóm, phạm vi, nguồn, bước, trạng thái thi công và trạng thái nghiệm thu.
- **Hai trạng thái độc lập**: `construction_status` (`NOT_STARTED|IN_PROGRESS|COMPLETED|BLOCKED`) lấy từ `ProgressEvent`; `acceptance_status` chỉ lấy từ liên kết tường minh `component_acceptance_links` (`NOT_LINKED|PENDING|APPROVED|CONDITIONAL|REJECTED|CONFIRMED`) và `acceptance_count` là số BBNT đã xác nhận. Không ghi/suy ra nghiệm thu từ tiến độ.
- **Duyệt nhiều cấu kiện chính xác**: `POST /progress/bulk-preview` kiểm tra đúng `component_ids[]` + một `stage_definition_id`, trả cấu kiện thiếu, cấu kiện chưa gắn bước và `can_commit`; không ghi DB. `POST /progress/bulk` yêu cầu `{reviewed: true, idempotency_key, ...}` và kiểm lại đúng danh sách/bước trong transaction trước khi ghi `ProgressEvent` + audit.
- **Idempotency bulk**: bảng `component_progress_batches` (đã có trong migration shared-core `b3e5f7a9c1d2`) lưu hash/result; retry cùng key không nhân đôi sự kiện.
- **Nhật ký ngày chỉ đọc**: `GET /projects/{p}/journals/{date}/preview` trả báo cáo ngày, sự kiện thi công, BBNT `confirmed` đúng ngày và các mục `blank_sections`/`warnings`. Không tự điền thời tiết/thiết bị/thay đổi thiết kế/môi trường/nghiệm thu; báo cáo nháp chỉ cảnh báo, không dùng để xuất.
- **UI**: tab “Tiến độ” trong màn hình Cấu kiện (site-owned, không sửa app shell). Bộ lọc, chọn từng cấu kiện hoặc tất cả đang lọc, xem lại danh sách chính xác từ máy chủ, xác nhận rồi mới lưu. Không cho bulk theo chuỗi văn bản.
- **Không đổi app shell**: `frontend/src/app/App.tsx` không bị sửa trong vòng này.

### File thay đổi (vòng 8)

- Backend: `backend/app/site/db.py` (mới, dependency DB dùng chung cho router site), `backend/app/site/progress.py` (mới), `backend/app/site/models.py` (thêm `SiteProgressBulkBatch`), `backend/app/site/router.py` (gắn route tiến độ).
- Test: `backend/tests/site_report/test_component_progress.py` (mới).
- Frontend: `frontend/src/features/site/lib/componentProgress.ts` + `.test.ts` (mới), `frontend/src/features/site/components/ComponentProgressPanel.tsx` (mới), `frontend/src/features/site/components/ComponentCatalogImport.tsx` (tab), `frontend/src/features/site/lib/api.ts`, `frontend/src/features/site/index.ts`.
- Hợp đồng: `docs/API_CONTRACTS.md` (route + quy tắc trạng thái/idempotency/nhật ký).
- Không sửa migration, `backend/app/core`, acceptance, Excel nguồn hay DB thật.

### Kiểm thử (vòng 8)

- Backend toàn bộ, DB tạm: **333 passed, 7 skipped**. Riêng site: **66 passed**.
- Frontend: **143 passed**, `tsc --noEmit` OK, production build OK.
- Migration: `alembic upgrade head` và `downgrade -1` → `upgrade head` trên SQLite tạm OK; không dùng `data/app.db`.
- Test tiến độ bao phủ: view/filter hai trạng thái độc lập; preview không ghi DB; chọn thiếu cấu kiện/bước bị chặn; `reviewed: false` bị 422; retry cùng key idempotent; key khác payload 409; ghi `COMPLETED` không tạo acceptance; acceptance chỉ đổi khi có link/BBNT xác nhận; journal chỉ lấy đúng ngày, BBNT confirmed, không tự điền mục trống.

### Unresolved / manual review (vòng 8)

- UI chưa tạo StageDefinition/ComponentStage; cần tạo bước và gắn vào cấu kiện bằng API core trước khi bulk khả dụng. Cấu kiện chưa gắn bước bị từ chối, không tự gắn.
- UI gửi `evidence_refs: []`; API đã nhận tối đa 20 tham chiếu nhưng chưa có màn hình chọn ảnh chứng cứ đã xác nhận.
- `acceptance_status` phụ thuộc acceptance agent nhập link; nếu chưa nhập link thì đúng là `NOT_LINKED`, không phải “chưa nghiệm thu thực tế”.
- Journal mới là preview read-only, chưa có xuất Word/PDF và chưa có màn hình xem trong UI.
- Chưa có test render/E2E trình duyệt cho tab Tiến độ; đã kiểm bằng helper Vitest, typecheck và build.
- Không commit/push.

## Chức năng đã hoàn thành

### Vòng 7 — danh mục công việc cho ngày chưa có báo cáo
- **Nguyên nhân**: trong `SiteReportPage`, khối `getWorkItems(projectId)`/`getOrganizations`/`listManpowerPresets` nằm trong nhánh `if (!serverFailed && remote)`. Khi ngày được chọn chưa có báo cáo, `getDailyReport` trả `null` (404), nên `remote = null` và các API danh mục không bao giờ được gọi. Thêm nữa nhánh `else if (!baseReport)` gọi `setWorkItems([])`, xoá luôn danh sách nếu có.
- **Sửa**: tách tải danh mục khỏi tải báo cáo. Helper thuần `shouldLoadCatalogs(serverFailed)` (`lib/viewCache.ts`) quyết định nạp danh mục khi server truy cập được. Ba API `getWorkItems`, `getOrganizations`, `listManpowerPresets` nằm trong nhánh này, mỗi API có `try/catch` riêng nên một API lỗi không chặn hai API còn lại (không dùng `Promise.all`).
- **Ảnh/cache**: `listPhotos` và `saveViewCache` vẫn chỉ chạy khi có `remote` của đúng ngày; không thay đổi hành vi lưu báo cáo, offline queue, ảnh gốc/app PYC history.
- **Offline**: khi `serverFailed` và có cache, vẫn dùng `cached.workItems`/`cached.photos`; khi `serverFailed` và không có cache, xoá danh mục cũ của ngày trước để không hiện lựa chọn stale.
- **Không đè danh sách**: bỏ `setWorkItems([])` khỏi nhánh không có báo cáo khi server còn truy cập được, nên danh sách vừa tải được giữ nguyên.
- Quyết định nhỏ: đặt helper trong `lib/viewCache.ts` thay vì tạo module mới, vì đây là quyết định chọn nguồn dữ liệu view (server/cache/empty) và đã có test Vitest cùng chỗ.

### Vòng 6 — nhập tên nhân lực, công việc hôm nay, `work_name`
- **Sửa lỗi mất dấu cách khi nhập tên**: `splitManpowerTeam` và `teamToManpowerEntries` giữ nguyên text đang gõ (kể cả dấu cách cuối). Helper `normalizePersonName` chỉ `trim` + gộp khoảng trắng khi `onBlur` hoặc trước khi gửi API/draft (`buildBody` trong `SiteReportPage`). Add/remove Kỹ thuật, preset, dedupe vẫn dùng key đã chuẩn hoá nên không bị trùng tên.
- **Khối “Công việc thực hiện hôm nay”**: bỏ hoàn toàn input `datetime-local`; `WorkLogForm` nhận prop `reportDate` và hiển thị `Ngày báo cáo: DD/MM/YYYY`. Mỗi dòng: select công việc, input Vị trí tự do, nút xoá; số lượng/ĐVT/component/trạng thái/ghi chú nằm trong mục “Chi tiết” thu gọn. Trạng thái mặc định `done`, nút “+ Thêm công việc”, empty state rõ ràng. Không tự động ghi đè vị trí/component khi chọn công việc.
- **Danh mục công việc**: helper thuần `frontend/src/features/site/lib/workItems.ts` gom 41 dòng danh mục thành 7 tên duy nhất và nhóm theo Đục phá / Xử lý bề mặt / Vệ sinh-kết dính / Khoan cấy / Lắp đặt-bơm vữa / Khác. `work_name` ngoài danh mục vẫn được thêm option để hiển thị.
- **`work_name`**: thêm cột nullable `String(500)` vào `DailyWorkLog` (model/schema/upsert), type frontend và `reportReconnect` normalise. Chọn một tên duy nhất ⇒ `work_name` = tên, `work_item_id = null`; dữ liệu cũ có `work_item_id` giữ nguyên nếu người dùng không đổi select. Snapshot/export resolve `work_item_name` từ `work_item_id` trước, fallback `work_name`.
- **Xuất báo cáo**: dòng công việc trong Zalo/PDF/DOCX dùng dạng `Tên công việc tại Vị trí`; nếu không có vị trí thì dùng component. Không đổi định dạng mục nhân lực/kế hoạch.

### Báo cáo ngày
- `PUT/GET /projects/{p}/daily-reports/{date}` upsert idempotent theo `project_id + report_date`.
- `manpower[]`, `work_logs[]`, `next_day_plans[]`, `notes`, `status=draft|reviewed`.
- `site_notes` tuỳ chọn gồm 8 mục: `weather`, `materials`, `equipment`, `incidents`, `difficulties`, `safety`, `recommendations`, `other`; lưu JSON text, mục trống = `null`, không tự sinh nội dung.
- `count=0` và `count=null` được giữ khác nhau xuyên suốt: Pydantic → DB → response → snapshot → Zalo/PDF/DOCX/ZIP.
- Từ chối `count < 0`, `group_name` rỗng, `status` ngoài `draft|reviewed`.
- Thời gian naive từ mobile được hiểu là giờ `Asia/Ho_Chi_Minh`, chuẩn hoá UTC khi lưu; response luôn có timezone (SQLite không giữ offset nên output tự gắn UTC).
- Kiểm tra `end_time >= start_time`.
- Validate `work_item_id` của work log/next-day plan và `organization_id` của manpower thuộc đúng project; lỗi 404, không xoá bản nháp cũ.
- Upsert thay thế toàn bộ collection con sau khi validate, tránh mất dữ liệu khi request sai.

### Mẫu nhân lực
- CRUD project-scoped `/manpower-presets`: danh sách, tạo, sửa, xoá; mỗi mẫu có `group_name`, `person_name`, `count`, `organization_id`.
- `count=0` và `count=null` được giữ nguyên trong DB/API/UI; UI chỉ thêm mẫu khi người dùng bấm “Dùng”.
- `organization_id` non-null phải thuộc cùng project; UI tải organizations từ core để chọn.

### Ảnh hiện trường
- `POST /projects/{p}/photos` upload nhiều ảnh multipart; lưu nguyên bytes gốc, chỉ lưu metadata trong DB. Response trả metadata kèm `sync_status=synced` và echo `client_upload_id` để client offline đối chiếu.
- SHA-256, kích thước, MIME, tên file gốc; EXIF capture time/device/GPS best-effort.
- EXIF datetime không có offset được hiểu là giờ Việt Nam rồi đổi UTC; GPS EXIF chỉ là metadata **chưa xác nhận** (`gps_source=exif`, `gps_confirmed=false`).
- Idempotent theo `client_upload_id` cho retry offline; cùng id nhưng bytes khác trả `409`.
- `GET /photos/{id}/original` stream sau kiểm tra membership và kiểm tra path nằm trong storage; header `nosniff`, `no-store`.
- `PATCH /photos/{id}` sửa caption/category/report/work item; JSON `null` xoá field, field bỏ qua giữ nguyên.
- Ảnh chỉ vào snapshot/export khi có `confirmed_caption` hoặc `category` do người dùng chọn; `suggested_caption` một mình không đủ.
- Metadata bổ sung `location`, `component`, `stage`; upload, PATCH và response đều hỗ trợ.
- `GET /photos` lọc theo `date` (ngày capture_time, fallback upload_time theo Asia/Ho_Chi_Minh), `location`, `component`, `stage`, `work_item_id`, `category`, `report_id`; lọc exact-match, luôn project-scoped.
- Lọc `work_item_id` dùng bảng liên kết `photo_work_item_links`; ảnh của project khác không thể lọt qua cùng filter.
- `report_id` và `work_item_ids` phải thuộc đúng project.
- Chặn file rỗng (422), file quá lớn (413, mặc định 50 MB), và chỉ nhận raster image trong allow-list (JPEG/PNG/WebP/AVIF/GIF/BMP/TIFF/HEIC/HEIF). SVG/HTML bị từ chối; ảnh gốc không bao giờ được serve inline nếu MIME không an toàn.

### Lịch sử nghiệm thu theo work item
- Panel read-only trong trang báo cáo, gom work item từ `work_logs` và `next_day_plans` của ngày.
- Ưu tiên `GET /projects/{p}/work-items/{id}/acceptance-history`; nếu endpoint chưa có/404 thì fallback `GET /acceptance-requests` + `GET /acceptance-records` và lọc/ghép theo `work_item_id`/`request_id`.
- Hiển thị số PYC/BBNT, trạng thái, revision, `stale`, warnings nếu API trả; empty/404 hiển thị “Chưa có PYC/BBNT”, không lỗi trang.
- Chỉ đọc; không có nút tạo/sửa/xoá/xác nhận/xuất PYC/BBNT từ site. Nút “Mở Nghiệm thu” chỉ gọi callback điều hướng của app shell nếu được truyền.
- Không gọi AI, không tự suy luận kết quả nghiệm thu.

### Xuất báo cáo
- `POST /daily-reports/{date}/exports` với `format=zalo|pdf|docx|zip`.
- Chỉ xuất khi báo cáo đã `reviewed` (theo MASTER_ARCHITECTURE: xuất từ snapshot đã duyệt). Báo cáo nháp trả `409`.
- Snapshot JSON có hash riêng; lịch sử lưu `GeneratedDocument` + `snapshot_sha256` + `auto_send=false`.
- Zalo/text/PDF/DOCX dùng cùng một nội dung theo mẫu người dùng:
  - tiêu đề lấy từ `Project.report_title`, fallback `Project.name`, cuối cùng là `BÁO CÁO NGÀY`;
  - ngày hiển thị `DD/MM/YYYY`;
  - bốn mục đánh số: `1. Nhân lực`, `2. Công việc thực hiện`, `3. Dự kiến công việc ngày kế tiếp`, `4. Hình ảnh`;
  - mục 3 dùng `plan_date` thật: mọi plan cùng ngày thì ghi `3. Dự kiến công việc ngày DD/MM/YYYY`, khác ngày thì ghi ngày từng dòng; không tự suy ra ngày kế hoạch.
- `work_item_id` của work log/next-day plan được resolve tên từ bảng `work_items` **cùng project**; tên hiển thị cùng vị trí/hạng mục/mô tả đã lưu. Không tự sinh mô tả công việc, số lượng hoặc đơn vị: quantity null bị bỏ qua, quantity `0` vẫn hiển thị `0`.
- `site_notes` chỉ in block “Ghi chú hiện trường” khi có ít nhất một mục non-null; thứ tự Thời tiết, Vật tư, Thiết bị, Sự cố, Khó khăn, An toàn, Kiến nghị, Khác. Không in mục trống.
- Zalo chỉ tạo text và trả `preview_text`; không có endpoint gửi, không tự động gửi. UI có nút sao chép, tải qua lịch sử và nút “Chia sẻ…” chỉ hiện khi `navigator.share` tồn tại.
- Web Share do người dùng bấm; nếu thiết bị không hỗ trợ hoặc chia sẻ lỗi thì fallback sao chép; huỷ chia sẻ không tự gửi/sao chép. Không scrape Zalo.
- PDF dùng PyMuPDF, cố gắng nhúng font Unicode (DejaVuSans/NotoSans) để hiển thị tiếng Việt.
- DOCX dùng `python-docx` khi có, fallback OOXML tối thiểu.
- ZIP gồm `snapshot.json`, `zalo.txt`, `report.pdf`, `report.docx`, và **chỉ ảnh đã xác nhận** trong `photos/`.
- Snapshot ghi rõ `photo_summary.evidence_count`, `omitted_unconfirmed_count`, `evidence_policy`, `auto_send=false`.
- Lịch sử xuất `GET /daily-reports/{date}/exports`; tải file qua `/generated-documents/{id}/download` sau kiểm tra project.

### Cache dữ liệu đã xem (offline read-only)
- Sau khi tải báo cáo thành công, lưu snapshot `(projectId, date)` vào IndexedDB store `views`: report JSON + metadata danh sách ảnh + work items. Không lưu bytes ảnh gốc.
- Khi `GET daily-report` lỗi/offline, dùng snapshot đúng project/date gần nhất; hiển thị nhãn “Đang dùng bản offline · Dữ liệu lưu trên thiết bị, cập nhật lúc …”.
- Không ghi đè server từ cache; cache chỉ là nguồn đọc dự phòng. Draft mới hơn vẫn được ưu tiên cho phần nhập liệu.
- Ảnh trong cache chỉ là metadata; nếu ảnh gốc không tải được khi offline, `AuthenticatedImage` hiện placeholder, không làm hỏng trang.
- Chỉ báo “Đã đồng bộ lúc …” sau khi tải/lưu server thành công; “Đang dùng bản offline” khi đang đọc cache.
- Service worker hiện chỉ cache shell/app assets, bỏ qua mọi `/api/`; test service-worker có sẵn xác nhận API có auth không bị cache.

### Đổi mật khẩu trong app shell (ngoại lệ shared frontend)
- Header khi đã đăng nhập có nút “Đổi mật khẩu” cạnh “Đăng xuất”.
- Dialog mobile-first: mật khẩu hiện tại, mật khẩu mới ≥12, xác nhận; validate client, hiển thị lỗi backend rõ ràng, disable khi đang gửi.
- Gọi `POST /api/v1/auth/change-password` với bearer token hiện tại, body `{current_password,new_password}`.
- Thành công: backend thu hồi token; app xoá token/localStorage, đóng dialog, về màn hình đăng nhập kèm thông báo.
- Lỗi/mất mạng: giữ dialog và token để người dùng thử lại; không tự đăng xuất.

### Mobile-first / offline
- Trang báo cáo một cột, nút lớn, sticky action bar, sticky header online/offline + số mục chờ.
- Nhập nhân lực có ghi chú rõ “để trống = chưa rõ, 0 = không có người”; hiển thị tổng đã biết, nhóm chưa rõ, nhóm 0 người; chọn organization.
- Panel mẫu nhân lực mobile: tạo/sửa/xoá mẫu, chọn organization, bấm “Dùng” để thêm dòng vào báo cáo.
- Form ghi chú hiện trường 8 mục, mở rộng/thu gọn; nội dung trống không vào export.
- Ảnh có control vị trí/hạng mục/giai đoạn khi upload và khi sửa metadata; bộ lọc ảnh theo ngày/vị trí/hạng mục/giai đoạn/công việc.
- Panel lịch sử nghiệm thu theo work item nằm ngay trong trang báo cáo, chỉ đọc và có nút mở trang Nghiệm thu khi app shell truyền callback.
- Work log/next-day plan chọn được work item từ API core, tự điền vị trí/hạng mục/mô tả khi có.
- Tự lưu bản nháp IndexedDB (debounce 400 ms), ưu tiên bản nháp mới hơn bản server.
- Lưu offline: báo cáo và ảnh vào queue IndexedDB; queue id làm idempotency key; tự thử lại khi online và mỗi 15 giây.
- Queue có exponential backoff 5 s → 10 s → 20 s … trần 5 phút; lưu `attempts`, `nextRetryAt`, `status`, `lastError`.
- Sau `QUEUE_MAX_ATTEMPTS = 8` lần lỗi, mục chuyển `failed`, dừng tự retry; người dùng có thể “Bỏ mục” sau xác nhận.
- “Bỏ mục” chỉ xoá đúng item queue đang chọn, không xoá bản nháp/ảnh gốc và không đụng queue project khác.
- Queue được lọc theo `item.projectId === projectId` trước khi tính pending/sync; item của project khác không bị replay, sửa hay xoá.
- Snapshot xem gần nhất được lưu theo `(projectId,date)`; offline mở lại không cần mạng, có nhãn thời điểm cập nhật và không ghi đè server.
- Ảnh chụp/chọn nhiều ảnh; nếu mất mạng giữ nguyên bytes trong IndexedDB và hiện preview chờ đồng bộ.
- Ảnh xem qua fetch có Bearer token (không dùng `<img src>` trực tiếp vì trình duyệt không gắn header Authorization).
- Ảnh chụp trước lần lưu đầu được tự gắn vào báo cáo khi lưu thành công; ảnh queue trước khi có báo cáo được gắn sau khi đồng bộ báo cáo.
- Nút tải file dùng fetch có auth rồi tạo blob URL; nút sao chép Zalo dùng Clipboard API.
- Cảnh báo rõ: không tự động gửi Zalo, ảnh gốc được bảo toàn.

## File đã thay đổi

Backend:
- `backend/app/site/models.py`
- `backend/app/site/dependencies.py`
- `backend/app/site/schemas.py`
- `backend/app/site/service.py`
- `backend/app/site/router.py`
- `backend/tests/site_report/conftest.py`
- `backend/tests/site_report/test_daily_report.py`
- `backend/tests/site_report/test_photos.py`
- `backend/tests/site_report/test_exports.py`
- `backend/tests/site_report/test_scope.py` (mới)
- `backend/tests/site_report/test_access_integration.py` (mới)
- `backend/tests/site_report/test_zalo_format.py` (mới)
- `backend/tests/site_report/test_presets.py` (mới)
- `backend/tests/site_report/test_manpower_team.py` (mới, vòng 5)
- `backend/tests/site_report/test_work_names.py` (mới, vòng 6)

Frontend:
- `frontend/src/features/site/types.ts`
- `frontend/src/features/site/index.ts`
- `frontend/src/features/site/lib/api.ts`
- `frontend/src/features/site/lib/offlineDb.ts`
- `frontend/src/features/site/lib/queueRetry.ts` (mới)
- `frontend/src/features/site/lib/queueRetry.test.ts` (mới)
- `frontend/src/features/site/lib/acceptanceHistory.ts` (mới)
- `frontend/src/features/site/lib/acceptanceHistory.test.ts` (mới)
- `frontend/src/features/site/lib/viewCache.ts` (mới; vòng 7 thêm `shouldLoadCatalogs`)
- `frontend/src/features/site/lib/viewCache.test.ts` (mới; vòng 7 thêm test helper)
- `frontend/src/features/site/lib/manpower.ts`
- `frontend/src/features/site/lib/manpower.test.ts`
- `frontend/src/features/site/lib/datetime.ts`
- `frontend/src/features/site/lib/datetime.test.ts`
- `frontend/src/features/site/lib/offlineDb.test.ts`
- `frontend/src/features/site/lib/manpowerTeam.ts` (mới)
- `frontend/src/features/site/lib/manpowerTeam.test.ts` (mới)
- `frontend/src/features/site/lib/workItems.ts` (mới, vòng 6)
- `frontend/src/features/site/lib/workItems.test.ts` (mới, vòng 6)
- `frontend/src/features/site/hooks/useOfflineSync.ts`
- `frontend/src/features/site/components/ManpowerTable.tsx`
- `frontend/src/features/site/components/ManpowerTeamForm.tsx` (mới, vòng 5)
- `frontend/src/features/site/components/WorkLogForm.tsx`
- `frontend/src/features/site/components/NextDayPlanForm.tsx`
- `frontend/src/features/site/components/PhotoCapture.tsx`
- `frontend/src/features/site/components/ExportPanel.tsx` (mới)
- `frontend/src/features/site/components/SiteNotesForm.tsx` (mới)
- `frontend/src/features/site/components/ManpowerPresets.tsx` (mới)
- `frontend/src/features/site/components/OfflineQueuePanel.tsx` (mới)
- `frontend/src/features/site/components/AcceptanceHistoryPanel.tsx` (mới)
- `frontend/src/features/site/pages/SiteReportPage.tsx` (vòng 7: tách tải danh mục khỏi `remote`)

Shared frontend exception (vòng 5):
- `frontend/src/app/App.tsx`
- `frontend/src/app/ChangePasswordDialog.tsx` (mới)

Tài liệu:
- `docs/agent-reports/site-report.md`

`backend/app/site/models.py` đã bổ sung model/field site-local; migration vẫn do Codex sở hữu (xem schema đề xuất bên dưới).

## API đã triển khai (dưới `/api/v1`)

| Method | Route | Quyền |
| --- | --- | --- |
| GET | `/projects/{p}/daily-reports/{date}` | project member |
| PUT | `/projects/{p}/daily-reports/{date}` | project editor (`project_manager`, `engineer`, admin) |
| GET | `/projects/{p}/manpower-presets` | project member |
| POST | `/projects/{p}/manpower-presets` | project editor |
| PUT | `/projects/{p}/manpower-presets/{id}` | project editor |
| DELETE | `/projects/{p}/manpower-presets/{id}` | project editor |
| POST | `/projects/{p}/photos` | project editor |
| GET | `/projects/{p}/photos?date=&location=&component=&stage=&work_item_id=&category=&report_id=` | project member |
| GET | `/projects/{p}/photos/{id}/original` | project member |
| PATCH | `/projects/{p}/photos/{id}` | project editor |
| DELETE | `/projects/{p}/photos/{id}` | project editor; `204`, giữ ảnh + trả `409` nếu còn là bằng chứng |
| POST | `/projects/{p}/daily-reports/{date}/exports` | project editor |
| GET | `/projects/{p}/daily-reports/{date}/exports` | project member |
| GET | `/projects/{p}/generated-documents/{id}/download` | project member |

Frontend cũng gọi API core có sẵn `GET /projects/{p}/work-items` và `GET /projects/{p}/organizations` để chọn work item/organization.

Mọi route đều nhận user qua FastAPI dependency `require_project_member` hoặc `require_site_editor` (không gọi access helper trực tiếp trong thân endpoint). `test_scope.py` kiểm tra tĩnh để tránh route mới quên project scope hoặc cho viewer ghi dữ liệu.

## Model cần cho tích hợp

Module đang dùng định nghĩa tại `backend/app/site/models.py`, cùng `Base` của core khi có:
- `DailyReport`, `ManpowerEntry`, `ManpowerPreset`, `DailyWorkLog`, `NextDayPlan`
- `SitePhoto`, `PhotoWorkItemLink`
- `GeneratedDocument`

Tích hợp shared hiện tại:
- `Project.report_title` đã có trong `app.core.models` và migration `9f282c0325ea_initial_integrated_schema.py`; UI tạo project đã gửi `report_title`.
- Router đã được mount trong `backend/app/main.py`.
- Migration ban đầu đã có các bảng site (`daily_reports`, `site_photos`, `manpower_entries`, …) và `work_items`/`audit_logs`.
- `SitePhoto.gps_source`/`gps_confirmed` vẫn là field **response-only** (tính từ `gps_lat/lon`), không thêm cột DB.
- Nếu model site thay đổi trong tương lai, cần cập nhật cùng migration chain của Codex; agent không sửa migration.

### Schema additions cần Codex đưa vào migration

Các thay đổi dưới đây đã có trong `backend/app/site/models.py` nhưng **chưa** được thêm migration (agent không sửa `backend/alembic`):

| Bảng | Cột/kiểu | Null/index |
| --- | --- | --- |
| `daily_reports` | `site_notes_json TEXT` | NULL |
| `site_photos` | `location VARCHAR(255)` | NULL, index `ix_site_photos_location` |
| `site_photos` | `component VARCHAR(255)` | NULL, index `ix_site_photos_component` |
| `site_photos` | `stage VARCHAR(80)` | NULL, index `ix_site_photos_stage` |
| `manpower_presets` | bảng mới: `id VARCHAR(36) PK`, `project_id VARCHAR(36) NOT NULL` (index `ix_manpower_presets_project_id`), `group_name VARCHAR(120) NOT NULL`, `person_name VARCHAR(120) NULL`, `count INTEGER NULL`, `organization_id VARCHAR(36) NULL`, `created_at DATETIME NOT NULL`, `updated_at DATETIME NOT NULL` | — |
| `daily_work_logs` | `work_name VARCHAR(500)` | NULL |

`organization_id` tham chiếu logic tới `organizations.id` trong cùng project (service validate; không thêm FK cross-module nếu Codex muốn tránh vòng migration). Original photo path/SHA không đổi; không có cột binary mới.

## Test đã chạy

Backend:
```bash
cd backend
DATABASE_URL="sqlite:////tmp/opencode/site-report-workname-$$.db" \
  ../.venv/bin/python -m pytest tests/site_report -q
# 60 passed
```
Bao phủ:
- `0` vs `null` qua PUT/GET, snapshot và Zalo.
- status/count/group_name không hợp lệ → 422.
- upsert idempotent, 404 báo cáo.
- work log sai thứ tự thời gian → 422; naive time → UTC.
- work item khác project/không tồn tại → 404; request sai không xoá bản nháp cũ.
- ảnh gốc giữ nguyên bytes + SHA + header bảo mật.
- idempotent `client_upload_id`, conflict cùng id khác bytes → 409.
- patch caption/category, JSON null xoá field.
- report/work item cross-project → 404.
- file rỗng → 422, quá lớn → 413, số client id lệch → 422, MIME không phải ảnh → 422.
- EXIF datetime/GPS conversion; GPS không tự xác nhận.
- path ảnh ngoài storage bị từ chối.
- export nháp → 409; Zalo có `0`, “chưa rõ”, không có suggested-only caption, không tự gửi.
- PDF/DOCX/ZIP tạo và tải được; DOCX đọc lại có tiếng Việt.
- ZIP chỉ chứa ảnh đã xác nhận; snapshot giữ `0/null`, `auto_send=false`.
- lịch sử xuất; export/download cross-project → 404; format lạ → 422.
- mọi route có project scope, write route yêu cầu editor.
- integration với core auth/membership thật: outsider 404, viewer đọc được nhưng ghi 403, engineer ghi/upload/export được; export nháp 409.
- audit log được ghi cho upsert báo cáo (actor/project/entity).
- tiêu đề project (`report_title` / fallback tên project / generic), ngày `DD/MM/YYYY` và 4 mục đánh số đúng mẫu.
- mục 3 dùng ngày kế hoạch thật: nếu mọi plan cùng `plan_date` thì đưa ngày vào tiêu đề; nếu khác ngày thì hiện ngày từng dòng; không suy diễn ngày khi không có plan.
- resolve tên work item cùng project cho work log và next-day plan; work item project khác/không tồn tại không được dùng.
- quantity null không sinh số/đơn vị giả; work log không quantity vẫn hiển thị đúng dòng.
- preset CRUD giữ `0`/`null`, validate organization cùng project, cross-project 404, xoá/sửa không ảnh hưởng project khác.
- structured `site_notes` roundtrip 8 mục, mục trống thành null, xuất hiện đúng trong snapshot/Zalo, không tự sinh nội dung.
- ảnh upload/PATCH `location`/`component`/`stage`, lọc theo ngày/vị trí/hạng mục/giai đoạn, cross-project rỗng, bytes gốc không đổi sau khi sửa metadata.
- `organization_id` của manpower report và preset phải thuộc đúng project.
- Lọc ảnh theo `work_item_id` qua bảng liên kết; project khác trả rỗng, work item không tồn tại trả rỗng.
- Normalize lịch sử nghiệm thu từ nhiều shape (`requests`/array/`data`), giữ revision/stale/warnings, ghép BBNT theo request, fallback không tự tạo PYC/BBNT.
- Vòng 6: PUT work log có `work_name` + `location` nhưng không có `work_item_id` → response giữ `work_name`; snapshot có `work_item_name` fallback `work_name`; Zalo có `Tên tại Vị trí`.
- Vòng 6: work log cũ có `work_item_id` vẫn resolve tên từ danh mục và xuất `Work item 1 tại ...`; work log không có location dùng component.

Toàn bộ test site + core hiện có:
```bash
cd backend
DATABASE_URL="sqlite:////tmp/opencode/site-report-combined-$$.db" \
  ../.venv/bin/python -m pytest tests/site_report tests/test_core.py -q
# 62 passed (60 site + 2 core)
```

Lưu ý test harness liên agent: chạy `pytest -q` cho toàn repo hiện có thể lỗi collection vì `tests/engineering_ai/conftest.py` import `app.core.database` trước khi `tests/test_core.py` kịp đặt `DATABASE_URL`, làm engine shared trỏ về DB mặc định. Không được xoá/reset `data/app.db`. Luôn đặt `DATABASE_URL` tạm dưới `/tmp/opencode` trước khi chạy test/migration, ví dụ:
```bash
DATABASE_URL="sqlite:////tmp/opencode/site-report-check-$$.db" \
  ../.venv/bin/python -m pytest tests/site_report tests/test_core.py -q
```
Kết quả đã chạy với DB tạm: 62 passed.

Frontend (Vitest, chạy từ `frontend/`):
```bash
cd frontend
npx vitest run src/features/site
# 9 test files, 59 tests passed
npx tsc --noEmit -p tsconfig.json
# OK
```
Không chạy full `npm run build` trong vòng này để tránh tranh chấp với coordinator; coordinator chạy full gate.
- `summarizeManpower` / `parseManpowerCount` giữ `0` khác `null`.
- `addDaysISO` xử lý cuối tháng/năm nhuận không lệch UTC.
- `datetime-local` luôn hiểu/hiển thị theo Asia/Ho_Chi_Minh (UTC+7), không phụ thuộc timezone thiết bị.
- Queue id báo cáo ổn định theo project+ngày; queue id ảnh duy nhất để retry idempotent.
- Queue offline lọc theo `projectId`: không replay hay xoá item của project khác; item project khác vẫn nằm trong IndexedDB.
- Backoff tăng 5 s → 10 s → 20 s … có trần 5 phút; `attempts` tăng đúng; đạt max 8 thì `failed` và không tự retry.
- Discard chỉ xoá đúng id đã chọn; queue/array gốc và item project khác không bị thay đổi; id giữ nguyên sau lỗi để retry idempotent.
- Trạng thái queue hiển thị pending/failed, số lần thử, thời gian chờ và last error.
- Test acceptance history: normalize payload, lọc theo work item, ghép record theo request, payload rỗng/không hợp lệ trả rỗng.
- Cache snapshot: key theo project+date, chọn bản mới nhất đúng scope, không trả cache project/ngày khác; fallback chỉ khi server lỗi và có cache.
- Nhãn thời gian cache hiển thị theo Asia/Ho_Chi_Minh; payload không hợp lệ không làm hỏng luồng.
- Vòng 6: gom 41 dòng danh mục → 7 tên duy nhất; nhóm đúng 6 loại; giữ option `work_name` ngoài danh mục.
- Vòng 6: `formatWorkLogLabel` trả `Tên tại Vị trí`, fallback component, một phía thì giữ nguyên.
- Vòng 6: `teamToManpowerEntries`/`splitManpowerTeam` giữ nguyên dấu cách đang gõ; `normalizePersonName` chỉ trim/gộp khoảng trắng; dedupe Kỹ thuật vẫn đúng.
- Vòng 6: `formatISODate` hiển thị `DD/MM/YYYY` không lệch timezone.
- Vòng 7: `shouldLoadCatalogs(false) === true` và `shouldLoadCatalogs(true) === false`, bảo vệ quyết định nạp danh mục khi server truy cập được dù ngày chưa có báo cáo. Chưa có test render/E2E cho chính `SiteReportPage` (xem mục 24).

Typecheck/build:
- `npx tsc --noEmit -p tsconfig.json`: **OK**.
- Không chạy full `npm run build` theo yêu cầu coordinator.
- Chưa chạy E2E trình duyệt; UI nhập công việc/nhân lực mới được kiểm tra bằng unit test logic và typecheck. UI đổi mật khẩu chưa được kiểm thử E2E trên thiết bị thật.

## Phụ thuộc

Backend (`backend/requirements.txt` đã có):
- FastAPI, SQLAlchemy 2, Pydantic 2, python-multipart
- PyMuPDF (PDF), Pillow (EXIF), python-docx (DOCX), pytest, httpx

Frontend (do app shell cung cấp):
- React + TypeScript + Vite + Tailwind
- IndexedDB, Fetch, Clipboard API, Web Share API (optional, feature-detected)
- Vitest 4 + Vite 7 + TypeScript 5 (đã có trong `frontend/package.json`)

Biến môi trường:
- `SITE_REPORT_STORAGE` (mặc định `/tmp/opencode/site-report-storage`) — phải đặt thư mục private, bền vững trong triển khai thật.
- `SITE_PHOTO_MAX_BYTES` (mặc định 50 MB).
- `SITE_REPORT_PDF_FONT` (tuỳ chọn) — đường dẫn TTF Unicode cho PDF.

## Vấn đề chưa giải quyết

1. **PDF tiếng Việt**: đã thử nhúng DejaVuSans/NotoSans nếu có trên máy chủ; nếu không tìm thấy font, PDF dùng Helvetica mặc định và có thể mất dấu. Nên cấu hình `SITE_REPORT_PDF_FONT` hoặc thêm font vào image deploy.
2. **DOCX fallback**: khi thiếu `python-docx` mới dùng OOXML tối thiểu (không style). Requirements đã có python-docx nên production nên dùng đường chính.
3. **Offline**:
   - Backoff được kiểm tra theo nhịp sync 15 giây, nên mục đến hạn có thể trễ tối đa ~15 giây; chưa dùng Background Sync/Periodic Sync API.
   - Mục `failed` được giữ lại cho người dùng xem lỗi và bỏ thủ công; không tự xoá dữ liệu.
   - Nếu IndexedDB bị chặn (private mode), app vẫn lưu server khi online nhưng mất khả năng nháp offline.
   - Chưa cache danh sách ảnh/báo cáo đã tải để xem offline; chỉ nháp và ảnh mới nằm trong IndexedDB.
   - Ảnh queue trước khi báo cáo đầu tiên được xử lý **sau** queue báo cáo và gắn theo `reportDate`; nếu báo cáo chưa tồn tại, ảnh tiếp tục chờ trong queue thay vì tạo ảnh unlinked. Trang cũng không tải ảnh unlinked của người dùng khác.
   - Chưa xử lý xung đột nhiều thiết bị cùng sửa một báo cáo (last write wins theo PUT).
   - Chưa kiểm thử thực tế trên iOS/Android: confirm dialog, IndexedDB eviction, Web Share và hành vi khi app bị đóng giữa lúc sync.
4. **Quy tắc export reviewed**: đang bắt buộc `status=reviewed` theo MASTER_ARCHITECTURE. Nếu sản phẩm muốn xuất nháp, cần quyết định lại và nới điều kiện trong `service.create_export` + UI.
5. **GPS**: không có UI xác nhận GPS và không tự động dùng GPS làm bằng chứng; nếu cần GPS đã xác nhận phải bổ sung cột/flow riêng.
6. **Bảo mật upload**: đã kiểm tra raster MIME allow-list, kích thước, path và không serve inline MIME lạ; chưa quét malware, chưa giới hạn số ảnh/request, chưa rate limit (thuộc shared/infra).
7. **Xoá ảnh/báo cáo**: đã có `DELETE /projects/{p}/photos/{id}` (vòng 10); chưa có endpoint xoá báo cáo ngày hoặc snapshot/export.
8. **Excel nguồn**: không đọc/ghi/chỉnh file Excel; module site không dùng template PYC/BBNT.
9. **Migration V2**: các cột/bảng ở mục “Schema additions” chưa có trong `backend/alembic`; Codex cần thêm migration trước khi chạy production. Agent không sửa migration.
10. **Web Share**: nút “Chia sẻ…” phụ thuộc Web Share API của trình duyệt/thiết bị; chưa có E2E trên thiết bị thật. Fallback sao chép đã có, nhưng cần kiểm tra thủ công trên iOS/Android.
11. **Photo filters**: hiện exact-match, chưa phân trang; UI lọc theo report hiện tại. Nếu cần tìm toàn project/xem thư viện ảnh lớn phải bổ sung API pagination.
12. **Organizations**: UI phụ thuộc `GET /projects/{p}/organizations` của core; nếu endpoint lỗi/không có quyền, select tổ chức ẩn và `organization_id` hiện có vẫn được giữ.
13. **Acceptance history endpoint**: `GET /projects/{p}/work-items/{id}/acceptance-history` do acceptance-agent thêm; hiện chưa có trong router. Site đã có fallback `/acceptance-requests` + `/acceptance-records`; shape/revision/stale cuối cùng cần đối chiếu khi endpoint hoàn tất.
14. **Link Nghiệm thu**: `SiteReportPage` nhận prop optional `onOpenAcceptance`; app shell hiện chưa truyền callback nên nút chỉ hiện khi coordinator nối `setPage("acceptance")`.
15. **Acceptance history UI**: chỉ hiển thị work item xuất hiện trong work log/kế hoạch ngày; chưa lấy work item chỉ gắn qua ảnh, chưa phân trang lịch sử.
16. **Offline cache adapter**: logic thuần đã test Vitest; phần ghi/đọc IndexedDB thật chưa có test fake-indexeddb. Cần kiểm tra thực tế trên trình duyệt/PWA.
17. **Cache storage**: mỗi `(projectId,date)` chỉ giữ một snapshot mới nhất; chưa có eviction/giới hạn dung lượng và chưa cache bytes ảnh (đúng chủ đích). IndexedDB đầy/quota sẽ bỏ qua cache, không làm hỏng trang.
18. **Multi-tab/upgrade**: DB_VERSION đã tăng lên 2 để thêm store `views`; nếu tab cũ đang mở giữ kết nối cũ, upgrade IndexedDB có thể bị chặn. Cần kiểm tra đóng/mở nhiều tab.
19. **Service worker**: giữ cache shell hiện tại (`site-assistant-shell-v2`), không cache `/api/`; chưa cần đổi version trong vòng này. Test service-worker hiện có xác nhận API request không được respondWith.
20. **Đổi mật khẩu**: backend đã có `POST /auth/change-password` và thu hồi token; UI mới được typecheck/build, chưa E2E trên trình duyệt/điện thoại thật. Cần kiểm tra luồng đổi thành công → tự về login, lỗi mật khẩu hiện tại và mất mạng.
21. **Migration `work_name`**: đã thêm migration Alembic `a7c3e9f2b641` (sau `e2f6a1c9d430`) cho cột `daily_work_logs.work_name VARCHAR(500) NULL`; đã áp dụng vào `data/app.db`. Test dùng `Base.metadata.create_all` nên không phụ thuộc migration.
22. **Nhóm danh mục công việc**: phân loại dựa trên từ khoá tên (đục / tẩy gỉ / vệ sinh-keo-epoxy / khoan-cấy / lắp đặt-bơm vữa). Nếu danh mục thật đổi tên theo cách không còn từ khoá, cần cập nhật `workItems.ts` và test tương ứng.
23. **UI WorkLogForm**: đã kiểm tra bằng helper test + typecheck, chưa có test render (RTL) hoặc E2E trên thiết bị thật cho thao tác chọn công việc, nhập vị trí và mở/đóng “Chi tiết”. Trường `start_time`/`end_time` cũ vẫn được giữ nguyên trong dữ liệu nhưng không còn nhập từ UI.
24. **Vòng 7 chưa có test render/E2E cho `SiteReportPage`**: repo frontend chưa có React Testing Library nên chỉ kiểm tra bằng helper `shouldLoadCatalogs` + typecheck + Vitest hiện có. Cần kiểm tra thủ công luồng: chọn ngày chưa có báo cáo (GET daily-report 404) → dropdown Công việc và danh mục tổ chức/mẫu nhân lực vẫn có dữ liệu; một API danh mục lỗi không làm mất hai danh mục còn lại.

## Hướng dẫn chạy

Backend:
```bash
cd backend
# Dùng virtualenv hiện có; không xoá/ghi đè data/app.db
DATABASE_URL="sqlite:////tmp/opencode/site-coord-$$.db" \
  ../.venv/bin/python -m pytest tests/site_report -q
```
Không xoá/reset/ghi đè `data/app.db`; mọi test dùng `DATABASE_URL` tạm dưới `/tmp/opencode`.

Toàn bộ test backend (site + core, DB tạm):
```bash
cd backend
DATABASE_URL="sqlite:////tmp/opencode/site-coord-$$.db" \
  ../.venv/bin/python -m pytest tests/site_report tests/test_core.py -q
```

Frontend test/typecheck:
```bash
cd frontend
npx vitest run src/features/site
npx tsc --noEmit -p tsconfig.json
# Full `npm run build` do coordinator chạy.
```

Kiểm tra thủ công sau khi Codex mount router + app shell:
1. Đăng nhập, tạo project, thêm work item (API core).
2. Mở `SiteReportPage` với `projectId` và ngày.
3. Tạo organization (API core), tạo/sửa/xoá mẫu nhân lực, bấm “Dùng” và kiểm tra `0` khác “chưa rõ”.
4. Nhập nhân lực có cả `0` và để trống, chọn organization; lưu nháp; tải lại trang kiểm tra bản nháp còn.
5. Nhập structured site notes, kiểm tra roundtrip và block “Ghi chú hiện trường” khi xuất.
6. Chụp ảnh với vị trí/hạng mục/giai đoạn và gắn work item; sửa metadata; lọc ảnh theo ngày/vị trí/hạng mục/giai đoạn/work item; kiểm tra ảnh gốc vẫn tải được và bytes không đổi; filter work item ở project khác phải rỗng.
7. Tải báo cáo thành công, sau đó ngắt mạng và mở lại cùng project/ngày: phải thấy snapshot gần nhất + nhãn “Đang dùng bản offline · Dữ liệu lưu trên thiết bị, cập nhật lúc …”; ảnh không tải được hiện placeholder, trang không hỏng.
8. Ngắt mạng: sửa báo cáo + chụp ảnh; bật mạng; kiểm tra queue tự đồng bộ, không tạo ảnh trùng, queue project khác không bị đụng.
9. Giả lập lỗi sync liên tiếp: kiểm tra thời gian chờ tăng dần (5 s → 10 s → … → 5 phút), sau 8 lần chuyển “thất bại”, bấm “Bỏ mục” phải xác nhận và chỉ mục đó biến mất; nháp/ảnh gốc còn nguyên.
10. Chuyển báo cáo sang “Đã duyệt”, lưu, xuất Zalo/PDF/DOCX/ZIP.
11. Xác nhận Zalo chỉ hiện nội dung + nút sao chép/chia sẻ; không có hành vi gửi tự động. Trên thiết bị có Web Share, bấm “Chia sẻ…” phải mở hộp thoại hệ thống; huỷ không gửi.
12. Có work item trong work log/kế hoạch: panel lịch sử nghiệm thu hiển thị PYC/BBNT read-only. Khi endpoint history chưa có, fallback danh sách PYC/BBNT phải không làm lỗi trang; empty/404 hiển thị “Chưa có PYC/BBNT”. Nút “Mở Nghiệm thu” cần app shell truyền `onOpenAcceptance`.
13. Nhập “Chỉ huy trưởng” và tên Kỹ thuật có dấu cách ở giữa/cuối: dấu cách phải giữ nguyên khi đang gõ; rời ô (blur) tên được trim/gộp khoảng trắng; thêm/xoá Kỹ thuật và dùng preset vẫn đúng.
14. Khối “Công việc thực hiện hôm nay”: không còn ô giờ bắt đầu/kết thúc; hiển thị “Ngày báo cáo: DD/MM/YYYY”; select chỉ có 7 tên duy nhất chia nhóm; chọn công việc không tự ghi đè Vị trí/component; mở “Chi tiết” thấy số lượng/ĐVT/trạng thái/ghi chú; thêm/xoá dòng và empty state hoạt động.
15. Lưu work log chọn theo tên (không có `work_item_id`), xuất Zalo/PDF/DOCX/ZIP: dòng công việc có dạng `Tên tại Vị trí`; báo cáo cũ có `work_item_id` vẫn hiển thị đúng tên danh mục.
16. Chọn một ngày chưa có báo cáo (GET daily-report trả 404) khi đang online: dropdown “Công việc” trong khối “Công việc thực hiện hôm nay” phải có danh mục; form nhân lực hiện được organizations/mẫu nhân lực. Thử chặn riêng một API danh mục: hai danh mục còn lại vẫn hiển thị. Sau đó lưu báo cáo và kiểm tra hành vi lưu/queue không đổi.
17. Ngắt mạng, mở lại đúng ngày đã có cache: work items/ảnh lấy từ cache như trước; ngày không có cache phải hiện thông báo và không giữ danh mục của ngày khác.

## Cập nhật Tổng quan (Overview) — 2026-11-23

Phạm vi: chỉ Dashboard Tổng quan và hai API đọc mới; không sửa `App.tsx`, điều hướng, migration, `data/` hay `backend/app/engineering_ai`.

### API mới (dưới `/api/v1`)

| Method | Route | Quyền |
| --- | --- | --- |
| GET | `/projects/{p}/overview/latest-day` | project member |
| GET | `/projects/{p}/overview/segments` | project member |

- `latest-day`: lấy ngày lớn nhất giữa `component_progress_events.event_date` và `daily_reports.report_date` của đúng project. Trả `{date, works[], manpower_total, photo_count, daily_report_exists, acceptance_today[]}`. `works[]` gom sự kiện mới nhất theo cặp cấu kiện + định nghĩa bước trong ngày, khóa nhóm gồm `stage_name, zone, segment, component_type, status`; `codes[]` là mã chuẩn đã sắp xếp. `manpower_total` giữ `null` khi chưa có báo cáo/không có số đã nhập (0 vẫn là 0). `photo_count` đếm ảnh có `upload_time` rơi vào ngày địa phương. `acceptance_today` chỉ lấy `AcceptanceRecord.status = confirmed` có `confirmed_at` đúng ngày; không suy ra từ tiến độ. Khi project chưa có cả hai loại dữ liệu: `date=null`, `works=[]`, `manpower_total=null`, `photo_count=0`, `daily_report_exists=false`, `acceptance_today=[]`.
- `segments`: mỗi zone + segment trả `component_count`, `verified_components`, `construction.{not_started,in_progress,completed,blocked,completion_ratio}`, `acceptance.{confirmed,completion_ratio}`. Hai tỷ lệ dùng chung mẫu số là cấu kiện `VERIFIED`; nghiệm thu vẫn lấy từ BBNT đã xác nhận.

### Backend

- `backend/app/core/overview_router.py` (mới): hai endpoint trên, dùng `require_project_member`, model core + site + acceptance; không ghi DB.
- `backend/app/main.py`: import và mount `overview_router`.
- `backend/tests/test_overview.py` (mới): 7 test cho chọn ngày lớn nhất (kể cả khi báo cáo ngày muộn hơn tiến độ), gom `works`, chỉ nghiệm thu thật, project scope/member read, project rỗng và segment summary với hai tỷ lệ độc lập (kể cả cấu kiện chưa xác minh bị loại khỏi tử/mẫu).

### Frontend

- `frontend/src/app/overviewFormat.ts` + `overviewFormat.test.ts` (mới): định dạng ngày `DD/MM`, phần trăm vi-VN, đơn vị cọc/dầm/cấu kiện, nhãn trạng thái, nhãn đoạn, gộp mã duy nhất và dòng “21/11 · Đục bê tông om vỡ · PD2 Cầu chính · 14 cọc hoàn thành”.
- `frontend/src/app/LatestDayCard.tsx` (mới): card “Báo cáo ngày gần nhất”, chip nhân lực/ảnh/báo cáo/nghiệm thu, danh sách mã trong `<details>` native, nút “Mở Hiện trường”; có trạng thái tải/lỗi/rỗng.
- `frontend/src/app/SegmentProgressBars.tsx` (mới): hai thanh độc lập “Thi công” và “Nghiệm thu” cho từng đoạn, sắp theo zone/segment, `role="progressbar"` + `aria-label`; ẩn đoạn chưa có cấu kiện xác minh và có empty state.
- `frontend/src/app/CorePages.tsx` (chỉ `Dashboard`): bỏ 4 card KPI theo work item cũ; thay bằng “Đang thi công”, “Hoàn thành chưa nghiệm thu”, “Đã nghiệm thu”, “Cần xử lý” (hai số giữa lấy từ `progress/summary`, hai số còn lại từ `reconciliation/issues.counts`); thêm card ngày gần nhất và khối tiến độ theo đoạn; đổi mục nhanh thành “Hỏi đáp AI” / “Hỏi nhanh về công trình”.
- `frontend/src/app/ConstructionProgressChart.tsx`: chỉ bổ sung `acceptance?` vào type (không đổi hành vi biểu đồ).

### Kiểm tra đã chạy (DB/storage tạm, không dùng `data/app.db`)

Backend:
```bash
cd backend
DATABASE_URL="sqlite:///$TEMP/overview-test.db" \
  ../.venv/Scripts/python -m pytest tests/test_overview.py tests/test_component_insights.py -q
# 9 passed
```
Full suite trừ module engineering_ai (do agent khác đang sửa):
```bash
DATABASE_URL="sqlite:///$TEMP/full-test-overview.db" \
SITE_REPORT_STORAGE="$TEMP/site-storage-overview" \
ENGINEERING_AI_STORAGE="$TEMP/ai-storage-overview" \
ACCEPTANCE_STORAGE="$TEMP/acceptance-storage-overview" \
  ../.venv/Scripts/python -m pytest -q --ignore=tests/engineering_ai
# 225 passed, 6 skipped, 2 failed, 2 errors — tất cả do engineering_ai
```
Lỗi transient của agent khác, không sửa: thiếu `app.engineering_ai.vision`, `app.engineering_ai.retrieval`, `HashingEmbeddingProvider`, `numeric_cross_check`, `make_scanned_pdf`, và `_shared_session_factory`; collection `tests/engineering_ai` cũng lỗi vì các symbol này.

Frontend:
```bash
cd frontend
npm test        # 32 files, 199 tests passed
npm run build   # OK (chỉ còn cảnh báo chunk >500 kB có sẵn)
```

Kiểm tra đọc trên DB demo thật (`data/storage/demo-live/app.db`, chỉ SELECT):
- `latest-day` → `date=2026-11-21`, một nhóm `Đục bê tông om vỡ dày trung bình t`, Cầu chính/đoạn 2, `COMPLETED`, `count=14`, 14 mã; `manpower_total=null`, `photo_count=0`, `daily_report_exists=false`, `acceptance_today=[]`.
- `segments` Cầu chính: đoạn 1 `completed=44/130`, đoạn 2 `completed=14/86`, đoạn 3 `0/71`; nghiệm thu `confirmed=0` ở cả ba. Hai tỷ lệ tách biệt đúng.

### Ghi chú

- `photo_count` đếm theo ngày upload địa phương; ảnh của báo cáo cũ không bị tính sang ngày mới.
- Tên bước lấy nguyên văn từ `component_stage_definitions.name` (dữ liệu DAP đang có hậu tố “dày trung bình t” do lần nhập trước); API không tự sửa tên.
- Card “Cần xử lý” cộng toàn bộ `counts` đối soát; nếu muốn loại trừ một loại cụ thể cần chỉnh ở frontend.
- Chưa có test render/E2E cho Dashboard mới; mới kiểm tra bằng helper Vitest, typecheck/build và gọi service trên DB demo.

## Wave 2 UI/UX — 2026-11-23

Phạm vi: `frontend/src/app/*`, `frontend/src/features/site/*`, `frontend/vite.config.ts` (không đổi), báo cáo này. Không sửa `frontend/src/features/engineering-ai`, backend, migration hay `data/`.

### Điều hướng

- Menu chính còn đúng 5 mục theo thứ tự: **Tổng quan, Cấu kiện, Hiện trường, Nghiệm thu, Hỏi AI**. Trang `documents` đổi nhãn thành “Hỏi AI” với mô tả “Hỏi đáp về cấu kiện, tiến độ và bản vẽ có dẫn nguồn”.
- “Công trình” và “Công việc” chuyển vào menu “Danh mục & cài đặt” ở đáy sidebar desktop và menu tài khoản top-right trên mobile; cả hai dùng lại `frontend/src/ui/MenuButton.tsx`.
- Bottom nav mobile giữ đúng 5 mục như trên. Page id/state giữ nguyên (`dashboard`, `components`, `daily-report`, `acceptance`, `documents`, `projects`, `work-items`).
- Quick action ở Tổng quan đổi nhãn thành “Hỏi AI” cho khớp điều hướng.

### Code splitting

`App.tsx` dùng `React.lazy` + `Suspense` cho Cấu kiện, Hiện trường, Nghiệm thu và Hỏi AI, với fallback `role="status"` (“Đang tải …”). Trang Tổng quan/Công trình/Công việc vẫn tải ngay.

| Chunk | Trước | Sau |
| --- | --- | --- |
| main `index` | 637,42 kB (gzip 172,71) | **280,53 kB (gzip 84,74)** |
| `ComponentCatalogImport` | — | 117,78 kB |
| `SiteReportPage` | — | 88,35 kB |
| `AcceptancePage` | — | 64,68 kB |
| `EngineeringAIPage` | — | 39,36 kB |
| `datetime` shared | — | 8,20 kB |
| CSS | 57,59 kB | 56,67 kB |

Main chunk giảm ~56% và không còn cảnh báo chunk > 500 kB. Trong lúc làm, `npm run build` có lúc lỗi tạm thời do `features/engineering-ai` đang được agent khác sửa; lần chạy cuối đã build thành công, không sửa file engineering-ai nào.

### Nhập nhanh mã cấu kiện

- Parser thuần `frontend/src/features/site/lib/quickCodeEntry.ts`:
  - tách theo dấu phẩy/chấm phẩy/khoảng trắng/xuống dòng;
  - số trần dùng tiền tố chữ gần nhất: `F67,64,57,55, G65,62, H65 B153 155` → `F67 F64 F57 F55 G65 G62 H65 B153 B155`;
  - mã dầm có gạch giữ nguyên (`I-40-42`, `I40-42`), không phân biệt hoa/thường;
  - bỏ trùng theo thứ tự nhập, giữ danh sách trùng để hiển thị.
- Matcher `analyzeQuickCodes` chỉ tìm trong đúng tập cấu kiện đang lọc (khu vực + phân đoạn; ở Tiến độ trong ngày còn theo bước thi công), khớp `canonical_code` trước rồi `raw_code`; cấu kiện đã chọn hoặc bị trùng được báo là bỏ qua.
- UI `QuickCodeEntry.tsx` hiện xem trước chính xác: số mã khớp, mã khớp, mã không tìm thấy **màu đỏ**, mã trùng/đã chọn; nút “Chọn N cấu kiện đã xem trước” chỉ bấm được khi không còn mã chưa khớp. Không tự chọn từ text.
- Tích hợp ở `DailyProgressPanel` (trong từng dòng công tác, sau khi chọn bước) và `ComponentProgressPanel` (chế độ “Chọn nhiều”, theo khu/phân đoạn đang lọc).

### UX polish đã làm

1. Fallback Suspense có `role="status"` + `aria-live="polite"` để trình đọc màn hình biết trang đang tải.
2. Các mục trong menu tài khoản/overflow và menu “Danh mục & cài đặt” dùng `min-h-11` (≥ 44px); trigger sidebar giữ `app-nav-item` 44px.
3. Dòng “Đang tải dữ liệu…” của Tiến độ trong ngày thêm `role="status"`.
4. Xem trước nhập nhanh dùng `aria-live="polite"`, lỗi mã chưa khớp màu đỏ, trùng/đã chọn màu hổ phách, nút xác nhận bị vô hiệu khi còn mã sai.
5. Giữ nguyên empty state hiện có (chưa có cấu kiện/công tác/phân đoạn) và bổ sung thông báo rõ khi chưa có mã khớp; menu cài đặt có icon và trạng thái `aria-current` khi đang ở trang đó.

### Kiểm tra

```bash
cd frontend
npm test        # 32 files, 200 tests passed
npm run build   # OK, main 280,53 kB, không cảnh báo chunk >500 kB
```

## Wave 3a — Đợt thi công, void/sửa tiến độ — 2026-11-23

### Migration

- Revision mới `a1b2c3d4e5f6` (sau head `639cdb146bf2`): tạo `construction_batches`, `construction_batch_components`; thêm `batch_id`, `voided_at`, `voided_by`, `void_reason` vào `component_progress_events` + index `batch_id`.
- Đã chạy trên bản sao DB tạm ở head cũ, có sẵn 1 sự kiện/project legacy:
  `upgrade head` → `downgrade -1` → `upgrade head`; cả 3 bước giữ nguyên dòng `component_progress_events` cũ, bảng/cột mới xuất hiện rồi biến mất đúng như mong đợi.

### Đợt thi công

- Model: `ConstructionBatch`, `ConstructionBatchComponent` trong `backend/app/core/component_models.py` (khóa chính đôi batch+component).
- Router mới `backend/app/core/batch_router.py`, mount trong `main.py`:
  - list/create/patch batch; detail kèm cấu kiện; preview mã trên **toàn bộ** zone/segment với `matched/ambiguous/missing/already_in_batch`; thêm theo `component_ids` đã chọn tay; bỏ cấu kiện.
  - Mọi thay đổi ghi `AuditLog` (`construction_batch_created/updated/component_added/component_removed`). Member đọc, editor ghi.
  - `primary_zone` = khu xuất hiện nhiều nhất trong đợt, dùng cho badge.
- Bộ lọc `batch_id`: `GET /components`, `/progress`, `/progress/summary`, `/drawing-map`, `/overview/latest-day`, `/overview/segments`.
- Frontend:
  - `useConstructionBatch` lưu lựa chọn theo project trong `localStorage` (`construction_batch:<projectId>`, bọc try/catch) và `useConstructionBatches`.
  - `ConstructionBatchSelector` hiện trên Tổng quan và trang Cấu kiện; truyền `batch_id` vào summary/overview/progress/drawing-map.
  - `ConstructionBatchManager` (trong trang Cấu kiện): tạo đợt, nhập mã, xem trước, chọn tay từng ứng viên mơ hồ, thêm/bỏ cấu kiện.
  - `BatchZoneBadge` hiện “`<Khu> PĐ<segment> · thi công cùng đợt`” cho cấu kiện khác `primary_zone` (ví dụ Bunke PD1 khi đợt chính ở Cầu chính PD2).
  - `DailyProgressPanel` / `ComponentProgressPanel` nhận `batchId` + badge; `DrawingMapPanel` nhận `batchId`.

### Void batch và sửa sự kiện

- `commit_bulk`/`commit_daily` gắn `batch_id` cho mọi `ProgressEvent` (daily dùng id batch ngày, không phải batch từng dòng).
- `POST /progress/batches/{id}/undo` `{reason}`: chỉ trong cùng ngày địa phương, người tạo hoặc `project_manager`/admin; void toàn bộ sự kiện còn hiệu lực của đợt + audit.
- `POST /progress/events/{id}/correct` `{status, reason}`: void sự kiện cũ, tạo sự kiện mới cùng ngày/bước/khối lượng/evidence, `batch_id=null`; audit 2 bản ghi (void + corrected). Lý do bắt buộc, trạng thái trùng trả `409`.
- UI `ProgressHistoryPanel` trong thẻ cấu kiện: xem lịch sử còn hiệu lực, “Sửa” (chọn trạng thái + lý do) và “Hoàn tác đợt” (lý do), mobile-first, nút ≥ 44px.
- Mọi reader trong repo app đã lọc `voided_at IS NULL`: component router/detail/history, insights summary/reconciliation, overview latest-day/segments, drawing map, journal preview, photo-delete usage. `GET progress-events` và history bỏ sự kiện void.

### Engineering AI readers cần tự lọc voided (không sửa theo yêu cầu)

Các file sau vẫn đọc `ProgressEvent` và **phải** thêm điều kiện `voided_at IS NULL` khi agent engineering-ai tiếp tục:
- `backend/app/engineering_ai/database_chat.py` — `_related_rows(db, ProgressEvent, ...)` (~dòng 508, 692), truy vấn `select_from(ProgressEvent)` (~dòng 633), candidate `_event_candidate` (~dòng 751).
- `backend/app/engineering_ai/suggestions.py` — `select(ProgressEvent)` (~dòng 68) và các hàm gợi ý dựa trên danh sách event.
- `backend/app/engineering_ai/progress_parse.py` — truy vấn `select(ProgressEvent)` (~dòng 245) phục vụ parse tiến độ.

Test của hai module này cũng tạo `ProgressEvent` trực tiếp; chưa sửa. Cho tới khi cập nhật, chat/gợi ý AI có thể vẫn thấy sự kiện đã void.

### Kiểm tra

```bash
cd backend
DATABASE_URL="sqlite:///$TEMP/wave3-full.db" ... \
  ../.venv/Scripts/python -m pytest -q
# 350 passed, 6 skipped

cd frontend
npm test        # 32 files, 200 tests passed
npm run build   # OK; main index 292,52 kB, ComponentCatalogImport 130,87 kB, không cảnh báo >500 kB
```

Test mới: `backend/tests/test_construction_batches.py` (scope, preview mơ hồ/không tự chọn, audit, filter components/summary/segments/latest-day/drawing-map), `backend/tests/test_progress_void.py` (quyền creator/PM, cùng ngày, void ẩn khỏi summary/overview/journal, correct void+tạo mới, audit, validation). Chưa có E2E trình duyệt cho batch manager/history.

## Wave 3b — “Dán tin nhắn” — 2026-11-23

### Luồng

- Trang mới `progress-paste` (không thêm vào nav 5 mục), lazy-load:
  - Quick action Tổng quan **“Ghi tiến độ từ tin nhắn”**.
  - Nút **“Dán tin nhắn Zalo để ghi tiến độ”** trong Hiện trường và đầu khối Tiến độ trong ngày (Cấu kiện → Ghi theo ngày).
- Chọn **Đợt thi công** ngay trên trang (dùng `useConstructionBatch`, nhớ theo project); đổi đợt sẽ reset kết quả đọc.
- Textarea lớn + “Dán từ clipboard” (`navigator.clipboard.readText`, fallback hướng dẫn dán tay), ngày mặc định, gọi `POST /projects/{p}/ai/progress-parse` với `{text, default_date, batch_id}`.
- Hiển thị ngày editable, từng dòng công tác, chip mã **gom theo chữ cái đầu**; mã không khớp (`component_id=null`) màu đỏ. Có `<details>` “Xem trên mặt bằng” dùng `DrawingMapPanel` với `selection` tô sáng các mã đã đọc; danh sách chip luôn là fallback.
- Câu hỏi một card/ câu, chọn bằng nút (`aria-pressed`); nút “Xem lại trước khi ghi” chỉ bật khi trả lời đủ. Áp dụng local:
  - dedupe mã trùng;
  - skip mã không có/ngoài phạm vi;
  - chọn stage theo option câu hỏi hoặc select công đoạn từng dòng;
  - “Thi công cùng đợt” → gom `component_ids`, gọi preview batch rồi `POST .../construction-batches/{id}/components`;
  - “Ngày trước là đang làm” → sau khi ghi gọi `POST /progress/events/{id}/correct` cho các `event_ids` trong `apply` với lý do `Theo tin nhắn ngày DD/MM/YYYY: hôm trước đang làm`.
- Preview dùng đúng `daily-preview`; màn xem lại hiển thị số sẵn sàng, cảnh báo, checkbox xác nhận; commit `progress/daily` với key `paste-<date>-<fnv1a>` từ text+ngày. Nếu preview `can_commit=false` thì không cho ghi.
- Sau khi ghi: thẻ kết quả (số sự kiện/sửa/thêm đợt), Zalo summary (ngày, tổng theo loại, mã theo dòng như input, “Chưa nghiệm thu: N cấu kiện đã xong”) + nút Sao chép; danh sách “Đã thi công xong, chưa nghiệm thu” của đợt (lọc `construction_status=COMPLETED` và acceptance khác CONFIRMED/APPROVED) + nút Mở Nghiệm thu.
- Offline: lỗi mạng khi parse/preview/commit lưu text+ngày+đợt vào IndexedDB qua `saveDraft` key `paste:<projectId>`; thông báo “chưa ghi tiến độ, không xếp hàng tự động”. Mở lại trang khôi phục bản nháp; lưu thành công thì xoá draft.

### Helper thuần + test

- `frontend/src/features/site/lib/progressPaste.ts`: `applyPasteAnswers`, `pasteIdempotencyKey`, `buildZaloSummary`, `groupCodesByPrefix`, types bám response parse (kể cả optional `stage_definition_id`, `stage_candidates`, `earlier_events`, `in_batch`, `apply`/`codes`).
- `progressPaste.test.ts` (7 test): golden message 22/11 (26 cọc + 3 dầm) → 8 payload lines, dedupe G65, 3 mã Bunke vào batch, correction cho các sự kiện trước của F-66-67; chặn khi thiếu câu trả lời; skip/replace unknown; manual stage; status confirm; idempotency key; Zalo summary.

### Kiểm tra

```bash
cd frontend
npm test        # 33 files, 207 tests passed
npm run build   # OK; main index 293,67 kB; ProgressPastePanel 20,21 kB; dailyProgress 38,98 kB; không cảnh báo >500 kB
cd ../backend
DATABASE_URL="sqlite:///$TEMP/wave3b-parse.db" ../.venv/Scripts/python -m pytest tests/engineering_ai/test_progress_parse.py -q
# 8 passed (chỉ đọc; không sửa engineering_ai)
```

Lưu ý: parser do agent engineering-ai sở hữu có thể còn chỉnh `apply` hints; UI đọc `apply.event_ids/component_ids/action` và fallback theo `id` câu hỏi. Nếu stage thực tế vẫn mơ hồ ở cấp `component_stage`, daily-preview sẽ chặn commit và người dùng quay lại chọn tay ở luồng hiện có. Chưa có E2E trình duyệt cho luồng dán tin nhắn.

## UI fix wave 1 — 2026-11-23

Phạm vi: `frontend/src/app/*`, `frontend/src/features/site/*`, `frontend/src/style.css`; không sửa engineering-ai/acceptance/backend.

### Tổng quan

- 4 KPI chuyển ngay dưới “Đợt thi công”, dạng 2×2 trên điện thoại và 4 cột desktop.
- “Báo cáo ngày gần nhất” + “Báo cáo ngày” gộp thành một thẻ **Báo cáo ngày**: dòng ngày gần nhất, chip nhân lực/ảnh/báo cáo, danh sách mã, và dòng **“Hôm nay DD/MM: chưa/đã có báo cáo”** kèm nút Tạo/Mở báo cáo hôm nay.
- Bỏ CTA trùng “Cập nhật hiện trường” ở header. “Ghi tiến độ từ tin nhắn” thành nút primary full-width đầu khối Việc nhanh; 4 quick action còn lại nằm dưới.
- Thanh đoạn chỉ hiện đoạn có hoạt động (thi công/đã nghiệm thu) và nút “Xem tất cả (N đoạn chưa hoạt động)”.
- Bỏ eyebrow tên công trình trên Tổng quan (tên đã có ở project selector/sidebar).
- KPI được tính trong đúng batch: lấy rows `/progress?batch_id` và lọc issues đối soát theo component của batch. Nhờ vậy “Hoàn thành chưa nghiệm thu” và chart khớp nhau (trước đây batch PD2 hiện 30/88 nhưng thẻ đối soát hiện 74 toàn công trình; nay 30/30).

### Đợt thi công mặc định

- `useConstructionBatch(projectId, batches, loading)`:
  - Có lựa chọn đã lưu → dùng lựa chọn đó (kể cả “Tất cả đợt” lưu sentinel `__all__`).
  - Chưa có → gọi `/progress?batch_id` cho từng batch, chọn batch có `construction_event` mới nhất (ngày + created_at, đã bỏ sự kiện void); không có hoạt động → tất cả.
  - Batch đã lưu không còn tồn tại → xoá lựa chọn và fallback.
- Screenshot xác nhận mặc định chọn “PD2 Cầu chính (88)”.

### Điều hướng & icon

- Bỏ “Quay lại” ở 5 trang cấp 1 (Tổng quan/Cấu kiện/Hiện trường/Nghiệm thu/Hỏi AI); vẫn giữ ở `progress-paste`/Công việc.
- Thêm `ComponentIcon` (stack) cho Cấu kiện; Hiện trường giữ icon nhà.
- Avatar lấy chữ cái đầu của username (script chụp không set `last_username` nên ảnh vẫn hiện “U”).
- Nhãn bottom nav 12px, nowrap để 5 mục không xuống dòng ở 390px.

### Readability & design tokens (`style.css`)

- Tokens: `--app-text-secondary`, `--app-touch: 2.75rem`, màu thi công not-started xám / in-progress amber / completed green / blocked red, acceptance xanh brand riêng.
- Mobile: body 16px; `.text-xs`/`text-[11px]`/`text-[10px]` nâng 14px; `slate-400/500`, `gray-400/500` đổi sang `#475569`; button/select/tab/input ngày tối thiểu 44px.
- Status chips dùng `.app-status--*` (ComponentProgress, DailyProgress, DrawingMap, chart). Acceptance trong ComponentProgress dùng badge viền `.app-acceptance-badge--*`; thanh nghiệm thu dùng track nét đứt + fill sọc, không cùng fill với thi công.
- Tabs Cấu kiện chuyển sang `app-tab-scroll` (overflow-x, không wrap); nút cuối có thể phải vuốt ngang.
- Sticky action Tiến độ trong ngày chuyển thành một hàng, nằm trên bottom nav; main padding-bottom tăng `pb-60`; trang Hiện trường có padding riêng và save bar nằm trên nav.
- Nút “Lưu báo cáo” đổi từ xanh lá sang brand `#405e9b` để không trùng nghĩa “hoàn thành/đã nghiệm thu”.

### Một entry dán tin nhắn / màn

- Tổng quan: chỉ nút primary “Ghi tiến độ từ tin nhắn”.
- Cấu kiện: chỉ nút trong khối Tiến độ trong ngày (tab Ghi theo ngày).
- Hiện trường: chỉ nút trong header báo cáo ngày.
- Không còn CTA “Cập nhật hiện trường” trùng.

### Before/after (ảnh chụp mới)

`cd C:/Users/Thang Minh Pham/.claude/jobs/0f99d406/tmp/shots && node shoot.js` → `phone errors: []`, `desktop errors: []`.

| Màn | Trước | Sau |
| --- | --- | --- |
| Tổng quan phone | KPI sau ~20 thanh đoạn; 2 thẻ báo cáo; CTA + 5 quick action; eyebrow tên project | KPI 2×2 ngay dưới batch; 1 thẻ “Báo cáo ngày” có dòng hôm nay; primary full-width; đoạn chỉ có hoạt động; không eyebrow |
| Tổng quan desktop | KPI dưới cùng; quick action wrap 5 | KPI 4 cột trên; primary full-width + 4 action; thẻ báo cáo gộp |
| Cấu kiện phone | 5 tab wrap 2 hàng; chưa có nút Quản lý đợt ở selector; sticky 2 tầng | Tab scroll ngang 1 hàng; nút Quản lý đợt; sticky 1 hàng trên nav; batch mặc định PD2 |
| Hiện trường phone | save bar xanh lá ngang nav; ngày 32px | save bar brand nằm trên nav; nút ngày 44px; chữ phụ 14px |
| Nav | Cấu kiện/Hiện trường cùng icon nhà; label wrap | icon stack/nhà khác nhau; label 12px một dòng; không “Quay lại” cấp 1 |

### Kiểm tra

```bash
cd frontend
npm test        # 34 files, 210 tests passed
npm run build   # OK; main 294,49 kB; CSS 59,21 kB; ComponentCatalogImport 92,85 kB; SiteReportPage 85,82 kB
```

Rủi ro/ghi chú: default batch gọi `/progress` cho từng batch khi chưa có lựa chọn — sóng yếu có thể chậm nếu có nhiều đợt; có thể thay bằng endpoint count nhẹ sau. Tabs Cấu kiện phải vuốt ngang để thấy “Nhật ký/Mặt bằng”. Nhãn bottom nav dùng 12px (ngoại lệ so với secondary 14px) để giữ 5 mục trên 390px.

## Design parameters `t_cm` — 2026-11-23

- Migration `b7c8d9e0f1a2` thêm `component_design_parameters` (unique component+name, provenance, audit).
- CLI `scripts/import_design_parameters.py` preview/commit; preview trên bản copy thật: 393 dòng, 392 dòng/392 cọc khớp, 390 cọc có `t`, 2.525 tham số, 1 mã không khớp (`Cầu chính / M263`), 0 mơ hồ/0 xung đột; `A162/A163` thiếu t trong nguồn.
- Tên bước được render `t = X cm`/dải `a–b cm`/`(chưa có số liệu)` trong component detail, history, daily preview, overview latest-day, journal, drawing popup và paste/Zalo summary.
- Chi tiết + test: `docs/agent-reports/site-design-parameters.md`.

## UI/field-work wave 2 - 2026-11-23

Phạm vi: `frontend/src/app/*`, `frontend/src/features/site/*`, `backend/app/site/*`, `backend/tests/site_report/*`, báo cáo này. Không sửa `engineering_ai`, `acceptance`, `data/app.db`, không migration, không commit/push.

### Ảnh gắn cấu kiện (không migration)

- `SitePhoto.component` (text cũ) lưu `@components:{"ids":[...],"label":"F1, F2"}` qua `backend/app/site/photo_components.py`; text cũ không đổi.
- Upload nhận form `component_ids` (csv), PATCH nhận `component_ids`; `PhotoOut.component` trả nhãn, `component_ids` trả id. Lọc ảnh thêm `component_id`.
- Frontend: picker tìm mã trong đợt/zone, mã có tiến độ mới nhất trước, chọn nhiều; chip mã trên thumbnail; bỏ ô "Hạng mục" free-text, giữ chú thích; lọc theo cấu kiện; payload offline có `componentIds`.
- Sau khi ghi tiến độ: nút "Chụp ảnh cho các cọc vừa ghi" mở Hiện trường với các cấu kiện đã chọn trước.
- Rủi ro đã biết: cột `component` khai báo `String(255)` nhưng SQLite không ép độ dài; JSON id nhiều cấu kiện có thể vượt 255 ký tự. Cần migration sang bảng liên kết nếu chuyển DB ép độ dài.

### Câu hỏi dán tin nhắn

- `groupPasteQuestions` gom câu hỏi cùng `kind`; card nhóm có "Áp dụng cho cả nhóm" và mở từng mã để chọn riêng. Frontend-only, API engineering-ai giữ nguyên.

### Bước tiếp theo sau khi lưu

- Nút mở báo cáo ngày đúng ngày, điền ghi chú bằng tóm tắt công việc (không tự lưu; chỉ điền khi ngày khớp và ghi chú đang trống).
- Nút mở nhật ký đúng ngày (tab Nhật ký, ngày đã chọn).
- Nút "Tạo PYC nháp" phát `AcceptanceDraftRequest {projectId,batchId,eventDate,componentIds,componentCodes}` qua `frontend/src/app/acceptanceHandoff.ts` (event `acceptance:create-draft` + sessionStorage `acceptance_draft_request`); module nghiệm thu đọc payload này.

### "Cần xử lý" trên Tổng quan

- Chỉ tính `ACCEPTANCE_WITHOUT_PROGRESS`, `ACCEPTANCE_BEFORE_PROGRESS`, `MISSING_SOURCE`, `DUPLICATE_OR_AMBIGUOUS_CODE`, `UNVERIFIED_COMPONENT`; loại `WORK_WITHOUT_ACCEPTANCE` (bình thường).
- Bấm thẻ "Cần xử lý" mở breakdown theo loại; thẻ "Hoàn thành chưa nghiệm thu" giữ nguyên.
- Screenshot DAP PD2: "Hoàn thành chưa nghiệm thu" 30, "Cần xử lý" 0.

### Mở cấu kiện từ Hỏi AI

- `App.tsx` nghe `engineering-ai:open-component`, chuyển sang trang Cấu kiện, tab Theo cấu kiện, mở editor/detail đúng component; đổi project nếu payload khác project hiện tại.

### Kiểm tra

```bash
cd frontend
npm test        # 34 files, 210 tests passed
npm run build   # OK; main 297,25 kB; ComponentCatalogImport 93,53 kB; SiteReportPage 89,67 kB
cd ../backend
.venv/Scripts/python.exe -m pytest tests -q
# 375 passed, 6 skipped
cd C:/Users/Thang Minh Pham/.claude/jobs/0f99d406/tmp/shots
node shoot.js
# phone/desktop chụp xong; còn 404 /acceptance/pending (thuộc module nghiệm thu)
```

**Chưa kiểm**: E2E bấm luồng dán tin nhắn → bước tiếp theo → PYC nháp (module nghiệm thu đọc payload). Đã bấm thử thẻ "Cần xử lý" trên trình duyệt: breakdown mở và hiện "Không có dữ liệu cần xử lý" với dữ liệu DAP PD2.

## Orchestrator fixes: PYC handoff + photo component links - 2026-11-23

Phạm vi: `frontend/src/app/*`, `frontend/src/features/site/*`, `backend/app/site/*`, một migration mới, test và báo cáo này. Không sửa `frontend/src/features/acceptance`, `engineering_ai`, không commit/push, không ghi `data/app.db`.

### 1. Sửa handoff "Tạo PYC nháp"

- `frontend/src/app/acceptanceHandoff.ts`: bỏ event `acceptance:create-draft` + sessionStorage; giữ type request và thêm `toAcceptanceInitialState()` map camelCase → `{batch_id, event_date, component_ids, stage_definition_id}`.
- `stage_definition_id` chỉ lấy khi tất cả dòng vừa lưu dùng đúng một công đoạn; nhiều công đoạn → `null`.
- `ProgressPastePanel`: request gửi thêm `stageDefinitionIds` lấy từ `savedLines`.
- `App.tsx`: giữ payload trong state `{projectId, state}`, đổi project nếu request thuộc project khác, truyền `initialState` cho `AcceptancePage`. State bị xoá khi rời trang Nghiệm thu hoặc đổi project để không áp dụng lại.
- Test: `frontend/src/app/acceptanceHandoff.test.ts` (2 ca: map đầy đủ + nhiều công đoạn/null batch).

### 2. Photo component links (bỏ mã hoá trong cột `component`)

- Migration `e6f7a8b9c0d1` (head cũ `b7c8d9e0f1a2`) tạo `site_photo_components(photo_id, component_id, project_id, created_by, created_at, PK(photo_id, component_id))`, index `component_id`/`project_id`, FK `photo_id` → `site_photos` cascade.
- Upgrade đọc mọi `site_photos.component` dạng `@components:{...}`, chỉ nhập các id đúng project, rồi đặt cột `component = NULL` (cột chỉ còn caption người dùng).
- Downgrade gom link theo ảnh, dựng lại `@components:{ids,label}` (giữ caption nếu có) rồi xoá bảng — round trip có dữ liệu đã test.
- `SitePhotoComponent` model; `photo_components.py` cung cấp `replace_photo_components`, `photo_component_ids(db, photo)`, `photo_component_label(db, photo)`, validate id theo project.
- Upload/PATCH nhận `component_ids`; PATCH thay toàn bộ link; `PhotoOut` trả `component` (caption) + `component_ids`; filter `component_id` dùng bảng link; xoá ảnh xoá link; export/journal evidence đọc mã qua bảng link.
- Frontend: bỏ fallback chip từ cột `component`, offline queue chỉ gửi `componentIds`, type ghi rõ `component` là caption.
- Test backend: 21 cấu kiện trên một ảnh, filter theo id, cấu kiện project khác → 404, PATCH thay/xoá link; migration round trip có dữ liệu (2 id).

### Kiểm tra

```bash
# Backend
.venv/Scripts/python.exe -m pytest backend/tests -q
# 376 passed, 6 skipped
.venv/Scripts/python.exe -m pytest backend/tests/test_component_migration.py backend/tests/site_report -q
# 97 passed

# Migration thật trên SQLite tạm: upgrade -> downgrade b7c8d9e0f1a2 -> upgrade (log OK)
cd backend
$env:DATABASE_URL="sqlite:///$env:TEMP/photo-links-migration-check.db"
..\.venv\Scripts\python.exe -m alembic upgrade head
..\.venv\Scripts\python.exe -m alembic downgrade b7c8d9e0f1a2
..\.venv\Scripts\python.exe -m alembic upgrade head

# Frontend
cd frontend
npm test        # 35 files, 212 tests
npm run build   # OK; main 297,60 kB; SiteReportPage 89,54 kB
```

Lưu ý vận hành: DB thật cần `alembic upgrade head` trước khi chạy code mới; migration tự chuyển dữ liệu `@components:` cũ. Ảnh legacy có caption text thường (không phải `@components:`) được giữ nguyên.

## Polish luồng dán tin nhắn - 2026-11-23

Phạm vi: `frontend/src/features/site/*` (ProgressPastePanel + helper/test), báo cáo này. Không sửa acceptance/engineering-ai/backend.

- **Công đoạn dễ đọc trên 390px**: nhãn "Công đoạn" nằm trên select, select rộng hết dòng trên mobile (không còn `max-w-56`), và tên công đoạn đã chọn được in lại bên dưới với `break-words`; tên này lấy từ candidate của parser nên giữ đầy đủ hậu tố `t = X cm` do backend đã render.
- **Lỗi 422/409 không im lặng**: `dailyProgressErrorMessage()` đọc `detail` dạng mảng của FastAPI, dịch lỗi ngày tương lai thành "Ngày thi công không được ở tương lai. Chọn hôm nay hoặc ngày trước đó.", và giữ nguyên thông báo backend khác. Lỗi preview hiện ngay dưới nút "Xem lại trước khi ghi"; lỗi lưu hiện ngay trên nút "Ghi tiến độ".
- **Question kind `future_date`**: nhãn nhóm "Ngày trong tương lai"; card câu hỏi generic hiện lựa chọn như các kind khác.
- **Vùng chạm xác nhận**: label checkbox cao tối thiểu 48px (`min-h-12`, padding dọc), checkbox 24px. Khi nút "Ghi tiến độ" bị tắt, có dòng giải thích: chưa tích xác nhận hoặc máy chủ chưa cho phép ghi.
- Test helper: `progressPaste.test.ts` thêm ca dịch lỗi future-date 422, giữ lỗi backend lạ, và nhãn `future_date`.

### Kiểm tra

```bash
cd frontend
npm test        # 35 files, 215 tests
npm run build   # OK; ProgressPastePanel 25,82 kB
```

**Chưa kiểm**: ảnh chụp 390px sau thay đổi (chỉ kiểm bằng type-check/build/test helper).

## Tổng quan "Hôm nay" mobile-first - 2026-11-24

Phạm vi: `frontend/src/app/*`, `frontend/src/features/site/*` (chỉ đọc/dùng helper), `backend/app/core/overview_router.py`, test và báo cáo. Không sửa engineering-ai/acceptance, không migration, không commit/push.

### Màn hình

- Ngay dưới chọn đợt có khối **Hôm nay**:
  - Một nút primary **Ghi tiến độ từ tin nhắn** (đã bỏ nút primary trùng trong “Việc nhanh”).
  - **Đang dở dang**: nhóm theo stage display name (có `t = … cm`), khu và phân đoạn; summary hiện số cấu kiện + số ngày kể từ cập nhật cũ nhất; mở nhóm để bấm từng mã → mở đúng component detail qua `onOpenComponent` của App.
  - **Chờ nghiệm thu**: tổng số + tối đa 3 nhóm từ `/acceptance/pending?batch_id`; nút **Tạo PYC nháp** dựng `AcceptanceDraftRequest` từ toàn bộ cấu kiện đang chờ và đi qua `openAcceptanceDraft`/`toAcceptanceInitialState` sẵn có.
  - **Hôm qua đã làm**: một dòng từ `/overview/latest-day`; nút **Sao chép Zalo** dùng lại `buildZaloSummary` qua helper `buildLatestDayZaloSummary`, có trạng thái đã sao chép/lỗi clipboard.
- KPI, biểu đồ, thanh đoạn, “Việc nhanh” và thẻ báo cáo ngày vẫn nằm dưới. Mỗi khối mới có loading/empty/error riêng.

### Backend

- `GET /projects/{p}/overview/in-progress?batch_id=`: member access, project-scoped, bỏ qua event `voided_at`; lấy event mới nhất theo `created_at/id` của từng cấu kiện, chỉ giữ `IN_PROGRESS`/`BLOCKED`.
- Gom theo stage definition + khu + phân đoạn + loại; `stage_name` dùng `display_stage_name` với `t_cm`; trả `days_since_update`, `last_event_date`, mã/status từng cấu kiện và tổng số. Không cần migration.
- Test `test_in_progress_groups_latest_non_voided_events_by_stage_and_segment`: nhóm/t (3–5 cm), batch filter, COMPLETED không lọt, event voided bị bỏ qua, batch project khác không lộ dữ liệu.

### Kiểm tra

```bash
cd backend
..\.venv\Scripts\python.exe -m pytest tests -q
# 378 passed, 6 skipped
cd ../frontend
npm test        # 35 files, 216 tests
npm run build   # OK; main 310,06 kB
```

Screenshots: **đã chạy** khi app local hoạt động ở 5173/8765 — `node shoot.js` → `phone errors: []`, `desktop errors: []`.

## Mặt bằng trên Tổng quan - 2026-11-24

Phạm vi: `frontend/src/app/*`, `frontend/src/features/site/*`, `backend/app/core/drawing_map_router.py` (chỉ đọc), test, báo cáo. Không migration, không sửa engineering-ai/acceptance.

### Giao diện

- Thẻ **Mặt bằng** nằm ngay dưới khối “Hôm nay”, tái dùng `DrawingMapPanel` ở `variant="compact"` (không copy code render): ẩn bộ lọc/danh sách chi tiết, giữ switcher trang khi có nhiều sheet có marker, khung bản vẽ ~55vh trên điện thoại, nút **Mở toàn màn hình** mở Cấu kiện → tab Mặt bằng.
- Trang chính chọn theo `primary_zone` của đợt (`pickPrimarySheet`); sheet Bunke chỉ xuất hiện trong switcher khi đợt có marker Bunke.
- Marker tô theo trạng thái thi công bằng token hiện có (`--app-construction-*`), viền `--app-acceptance` khi đã nghiệm thu; legend tiếng Việt. Vẫn kéo/chụm zoom, nút +/− và **Vừa khung**.
- Chạm marker mở bottom sheet trong thẻ: mã, công đoạn hiện tại (display name có `t`), ngày cập nhật cuối, trạng thái thi công, nghiệm thu; nút **Mở chi tiết** (mở đúng component) và **Ghi tiến độ** (mở luồng dán tin nhắn).
- Ảnh bản vẽ chỉ tải khi thẻ vào viewport (`IntersectionObserver`), có placeholder nhẹ; đợt không có marker đúng vị trí hiện thông báo rõ. Ảnh full-res vẫn chỉ tải cho sheet đang xem.

### Backend (read-only)

- `drawing_map_router` trả thêm `current_stage_name` (có `t`), `current_stage_definition_id`, `last_event_date`, `accepted` để bottom sheet không cần gọi thêm API. `accepted` lấy từ acceptance link + record `confirmed`, project-scoped.

### Kiểm tra

```bash
cd frontend
npm test        # 35 files, 218 tests
npm run build   # OK; main 310,90 kB; DrawingMapPanel chunk 33,22 kB (lazy)
cd ../backend
..\.venv\Scripts\python.exe -m pytest tests -q
# 379 passed, 6 skipped
cd C:/Users/Thang Minh Pham/.claude/jobs/0f99d406/tmp/shots
node shoot.js   # phone/desktop errors: []
```

Lazy image đã kiểm bằng Playwright: trước khi cuộn `0` request ảnh bản vẽ; cuộn tới thẻ → `1` request, không tải thêm sheet khác. Thẻ compact cao ~60vh trên phone, danh sách 81 mã không còn render trong card.

**Chưa kiểm**: thao tác chạm marker/zoom thật trên thiết bị; bottom sheet mới xem qua code, chưa có E2E tương tác.

## Mặt bằng: fit theo phạm vi cấu kiện - 2026-11-24

Phạm vi: `frontend/src/features/site/*`, test, báo cáo. Không sửa backend/acceptance/engineering-ai.

- **Fit mặc định**: `markerBounds` + `fitViewToBounds` tính bbox điểm marker của sheet đang xem (đã lọc theo đợt), thêm padding 8%, giới hạn zoom 1–4 và pan theo tâm. Cả thẻ Tổng quan và Cấu kiện → Mặt bằng dùng chung logic này; mở sheet/ảnh xong tự fit (ví dụ thực tế 131% thay vì 100%).
- **Vừa khung** quay lại fit bbox; thêm **Toàn tờ** đưa về 100%/pan 0.
- **Thanh zoom** chuyển khỏi overlay trên bản vẽ thành bar dưới ảnh (nút −, %, +, Vừa khung, Toàn tờ; ≥44px); không còn che nét vẽ. Kiểm DOM: `toolbar.top == image.bottom`.
- **Hit area marker**: nút trong suốt đặt `32 / zoom` trong hệ toạ độ đã scale, nên luôn ≥32px trên màn hình kể cả 100%; thực đo 44px do token touch target toàn cục.
- Unit test helper: fit bbox giữa/off-centre, clamp pan, marker rỗng, một điểm + cap zoom 4.

### Kiểm tra

```bash
cd frontend
npm test        # 35 files, 222 tests
npm run build   # OK; main 310,90 kB; DrawingMapPanel chunk 34,21 kB
cd C:/Users/Thang Minh Pham/.claude/jobs/0f99d406/tmp/shots
node shoot.js   # phone/desktop errors: []
```

Playwright kiểm thêm: mặc định 131% → **Toàn tờ** 100% → **Vừa khung** 131%; marker hit area 44×44; thanh zoom nằm dưới ảnh.

## Mặt bằng đa manifest + cấu kiện phát sinh + tọa độ DB - 2026-11-24

Phạm vi được giao: `backend/app/core/*`, `backend/app/site/*`, `frontend/src/app/*`, `frontend/src/features/site/*`, test, `docs/API_CONTRACTS.md`, `docs/DATA_MODEL.md`, báo cáo này; đúng **một** migration mới. Không sửa `backend/app/acceptance`, `backend/app/engineering_ai`, `scripts/import_acceptance_workbook.py`.

### 1. Bản đồ đa manifest, lọc và ảnh an toàn

- `drawing_map_router` đọc **mọi** `data/storage/dap-maps/<key>/manifest.json`, bỏ qua thư mục `expansion`, chỉ nhận key `[a-z0-9_-]`; mỗi manifest vẫn lọc đúng `project_id`.
- Sheet id công khai là `<key>-<sheet.id>` (ví dụ `pd2-beam`), ảnh resolve trong đúng `<key>/`; kiểm `path.parent == root` và `image` chỉ cho tên `*.jpg|*.jpeg`, chặn path traversal. Manifest `pd2` giữ nguyên shape/kết quả.
- Manifest sheet nhận thêm `zone`, `segment` tùy chọn (không bắt buộc với manifest cũ). `GET /drawing-map` nhận `batch_id`, `zone`, `segment`; khi có lọc, chỉ trả sheet còn marker phù hợp nên một đợt trải PD1 + Bunke trả cả hai trang.
- Marker gộp tọa độ DB: cùng `component_id + sheet_id` thì DB thắng manifest; marker DB có `position_id`, `position_status`, `position_note`. Cấu kiện có `RepairScope ADDITIONAL_SCOPE` (không bị `REJECTED`) hoặc `record_origin=ADDITIONAL` mang `origin=ADDITIONAL_SCOPE`.

### 2. Bảng `component_map_positions` và API ghi

- Model `ComponentMapPosition`: `project_id`, `component_id`, `sheet_id`, `points` JSON 0..1, `status DRAFT/REVIEWED`, `source manual`, `created_by/at`, `reviewed_by/at`, `note`; unique `(component_id, sheet_id)`.
- Migration `f8b9c0d1e2f3_component_map_positions.py` nối tiếp head `e6f7a8b9c0d1`; upgrade tạo bảng + 3 index, downgrade xóa bảng, không đụng dữ liệu cấu kiện.
- `PUT /projects/{p}/components/{id}/map-position`: quản lý/kỹ sư; cọc đúng 1 điểm, dầm ≥2; lưu nháp và audit `component_map_position_saved` kèm `before`/`after`, nên di chuyển marker thiết kế tạo override có vết.
- `POST /projects/{p}/components/{id}/map-position/review?sheet_id=`: chỉ `project_manager`, chặn duyệt lại (`409`), audit `component_map_position_reviewed`.
- `POST /projects/{p}/components` nhận thêm `design_group_id`, `approval_reference` (và ghi vào `RepairScope`); thêm `GET /projects/{p}/design-groups` để form chọn nhóm. `record_origin` của nhập thủ công vẫn là `MANUAL_ENTRY`; phạm vi phát sinh nằm ở `RepairScope ADDITIONAL_SCOPE`.

### 3. UI Cấu kiện → Mặt bằng

- Form **Thêm cấu kiện phát sinh** (`AdditionalComponentForm`): mã/mã gốc, loại, phân đoạn mặc định theo `primary_zone` của đợt, nhóm thiết kế tùy chọn, căn cứ/hồ sơ, kiểm tra trùng trước khi tạo, tùy chọn **Thêm vào đợt đang chọn** (mặc định bật khi có đợt). Tạo bằng API cấu kiện hiện có với `scope=ADDITIONAL_SCOPE`.
- Sau khi tạo, `DrawingMapPanel` vào chế độ đặt vị trí: chạm 1 điểm cho cọc, chạm ≥2 điểm cho dầm, kéo từng điểm để chỉnh, **Lưu vị trí nháp**. Nút **Đặt lại vị trí** trên chi tiết marker cũng vào chế độ này để ghi đè marker thiết kế; nút **Duyệt vị trí** hiện khi marker có `position_status=DRAFT`.
- Chuyển trang bị khóa trong lúc đặt để tọa độ không lệch sheet; lưu xong bản đồ tự tải lại và marker phát sinh hiện nét đứt.

### File chính

`backend/app/core/drawing_map_router.py`, `component_models.py`, `component_router.py`, `backend/alembic/versions/f8b9c0d1e2f3_component_map_positions.py`, `backend/tests/test_drawing_map.py`, `backend/tests/test_component_migration.py`, `frontend/src/features/site/lib/drawingMap.ts`, `componentImport.ts`, `api.ts`, `frontend/src/features/site/components/DrawingMapPanel.tsx`, `AdditionalComponentForm.tsx`, `ComponentCatalogImport.tsx`, `frontend/src/features/site/lib/drawingMap.test.ts`, `docs/API_CONTRACTS.md`, `docs/DATA_MODEL.md`.

### Kiểm tra đã chạy

```bash
cd backend
..\.venv\Scripts\python.exe -m pytest -q
# 384 passed, 6 skipped

$env:DATABASE_URL="sqlite:///$env:TEMP/alembic-heads.db"
..\.venv\Scripts\python.exe -m alembic heads
# f8b9c0d1e2f3 (head)

cd ../frontend
npm test        # 35 files, 224 tests
npm run build   # OK; main 311,01 kB; DrawingMapPanel chunk 40,27 kB
```

Backend test mới: đa manifest + `zone`/`segment`/`batch_id`, bỏ `expansion`, ảnh đúng thư mục; tạo vị trí DB cho marker thiết kế (override thắng manifest), cấu kiện phát sinh hiện marker, duyệt vị trí + audit; migration round-trip `e6f7a8b9c0d1 → head → e6f7a8b9c0d1 → head`. Frontend test mới: round-trip screen → tọa độ chuẩn hóa qua zoom/pan, từ chối điểm ngoài ảnh và geometry không hợp lệ.

### Unresolved / chưa kiểm

- Chưa chạy lại screenshot Playwright cho luồng mới: cần backend local khởi động lại để nạp route/model mới; chưa xác nhận app local đang chạy bản mới.
- Chưa có E2E thao tác chạm/kéo thật trên thiết bị; logic đặt điểm dùng chung hàm `clientToSheetPoint` đã có unit test.
- Nếu người dùng bỏ chọn “Thêm vào đợt đang chọn” trong khi đang lọc theo đợt, marker phát sinh sẽ không hiện trên bản đồ lọc đó cho tới khi thêm vào đợt.
- Ảnh bản vẽ vẫn là dữ liệu riêng trong `data/storage/dap-maps`, không đưa vào repo.

## Refactor file lớn + polish thẻ Mặt bằng - 2026-11-24

Phạm vi: `frontend/src/features/site/*`, `frontend/src/app/*`, `frontend/src/features/acceptance/pages/AcceptancePage.tsx` (được phép refactor lần này), test và báo cáo. Không sửa backend, `scripts/`, `frontend/src/features/engineering-ai`, không đổi hành vi API/nghiệp vụ, không commit/stash/reset/push.

### Task A - tách file, giữ nguyên hành vi

| File gốc | Trước | Sau | Ghi chú |
| --- | ---: | ---: | --- |
| `frontend/src/features/site/components/DrawingMapPanel.tsx` | 1854 | 449 | canvas, filters, sheet tabs, detail, placement, list, view controls + 5 hook files |
| `frontend/src/features/site/components/ComponentProgressPanel.tsx` | 1362 | 493 | progress card, toolbar, selection, list, editor/preview/banners + helpers |
| `frontend/src/features/site/components/ComponentCatalogImport.tsx` | 1133 | 433 | tabs, catalog list, import section/preview, candidate card, manual form |
| `frontend/src/features/site/components/DailyProgressPanel.tsx` | 1043 | 478 | header, banners, line card, footer, preview panel + helpers |
| `frontend/src/features/acceptance/pages/AcceptancePage.tsx` | 1625 | 443 | page shell/tabs, requests/records panels, editor, settings, pending, notices + 5 hooks |
| `frontend/src/features/site/lib/drawingMapPanel.ts` | mới | 219 | helper thuần + test 241 dòng |
| `frontend/src/features/site/lib/componentProgressPanel.ts` | mới | 201 | helper thuần + test 304 dòng |
| `frontend/src/features/site/lib/componentCatalogImport.ts` | mới | 71 | helper thuần + test 87 dòng |
| `frontend/src/features/site/lib/dailyProgressPanel.ts` | mới | 151 | helper thuần + test 302 dòng |
| `frontend/src/features/acceptance/pages/acceptancePageModel.ts` | mới | 249 | helper thuần + test 383 dòng |

Tất cả file component/hook mới đều dưới 500 dòng (file lớn nhất: `RecordDraftEditor.tsx` 317, `DailyProgressLineCard.tsx` 374, `DrawingMapCanvas.tsx` 385, `DrawingMapDetailPanel.tsx` 387). Default export, Props, text tiếng Việt, class Tailwind, aria-label và thứ tự request/handler được giữ nguyên; các hook chỉ tách logic stateful, không đổi payload API.

Helper thuần được test thêm: format/label, marker target/colour/dash/aria, placement point/validate, compact aspect, progress filters/editor definitions/quantity groups, catalog labels/tab index/page remaining, daily line/preview labels, acceptance draft/payload/date/error/pending filter.

### Task B - toolbar một hàng và chiều cao thẻ Mặt bằng

- `DrawingMapViewControls` đổi thanh zoom sang một hàng `flex-nowrap`: nút icon −, +, **Vừa khung**, **Toàn tờ** (SVG, giữ nguyên `aria-label`/`title`), phần trăm là text nhỏ `text-[11px]`; nút vẫn ≥44px. Không còn wrap hai hàng ở 390px.
- `DrawingMapCanvas` (compact) bỏ chiều cao cố định `34vh`; dùng `aspect-ratio` theo bbox marker đã fit và tỉ lệ ảnh (`contentAspectRatio`), kẹp `min-h-[45vh] max-h-[65vh]`. Fallback tỉ lệ 1.4 khi chưa có ảnh/bbox; bbox suy biến dùng tỉ lệ ảnh; dầm nằm ngang được kẹp 0.5–3 để không thành dải quá mỏng.
- Thêm test `contentAspectRatio` (bbox thường, rỗng, một điểm, dầm ngang).

### Kiểm tra

```bash
cd frontend
npm test        # 40 files, 292 tests passed
npm run build   # OK; main 311,01 kB; DrawingMapPanel chunk 47,55 kB
```

Sau mỗi file lớn đều chạy lại `npm test` + `npm run build`; các mốc: 237 → 250 → 260 → 272 → 291 → 292 tests.

**Chưa kiểm / screenshot**: backend local tại `127.0.0.1:8765` không có route `map-position` trong OpenAPI (process cũ, không reload), nên bỏ qua screenshot Playwright theo yêu cầu. Chưa có browser/E2E cho toolbar/aspect 390px; kiểm bằng helper test, typecheck và build.

## Cache ảnh bản vẽ có version + derivative + Cache Storage - 2026-11-24

Phạm vi: `backend/app/core/drawing_map_router.py`, `frontend/src/features/site/*`, `frontend/src/app/*`, `frontend/public/sw.js`, test, báo cáo. Không migration, không đổi schema, không sửa backend ngoài router bản đồ.

### Backend

- `image_url` công khai thêm `?v=<12 ký tự>` lấy từ `sha256(mtime_ns:size)` của file gốc; version cache trong bộ nhớ theo `(path, mtime_ns, size)`, xoá entry cũ khi file đổi. Marker vẫn dùng toạ độ 0..1 nên không lệch khi ảnh derivative nhỏ hơn.
- `GET .../drawing-map/{sheet_id}/image`:
  - trả `Cache-Control: private, max-age=31536000, immutable`, `ETag` theo version + variant (`webp`/`jpeg`/`full`), `Last-Modified`, `Vary: Accept`; trả `304` khi `If-None-Match` khớp.
  - mặc định trả derivative dài cạnh tối đa 2400 px, JPEG progressive quality 80 hoặc WebP quality 80 nếu Pillow hỗ trợ WebP và `Accept` có `image/webp`.
  - derivative ghi atomic vào `<key>/.cache/<name>.<version>.<webp|jpg>` (temp + `os.replace`), tái sử dụng nếu đã có; xoá derivative cũ cùng định dạng khi version đổi.
  - `?full=1` trả file gốc JPEG cho deep zoom; vẫn project-scoped + membership check.
  - Pillow lỗi/không đọc được ảnh thì fallback file gốc, không làm hỏng route.
- Frontend gửi `Accept: image/webp,image/jpeg,*/*` khi tải ảnh để nhận WebP.

### Đo dung lượng pd2/beam.jpg

| Biến thể | Bytes | Giảm |
| --- | ---: | ---: |
| Gốc 7500×5300 | 2.704.167 (2,58 MB) | — |
| WebP 2400 px q80 | 178.086 (0,17 MB) | **-93,4%** |
| JPEG progressive 2400 px q80 | 328.249 (0,31 MB) | **-87,9%** |

### Frontend cache

- `drawingImageCache` dùng Cache Storage `drawing-map-images-v1` + memory blob, key là URL versioned (bỏ prefix `/api/v1`), đọc cache trước khi gọi mạng; blob đã có trong memory được dùng ngay (không flash loading), mở lại bản đồ không tải lại nếu version không đổi.
- Ghi cache bọc `try/catch` (quota/lỗi storage không làm hỏng trang), giữ một version mỗi path (dọn version cũ trong memory + Cache Storage).
- Overview compact prefetch ảnh các sheet có marker sau khi render (idle, timeout 2 s), bỏ qua sheet đã có trong memory; ảnh private vẫn tải bằng Bearer token.
- Xoá cache khi login, logout, token hết hạn và đổi mật khẩu để không lộ ảnh giữa người dùng trên cùng trình duyệt.
- Service worker đã bỏ qua `/api/`; `activate` chỉ xoá cache shell cũ (`site-assistant-shell-*`), không xoá cache ảnh.

### Kiểm tra

```bash
cd backend
$env:DATABASE_URL="sqlite:///C:/Users/Thang Minh Pham/AppData/Local/Temp/opencode/full-test-image-cache.db"
..\.venv\Scripts\python.exe -m pytest -q
# 396 passed, 6 skipped

cd ../frontend
npm test        # 41 files, 297 tests passed
npm run build   # OK; main 312,70 kB; DrawingMapPanel chunk 47,96 kB
```

Test backend mới: header immutable/ETag/Last-Modified, 304 theo `If-None-Match`, derivative JPEG/WebP tạo và tái sử dụng (1 lần generate), `full=1` trả gốc, version đổi khi mtime đổi và `image_url` đổi theo, dọn derivative cũ. Test frontend: key versioned, ghi/đọc blob qua memory + Cache Storage, chỉ giữ version mới nhất, bỏ qua network khi blob đã cache, clear khi logout.

**Chưa kiểm**: chưa có browser/E2E đo thời gian mở lại bản đồ hoặc kiểm tra WebP thực tế trên thiết bị; chưa đo dung lượng các sheet còn lại (chỉ pd2 theo yêu cầu). File derivative sẽ nằm trong `.cache` cạnh ảnh gốc trên máy chủ sau lần request đầu.

## Mặt bằng: gesture mượt, hit-test và nhãn công việc - 2026-11-25

Phạm vi: `frontend/src/features/site/*`, `frontend/src/app/*` (không cần sửa), `backend/app/core/drawing_map_router.py` (chỉ thêm field đọc), test, báo cáo. Không migration, không commit/stash/reset/push, không sửa dữ liệu `data/storage/dap-maps`.

### Gesture

- Một wrapper duy nhất giữ ảnh + SVG marker + nhãn + điểm đặt; transform dùng `translate3d(...) scale(...)`, `will-change: transform`. Pointer move chỉ cập nhật qua `requestAnimationFrame`, ghi trực tiếp `style.transform` và `viewRef`; React state chỉ commit khi gesture kết thúc (hoặc nút zoom/wheel).
- Pinch neo theo trung điểm hai ngón (`pinchView`): zoom + pan hai ngón trong cùng một transform. Pan thả tay có quán tính giảm dần, dừng ở biên ảnh. Double-tap zoom 2× quanh điểm chạm, nếu đang ở zoom tối đa thì về 1×. `touch-action: none` giữ nguyên trên canvas.
- Bỏ hàng trăm nút DOM trong suốt; marker/label nằm trong một lớp SVG + lớp nhãn, nên vẫn dính vào ảnh khi pan/pinch.

### Hit-test

- Chạm: đổi toạ độ màn hình -> px, tính khoảng cách tới từng điểm cọc (sai số 22 px) và từng đoạn polyline dầm (14 px). Chọn hình gần nhất; hoà thì ưu tiên dầm.
- Nếu nhiều ứng viên trong 4 px của ứng viên gần nhất, hiện menu nhỏ “Chọn cấu kiện” liệt kê mã thay vì đoán. Marker không thuộc selection bị bỏ khỏi hit-test.
- Marker SVG vẫn có `role="button"`/`tabIndex` và Enter/Space cho bàn phím.

### Nhãn công việc

- Backend thêm `current_work_name` + `current_work_status`: lấy stage của event không void mới nhất; nếu chưa có event, lấy stage chưa làm đầu tiên theo `position` (`NOT_STARTED`). `current_stage_name` cũ giữ nguyên.
- Nhãn dưới cọc / giữa dầm: `mã · tên viết tắt`. Helper `abbreviateWorkName` map `Đục BT`, `Tẩy gỉ`, `Vệ sinh`, `Epoxy`, `Cát nhám`, `Ván khuôn`, `Vữa KCN`, `Sợi TT L1`, `Sơn UV`, `Đổ thải`; fallback 3 từ đầu.
- Màu theo `current_work_status`: xám/amber/lục/đỏ; marker đã nghiệm thu vẫn có viền nghiệm thu. Text có halo trắng, không bắt pointer.
- Mật độ: đầy đủ khi zoom ≥1.3, chỉ mã khi ≥1.05, ẩn dưới 1.05; collision skip đơn giản theo hình chữ nhật screen px. Legend compact đổi sang “Chưa làm / Đang làm / Hoàn thành / Tạm dừng” và ghi rõ nhãn theo công đoạn hiện tại.

### Kiểm tra

```bash
cd backend
$env:DATABASE_URL="sqlite:///C:/Users/Thang Minh Pham/AppData/Local/Temp/opencode/full-test-gestures.db"
..\.venv\Scripts\python.exe -m pytest -q
# 403 passed, 6 skipped

cd ../frontend
npm test        # 41 files, 306 tests passed
npm run build   # OK; DrawingMapPanel chunk 55,27 kB
```

Test mới: khoảng cách điểm-đoạn, hit-test gần cọc/dầm, ưu tiên dầm, trả nhiều ứng viên khi gần nhau; viết tắt 10 công đoạn + fallback; ngưỡng mật độ nhãn và collision; round-trip toạ độ, zoom quanh điểm chạm, pinch giữ trung điểm; backend fallback stage chưa có event.

**Chưa kiểm**: chưa đo 60 fps trên điện thoại thật với 500 marker; chưa có browser/E2E cho double-tap, quán tính và menu chọn. Nhãn vẫn scale theo wrapper trong lúc gesture, chỉ đổi mật độ sau khi thả tay.

## Vùng 14 - công tác chính, viewport một lần và sơ đồ sinh từ mã

Cập nhật: 27/11/2026. Phạm vi: `backend/app/core/main_works.py`, `backend/app/site/main_works_router.py`, `backend/app/site/router.py`, `backend/app/core/drawing_map_router.py`, `backend/app/core/overview_router.py`, test site/drawing/overview; `frontend/src/features/site/*`, test; báo cáo này. Không migration, không sửa `data/storage/dap-maps`, không đổi bảng `component_map_positions`, không commit/stash/push.

### 1. Viewport không tự dời

- Thêm reducer thuần `viewportFitStep` (`frontend/src/features/site/lib/drawingMap.ts`): chỉ trả `fit=true` khi mở sheet lần đầu (ảnh đã sẵn sàng) hoặc khi người dùng bấm "Vừa khung" (`reset`). Các sự kiện `metrics`, `data`, `selection` luôn trả `fit=false`; `gesture` đánh dấu sheet đã được người dùng đổi để không có fit muộn.
- `useDrawingMapViewport` bỏ hiệu ứng reset theo `activeImageUrl`/`imageReloadKey`; hiệu ứng fit dùng reducer, không phụ thuộc label density, selection hay data refresh. Pinch vẫn dùng `pinchView` giữ điểm dưới trung điểm hai ngón tay.
- Test: mở lần đầu fit; sau đó `metrics/data/selection` và gesture không fit; sheet mới chỉ fit khi dữ liệu sẵn sàng; reset mới fit lại.

### 2. Danh mục công tác chính (backend)

`GET /api/v1/projects/{p}/main-works?type=pile|beam` (chỉ đọc, `require_project_member`) trả:

```json
{"works":[{"key","label","component_type","order","stage_definition_ids":[]}],"hidden":[...],"unmapped":[...]}
```

Luật mẫu nằm trong `backend/app/core/main_works.py`; mỗi `StageDefinition` chỉ khớp tối đa một công tác. Danh sách chính thức:

- **Cọc**: 1 Đục bê tông; 2 Tẩy gỉ cốt thép; 3 Vệ sinh bề mặt; 4 Bổ sung/khoan cấy cốt thép; 5 Quét epoxy; 6 Rắc cát tạo nhám; 7 Lắp vỏ composite; 8 Bơm vữa không co ngót; 9 Dán sợi carbon; 10 Sơn bảo vệ.
- **Dầm**: 1 Đục bê tông; 2 Tẩy gỉ cốt thép; 3 Vệ sinh bề mặt; 4 Bổ sung/khoan cấy cốt thép; 5 Quét epoxy; 6 Rắc cát tạo nhám; 7 Ván khuôn; 8 Đổ/bơm vữa; 9 Dán sợi thủy tinh; 10 Sơn bảo vệ.

Kiểm tra trên bản sao chỉ đọc của `data/storage/demo-live/app.db` (sqlite backup sang thư mục tạm): **0 tên chưa map**. Các mục phụ (bao tải, vận chuyển đổ thải, vệ sinh bằng nước, hút nước, đục hà bám, keo gắn cấy, đường hàn, trám vá/trám phẳng, thợ lặn, demo) được trả trong `hidden` (99 dòng trên dữ liệu thật) và không xuất hiện trong picker.

### 3. Picker và tách dòng theo cấu kiện

- `frontend/src/features/site/lib/mainWorks.ts`: kiểu `MainWork`, fetch, tìm công tác theo definition, stage của từng cấu kiện trong công tác, tách payload theo definition, gộp preview/kết quả nhiều nhóm.
- **Ghi tiến độ ngày**: `DailyProgressLineDraft` chuyển từ `stage_definition_id` sang `main_work_key`. Khi gọi preview/save, mỗi cấu kiện được giải về stage riêng trong công tác và tách thành các dòng `stage_definition_id` mà API hiện có cần. Cấu kiện có 0 hoặc >1 stage trong công tác hiện UI chọn bước cụ thể; không tự đoán. Khối lượng nhóm chỉ giữ khi một công tác ra đúng một definition, tránh nhân bản khối lượng.
- **Chọn nhanh/bulk**: picker công tác chính; preview/save tách theo từng definition của từng cấu kiện, gộp kết quả. Idempotency key có hậu tố theo nhóm để retry an toàn.
- **Dán tin nhắn**: chọn công tác chính; nếu một công tác có nhiều biến thể trong tin nhắn/catalog thì hiện thêm "Bước cụ thể" ngay dưới, không đưa toàn bộ catalog vào danh sách chính.
- **Bộ lọc tiến độ**: chọn "Công tác" thay vì "Bước thi công", chip hiện `Cọc/Dầm · tên công tác`.
- **Nhãn bản đồ/Zalo**: `current_work_name` và `stage_name` tổng hợp ngày dùng nhãn công tác chính; `current_stage_name` vẫn giữ tên đầy đủ kèm `t` để hiện chi tiết cấu kiện.

### 4. Sơ đồ sinh từ mã (SVG)

- Không tải ảnh scan mặc định. `useSchematicMapResources` lấy `GET /projects/{p}/progress?batch_id=...` + `GET /main-works`, gộp theo phân đoạn, gộp Bunke vào Cầu chính (batch "PD2 Cầu chính" gồm 2 cấu kiện Bunke + 86 cấu kiện Cầu chính).
- `frontend/src/features/site/lib/schematicMap.ts` phân tích mã: `I49` cọc; `F-66-67` dầm ngang; `A-B-153`/`O-Q-198` dầm dọc; `Q-270` góc; `K-111-112`/`K-1` tấm chắn tàu; mã lạ là "?" ở cuối.
- Trục trái sang phải, bong bóng số trục trên đầu, **nén khoảng trục không dùng** (mỗi trục cách đều, nhãn đầy đủ); hàng ngang từ trên xuống `I,H,G,F`, Bunke `E,D,C,B,A` nằm dưới, có khung nét đứt + chữ "Bunke". Nếu trục Bunke dùng chung với trục chính thì canh thẳng; nếu rời nhau thì dời sang khối bên phải có khoảng cách.
- Cọc = hình tròn nhỏ; dầm = đoạn dày theo màu trạng thái; góc = hình thoi; tấm chắn tàu = hình chữ nhật; trạng thái/nghiệm thu/khung chọn giữ nguyên từ marker cũ.
- Giữ hit-test 22 px cọc / 14 px dầm, chọn khi gần nhau, pinch/pan/quán tính/double-tap, label đầy đủ ≥1.3/chỉ mã ≥1.05, va chạm bị bỏ qua. Fit chỉ lần đầu hoặc "Vừa khung".
- Nút "Bản vẽ gốc" trong chi tiết chỉ tải ảnh scan khi bấm; ảnh lấy qua `fetchDrawingMap` + cache ảnh riêng hiện có.
- Ẩn "Đặt lại vị trí" và panel placement; bảng `component_map_positions` và API vị trí không đổi.

### File chính

- Backend: `backend/app/core/main_works.py`, `backend/app/site/main_works_router.py`, `backend/app/site/router.py`, `backend/app/core/drawing_map_router.py`, `backend/app/core/overview_router.py`, `backend/tests/site_report/test_main_works.py`, `backend/tests/test_drawing_map.py`, `backend/tests/test_overview.py`, `backend/tests/test_design_parameters_api.py`.
- Frontend: `lib/mainWorks.ts`, `lib/schematicMap.ts`, `components/useSchematicMapResources.ts`, `components/SchematicPlanSurface.tsx`, `components/DrawingMapPanel.tsx`, `components/DrawingMapCanvas.tsx`, `components/useDrawingMapViewport.ts`, `components/DailyProgress*.tsx`, `components/ComponentProgress*.tsx`, `components/ProgressPastePanel.tsx`, test `mainWorks.test.ts`, `schematicMap.test.ts`, `dailyProgress.test.ts`, `drawingMap.test.ts`, v.v.

### Kiểm thử

```bash
# Backend, DATABASE_URL trỏ SQLite tạm
.venv\Scripts\python.exe -m pytest backend/tests -q
# 448 passed, 6 skipped

cd frontend
npm test        # 43 files, 321 tests passed
npm run build   # OK
```

**Chưa kiểm**: chưa chạy app local/browser để chụp màn hình sơ đồ thật (không có server đang chạy); chưa đo 60 fps trên điện thoại với 500 marker; chưa có E2E cho pinch/double-tap. Bulk nhiều definition gọi nhiều request preview/save; retry dùng cùng key có hậu tố nhóm nhưng nếu một nhóm lỗi giữa chừng có thể đã ghi các nhóm trước (API bulk hiện tại chỉ một definition mỗi lần).
