# API contracts v1

Prefix `/api/v1`. JSON UTF-8. Auth Bearer; mọi request project-scoped kiểm membership. Ngày `YYYY-MM-DD`, timestamp ISO-8601 có múi giờ. Lỗi `{detail, code}`; `403` thiếu quyền, `404` resource không thuộc project, `409` xung đột trạng thái, `422` dữ liệu sai.

`POST /auth/login` cấp bearer token 12 giờ; `POST /auth/logout` thu hồi token hiện tại.

| Route | Ý nghĩa |
| --- | --- |
| `POST/GET /projects` | Tạo và liệt kê công trình được phép; `can_delete` dành cho quản trị viên và quản lý công trình |
| `DELETE /projects/{p}` | Xóa mềm, trả `{id}`, giữ hồ sơ liên quan và ghi audit. Công trình đã xóa bị ẩn và các API theo công trình trả `404`. |
| `POST/GET /projects/{p}/work-items` | Danh mục công việc, import có preview trước khi lưu |
| `GET /projects/{p}/segments?zone=...` | Các phân đoạn đã nhập trong công trình |
| `GET /projects/{p}/components?q=...` | Danh mục theo project; `q` khớp mã chuẩn hoặc alias; lọc `zone`, `segment_id`, `type`, `group_id`, `scope` |
| `GET /projects/{p}/components/{id}` | Mã gốc/chuẩn, nhóm thiết kế, nguồn seed, phạm vi và các dòng DM liên quan |
| `POST /projects/{p}/components` | Tạo cấu kiện thủ công: `{segment_id, type, raw_code, canonical_code, scope, aliases?}`; chỉ quản lý/kỹ sư, segment cùng project, trả `201` |
| `POST /projects/{p}/components/import-preview` | Upload seed XLSX; trả candidates, liên kết DM, hash và conflicts; không ghi DB |
| `POST /projects/{p}/components/import-commit` | JSON `{reviewed: true, idempotency_key, preview, source_file_base64}`; đối chiếu lại file, từ chối xung đột, ghi audit trong transaction |
| `GET/POST /projects/{p}/stage-definitions?type=` | Định nghĩa bước thi công theo project + loại cấu kiện (`pile`/`beam`); đọc cho member, tạo cho quản lý/kỹ sư |
| `POST /projects/{p}/components/{id}/repair-scopes` | Đề xuất phạm vi sửa chữa `{kind, approval_reference?}`; `revision` tự tăng theo cặp component + kind, trạng thái `NEEDS_REVIEW` |
| `POST /projects/{p}/components/{id}/repair-scopes/{scope_id}/review` | Duyệt phạm vi `{decision: VERIFIED\|REJECTED, approval_reference?, note?}`; chỉ `project_manager`; chỉ scope `NEEDS_REVIEW` |
| `POST /projects/{p}/components/{id}/stages` | Gắn một định nghĩa bước vào cấu kiện và một phạm vi sửa chữa; không tự sinh bước mặc định |
| `GET/POST /projects/{p}/components/{id}/progress-events` | Nhật ký thi công append-only `{stage_id, event_date, status, quantity?, unit?, note?, evidence_refs?}`; lọc `stage_id` |
| `GET /projects/{p}/progress` | Tổng hợp tiến độ theo cấu kiện; lọc `q`, `zone`, `segment_id`, `type`, `group_id`, `scope`, `origin`, `stage_definition_id`, `construction_status`, `acceptance_status`; trả hai cột độc lập `construction_status` và `acceptance_status` |
| `POST /projects/{p}/progress/design-quantities` | Tra khối lượng thiết kế khi mở ghi tiến độ. Nhận `{component_ids: string[]}` với tối đa 500 mã ID duy nhất của công trình. Trả bản đồ theo ID bước thi công. |
| `POST /projects/{p}/progress/bulk-preview` | Kiểm tra đúng danh sách `component_ids[]` với một `stage_definition_id`; `stage_selections[]` (`{component_id, stage_id}`) bắt buộc khi một cấu kiện có nhiều bước cùng định nghĩa; trả cấu kiện thiếu, bước thiếu, danh sách mơ hồ/không khớp, cảnh báo và `can_commit`; không ghi DB; kiểm `evidence_refs` cùng project |
| `POST /projects/{p}/progress/bulk` | Ghi hàng loạt sau khi duyệt: `{reviewed: true, idempotency_key, ...bulk-preview}`; kiểm lại đúng danh sách, `stage_selections`, bước và evidence trong transaction; mơ hồ/không khớp trả `409`; ghi `ProgressEvent` và audit; trả `201` |
| `POST /projects/{p}/progress/daily-preview` | Xem trước nhiều công tác cùng ngày. Nhận `{event_date, lines:[{stage_definition_id, component_ids, stage_selections?, status, group_quantity?, group_unit?}]}`; trả `{can_commit, lines, warnings}`. |
| `POST /projects/{p}/progress/daily` | Ghi toàn bộ công tác trong một giao dịch. Thêm `reviewed: true` và `idempotency_key` vào payload preview. Trả `{created, lines}`. Khối lượng cấp nhóm giữ ở bản ghi nhóm, khối lượng từng cấu kiện để trống. |
| `GET /projects/{p}/drawing-map` | Mặt bằng đã đối chiếu. Mỗi sheet có trang, mã bản vẽ, URL ảnh và các marker theo ID cấu kiện cùng dự án. |
| `GET /projects/{p}/drawing-map/{sheet_id}/image` | Trả ảnh riêng cho thành viên dự án. |
| `GET /projects/{p}/progress/summary` | Tổng hợp project-scoped trên cấu kiện đã duyệt: tổng/đã duyệt/chờ duyệt, số có phạm vi phát sinh, 4 trạng thái thi công + tỷ lệ, liên kết/xác nhận nghiệm thu + tỷ lệ; hai tỷ lệ độc lập |

