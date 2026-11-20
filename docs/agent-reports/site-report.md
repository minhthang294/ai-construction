# Site Report Agent Report

Cập nhật: 18/11/2026 (vòng 9: snapshot nhật ký đã duyệt và xuất file có chứng cứ). Phạm vi chính: `backend/app/site/`, `frontend/src/features/site/`, test tương ứng và file báo cáo này. Ngoại lệ vòng 5 do coordinator giao trực tiếp: chỉ `frontend/src/app/App.tsx` + `frontend/src/app/ChangePasswordDialog.tsx` cho UI đổi mật khẩu. Không sửa `backend/app/core`, `backend/app/models`, migration, module agent khác, Excel nguồn.

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
7. **Xoá ảnh/báo cáo**: chưa có endpoint xoá (không nằm trong contract hiện tại).
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