Mỗi giá trị trả về từ `progress/design-quantities` gồm `quantity` (số hoặc `null`), `unit`, `scope` (`COMPONENT`, `SHARED` hoặc `SUBGROUP`), `scope_label`, `drawing`, `page` và `note`. Khối lượng dùng chung cho cụm hoặc phân nhóm được tra theo phạm vi đã ghi. API yêu cầu quyền thành viên công trình và chỉ đọc số liệu thiết kế.
| `GET /projects/{p}/reconciliation/issues` | Đối soát chỉ đọc: nghiệm thu không có thi công, thi công xong chưa nghiệm thu, thiếu nguồn, cấu kiện chưa duyệt, mã trùng/mơ hồ, BBNT xác nhận trước ngày thi công; trả `issues[]` và `counts` theo loại |
| `GET /projects/{p}/journals/{date}/preview` | Xem trước nhật ký ngày từ báo cáo ngày, sự kiện tiến độ và BBNT đã xác nhận; trả `preview_sha256`, `snapshot_eligible`, chứng cứ đã xác nhận và mục trống; chỉ đọc, không tự điền |
| `POST /projects/{p}/journals/{date}/snapshots` | Tạo snapshot bất biến từ đúng preview đã duyệt: `{reviewed: true, preview_sha256}`; lưu JSON + ảnh chứng cứ đã xác nhận, từ chối nếu preview đổi hoặc báo cáo ngày còn nháp |
| `GET /projects/{p}/journals/{date}/snapshots` | Danh sách snapshot đã duyệt của ngày, kèm hash, người/giờ duyệt, số chứng cứ/BBNT và URL tải JSON |
| `POST /projects/{p}/journals/{date}/exports` | `{snapshot_id, format: pdf\|docx\|zip}`; chỉ render từ snapshot đã duyệt, ZIP kèm ảnh chứng cứ đã lưu trong snapshot; trả `201` |
| `GET /projects/{p}/journals/{date}/exports` | Lịch sử file nhật ký đã xuất từ snapshot |
| `PATCH /projects/{p}/work-items/{id}` | Sửa tên/vị trí/cấu kiện/trạng thái công việc; ghi audit |
| `POST/GET /projects/{p}/organizations` và `/personnel` | Danh sách đơn vị và nhân sự theo công trình; nhân sự chỉ tham chiếu đơn vị cùng công trình |
| `PUT/GET /projects/{p}/daily-reports/{date}` | Bản nháp báo cáo, gồm `manpower[]`, `work_logs[]` (`work_item_id?`, `work_name?`, `location`, `component`, số lượng/trạng thái/ghi chú), `next_day_plans[]`, `notes`, `site_notes`; không còn giờ bắt đầu/kết thúc trên UI; upsert idempotent |
| `GET/POST /projects/{p}/manpower-presets` và `PUT/DELETE /projects/{p}/manpower-presets/{id}` | Preset nhóm nhân lực theo công trình, chỉ dùng khi người dùng chọn |
| `POST/GET /projects/{p}/photos` | Multipart upload nhiều ảnh; metadata location/component/stage và lọc `date`, `location`, `component`, `stage` |
| `GET /projects/{p}/photos/{id}/original` | Stream file sau kiểm quyền |
| `DELETE /projects/{p}/photos/{id}` | Xóa ảnh cùng công trình với quyền biên tập, trả `204`. Ảnh đang làm bằng chứng trả `409`. |
| `POST /projects/{p}/daily-reports/{date}/exports` | `format=zalo|pdf|docx|zip`, bản chụp nội dung và history |
| `POST/GET /projects/{p}/documents` | Upload PDF, version theo hash; liệt kê trạng thái ingest |
| `GET /projects/{p}/documents/{id}/pages/{n}` | Trang gốc/render và OCR, yêu cầu quyền |
| `GET /projects/{p}/documents/{id}/versions` | Danh sách version, is_current/is_effective, change_note |
| `POST /projects/{p}/documents/{id}/effective` | Người quản lý hồ sơ xác nhận revision hiệu lực; lưu effective_at/by |
| `GET /projects/{p}/documents/{id}/compare/{other_id}` | So sánh metadata/trang/chunk hai version, không kết luận thiết kế |
| `POST /projects/{p}/ai/search` | Query và citation từ page/chunk; rỗng nếu không có nguồn; `scope=effective|history` |
| `POST /projects/{p}/ai/chat` | Trả `{answer,citations[],confidence}`; thiếu nguồn dùng câu từ chối chuẩn; `scope`, tùy chọn vision một trang |
| `POST/GET /projects/{p}/ai/conversations` | Tạo mới/liệt kê; tìm kiếm `q` |
| `PATCH/DELETE /projects/{p}/ai/conversations/{id}` | Đổi tên/xóa hội thoại |
| `POST /projects/{p}/ai/cross-references` | Đối chiếu hai trang tài liệu; nhận xét chỉ để kỹ sư rà soát, kèm citation cả hai trang |
| `POST /projects/{p}/ai/photo-suggestions` | Gợi ý phân loại/chú thích ảnh chưa xác nhận; không ghi đè ảnh gốc |
| `POST /projects/{p}/ai/daily-report-drafts` | Soạn bản nháp từ dữ liệu báo cáo đã ghi, chỉ ra trường còn thiếu; không tạo số liệu |
| `POST /projects/{p}/ai/inspection-checklists` | Gợi ý checklist có citation tài liệu; không điền trạng thái nghiệm thu |
| `POST/GET /projects/{p}/acceptance-requests` | PYC nháp và lịch sử, liên kết work item/daily report cùng công trình |
| `DELETE /projects/{p}/acceptance-requests/{id}` | Xoá PYC; PYC có BBNT yêu cầu `?force=true` và xoá kèm BBNT/lịch sử export |
| `GET/PUT /projects/{p}/acceptance-numbering` | Cấu hình prefix/start/width/reset policy cho PYC/BBNT |
| `POST /projects/{p}/acceptance-requests/{id}/preview` | Preview dữ liệu điền template trước khi xuất |
| `GET /projects/{p}/acceptance-requests/{id}/preview-image` | Ảnh PNG của trang PYC đã điền, không tạo lịch sử export |
| `POST/GET /projects/{p}/acceptance-records` | BBNT nháp và checklist |
| `POST /projects/{p}/acceptance-records/{id}/revisions` | Tạo revision BBNT mới, giữ bản cũ |
| `GET /projects/{p}/work-items/{id}/acceptance-history` | Lịch sử PYC/BBNT theo work item |
| `POST /projects/{p}/acceptance-records/{id}/confirm` | Người có quyền xác nhận, ghi audit |
| `POST /projects/{p}/acceptance-records/{id}/exports` | Excel sao chép template PYC/BBNT; PDF PYC chỉ giữ trang PYC, PDF BBNT chỉ giữ trang BBNT; tên tải PYC dạng `YC-<số phiếu>.pdf` |
| `GET/POST /projects/{p}/acceptance-participants` | Danh mục người tham gia theo vai trò; `PUT/DELETE .../{id}` |

`DailyReport.status`: `draft|reviewed`; `AcceptanceChecklist.state`: `yes|no|unconfirmed`; `AcceptanceRecord.result`: `approved|conditional|rejected|null`. `null` là chưa có quyết định. `PhotoEvidence` chỉ dùng ảnh với caption/category đã được người dùng xác nhận. Citation gồm `document_id`, `document_name`, `version`, `page_number`, `drawing_number?`, `revision?`, `quote`, `url`, `ocr_confidence?`.

Import cấu kiện hiện chỉ hỗ trợ cấu trúc workbook seed. `reviewed` là xác nhận của người gọi API; commit chỉ chấp nhận dữ liệu khớp workbook gửi lại. Giao diện cho phép xem trước, lọc và duyệt, nhưng chưa sửa từng candidate: cần sửa workbook và xem lại. Import chỉ bổ sung và không xóa cấu kiện thiếu trong file. Không tạo tiến độ hay nghiệm thu từ ngày có trong seed.

Tạo cấu kiện thủ công ghi `verification=NEEDS_REVIEW`, `record_origin=MANUAL_ENTRY`, phạm vi `NEEDS_REVIEW` và để trống SHA nguồn, dòng nguồn, người/ngày duyệt cùng `approval_reference` thay vì suy diễn. `raw_code`, `canonical_code` và alias dùng chung một không gian định danh duy nhất theo project + segment + type; trùng trả `409`. Import giữ idempotency và vẫn yêu cầu đối chiếu thủ công khi gặp cấu kiện thủ công cùng mã.

Phạm vi sửa chữa: đề xuất luôn tạo bản ghi mới với `verification=NEEDS_REVIEW`; `DESIGN_SCOPE` và `ADDITIONAL_SCOPE` có dải `revision` riêng. Duyệt `VERIFIED` phải có `approval_reference` (bắt buộc với `ADDITIONAL_SCOPE`, tùy chọn với `DESIGN_SCOPE`); `REJECTED` không cần. Chỉ scope `NEEDS_REVIEW` được duyệt một lần, sau đó trả `409`; mọi lần duyệt ghi `reviewed_by`, `reviewed_at` và audit `repair_scope_reviewed`.

Bước thi công: `StageDefinition` thuộc project và đúng một loại cấu kiện; `ComponentStage` gắn định nghĩa với cấu kiện và đúng một `RepairScope` của cấu kiện đó. Cùng một định nghĩa bước có thể gắn lại cho phạm vi sửa chữa khác của cùng cấu kiện, nhưng không lặp trong cùng một phạm vi. Không có bộ bước mặc định cho mọi cọc/dầm; client chọn định nghĩa. Định nghĩa/bước trùng, sai project hoặc sai loại trả `409`/`404`; ghi audit khi tạo.

`ProgressEvent` là append-only: không có `PATCH`/`DELETE`, sửa sai bằng cách thêm event mới. Event bắt buộc `event_date` do người dùng nhập (không suy ra từ seed hay AI), `status` thuộc `IN_PROGRESS|COMPLETED|BLOCKED`; `quantity` không âm; `evidence_refs[]` tối đa 20, mỗi chuỗi 1–120 ký tự. Bằng chứng phải phân giải được trong cùng project: ảnh đã xác nhận (`<id>` hoặc `photo:<id>`), `document:<id>`, `page:<page_id>` hay `page:<document_id>:<page_number>`; sai project/không tồn tại trả `404`, ảnh chưa xác nhận hoặc ref sai định dạng trả `422`. Bảng `component_progress_events` dùng chung với luồng cập nhật hàng loạt của module site (`component_progress_batches` giữ idempotency cho bulk); trạng thái hiện tại của bước là status của event có `created_at` lớn nhất, timeline hiển thị theo `event_date`. Tiến độ thi công chỉ đọc/ghi bảng tiến độ, không tạo, sửa hay suy ra trạng thái nghiệm thu và không ghi vào module acceptance. Quyền ghi đề xuất/bước/tiến độ là `project_manager|engineer`; duyệt phạm vi là `project_manager`; đọc là member.

`progress/summary` chỉ tính cấu kiện `verification=VERIFIED`; trạng thái thi công của cấu kiện là status của event có `created_at` lớn nhất (`NOT_STARTED` nếu chưa có). `acceptance.linked` đếm cấu kiện có link PYC/BBNT; `acceptance.confirmed` chỉ đếm link tới BBNT `status=confirmed`. Hai tỷ lệ độc lập, cùng chia cho số cấu kiện đã duyệt; không suy ra nghiệm thu từ thi công. `reconciliation/issues` là read-only, project-scoped; loại issue gồm `ACCEPTANCE_WITHOUT_PROGRESS`, `WORK_WITHOUT_ACCEPTANCE`, `MISSING_SOURCE`, `UNVERIFIED_COMPONENT`, `DUPLICATE_OR_AMBIGUOUS_CODE`, `ACCEPTANCE_BEFORE_PROGRESS`; mỗi issue có cấu kiện, khu, phân đoạn, mô tả và mã tham chiếu liên quan.

Bulk progress: mỗi dòng preview trả `stage_options` (các bước cùng định nghĩa), `stage_ambiguous` và `stage_id` đã chọn. Nếu một cấu kiện có hơn một bước cùng `stage_definition_id`, client phải gửi `stage_selections` cho đúng cấu kiện; server không tự chọn bước đầu tiên. Preview và commit phải dùng cùng `stage_selections`; commit thiếu lựa chọn, lựa chọn không thuộc cấu kiện/định nghĩa hoặc cấu kiện đã đổi trả `409`. `evidence_refs` được kiểm project-scoped ở cả preview và commit bằng `app.core.evidence.validate_evidence_refs`; ref sai project/không tồn tại `404`, ảnh chưa xác nhận hoặc sai định dạng `422`.

Tổng hợp tiến độ của site trả `construction_status` (`NOT_STARTED|IN_PROGRESS|COMPLETED|BLOCKED`) và `acceptance_status` riêng. `acceptance_status` chỉ lấy từ liên kết tường minh `component_acceptance_links`: không có liên kết `NOT_LINKED`; có PYC/BBNT nhưng chưa xác nhận `PENDING`; BBNT đã xác nhận theo `result` thành `APPROVED|CONDITIONAL|REJECTED|CONFIRMED`. `acceptance_count` là số BBNT đã xác nhận. Không suy ra nghiệm thu từ tiến độ. Bulk progress bắt buộc `reviewed: true`, giữ nguyên đúng `component_ids[]` đã xem trước và một `stage_definition_id`; cấu kiện chưa gắn bước bị từ chối, không tự gắn bước. `component_progress_batches` chỉ lưu idempotency/result của bulk; event vẫn append-only trong `component_progress_events`. Nhật ký ngày: preview trả `blank_sections`, `warnings`, `preview_sha256`, `snapshot_eligible`, chứng cứ ảnh đã xác nhận và chỉ lấy BBNT `confirmed` đúng ngày xác nhận; không tạo sự kiện thi công/nghiệm thu giả. Snapshot yêu cầu `reviewed: true` + đúng `preview_sha256`; báo cáo ngày nháp chặn snapshot (`409`). Snapshot lưu JSON bất biến cùng bản sao ảnh chứng cứ đã xác nhận; tham chiếu ảnh chưa xác nhận/không phân giải bị bỏ và ghi cảnh báo, không tự liên kết. Export chỉ đọc snapshot đã duyệt, kiểm hash file/tham chiếu; PDF/DOCX nêu danh mục chứng cứ, ZIP kèm bytes; không đọc lại dữ liệu live và không tạo nghiệm thu.

Checklist `evidence_refs[]` chấp nhận ID ảnh cùng công trình (hoặc `photo:<id>`), `document:<id>`, `page:<page_id>` hay `page:<document_id>:<page_number>`. Ref không phân giải được hoặc trỏ sang công trình khác bị từ chối; trạng thái checklist chỉ do người dùng nhập.
