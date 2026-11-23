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
| `GET/POST /projects/{p}/construction-batches` | Danh sách đợt thi công (mặc định bỏ đợt đã lưu trữ) và tạo đợt `{name, note?}`; trả kèm `component_count`, `primary_zone`; cần quyền biên tập để tạo |
| `GET/PATCH /projects/{p}/construction-batches/{id}` | Chi tiết đợt kèm cấu kiện (mã, khu, phân đoạn, lý do) hoặc đổi tên/ghi chú/lưu trữ; ghi audit |
| `POST /projects/{p}/construction-batches/{id}/components/preview` | Xem trước mã trên **toàn bộ** khu/phân đoạn: `{codes:[...]}` trả `matched[]`, `ambiguous[]` (nhiều ứng viên), `missing[]`, `already_in_batch[]`; không tự chọn khi mã mơ hồ |
| `POST /projects/{p}/construction-batches/{id}/components` | Thêm cấu kiện đã chọn tay `{component_ids:[...], reason?}`, bỏ qua mục đã có; ghi audit từng cấu kiện |
| `DELETE /projects/{p}/construction-batches/{id}/components/{component_id}?reason=` | Bỏ cấu kiện khỏi đợt; ghi audit |
| `POST /projects/{p}/progress/batches/{id}/undo` | Hoàn tác đợt trong cùng ngày bởi người tạo hoặc `project_manager`: `{reason}`; đánh dấu toàn bộ sự kiện `voided_at/by/reason`, ghi audit |
| `POST /projects/{p}/progress/events/{id}/correct` | Sửa trạng thái một sự kiện kèm lý do bắt buộc `{status, reason}`: void sự kiện cũ + tạo sự kiện mới; audit cả hai |
| `GET /projects/{p}/components/{id}/progress-events` | Lịch sử tiến độ còn hiệu lực (bỏ sự kiện đã void); mỗi sự kiện có `batch_id` |
| `GET /projects/{p}/components?batch_id=` | Lọc danh mục theo đợt thi công; `progress`, `progress/summary`, `drawing-map`, `overview/latest-day`, `overview/segments` nhận cùng `batch_id` |
| `GET /projects/{p}/drawing-map` | Mặt bằng theo project/zone/segment. Marker trả `design_group`, `current_work`/`current_work_definition_id` (bước mới nhất đang IN_PROGRESS), `location_review`; phản hồi có `review_count` (mã chưa đặt được) và `position_review_count` (tọa độ đang chờ duyệt). |
| `GET /projects/{p}/drawing-map/{sheet_id}/image` | Trả ảnh riêng cho thành viên dự án. |
| `GET /projects/{p}/progress/summary` | Tổng hợp project-scoped trên cấu kiện đã duyệt: tổng/đã duyệt/chờ duyệt, số có phạm vi phát sinh, 4 trạng thái thi công + tỷ lệ, liên kết/xác nhận nghiệm thu + tỷ lệ; hai tỷ lệ độc lập |
| `GET /projects/{p}/overview/latest-day` | Ngày gần nhất có sự kiện tiến độ hoặc báo cáo ngày: trả `{date, works:[{stage_name, zone, segment, component_type, status, count, codes[]}], manpower_total|null, photo_count, daily_report_exists, acceptance_today[]}`; chỉ đọc bản ghi thật, nghiệm thu không suy ra từ tiến độ, `null`/rỗng khi chưa có dữ liệu |
| `GET /projects/{p}/overview/segments` | Tiến độ theo zone + segment: số cấu kiện và đã xác minh, đếm thi công hoàn thành/đang thi công/chưa bắt đầu và nghiệm thu đã xác nhận; hai tỷ lệ độc lập trên cùng mẫu số đã xác minh |

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
| `GET /projects/{p}/documents` | Liệt kê hồ sơ nguồn đã có, chỉ đọc (không còn upload/ingest) |
| `GET /projects/{p}/documents/{id}/pages/{n}` | Metadata trang và URL ảnh render, yêu cầu quyền; không trả text OCR |
| `GET /projects/{p}/documents/{id}/versions` | Danh sách version, is_current/is_effective, change_note |
| `POST /projects/{p}/documents/{id}/effective` | Người quản lý hồ sơ xác nhận revision hiệu lực; lưu effective_at/by |
| `POST /projects/{p}/ai/chat` | Trả `{answer,citations[],confidence}`; chỉ từ dữ kiện AI trích xuất và database cấu kiện; thiếu citation/nguồn dùng câu từ chối chuẩn; `scope=effective\|history` |
| `POST /projects/{p}/ai/progress-parse` | Chỉ đọc: `{text, default_date?, batch_id?}` -> ngày thi công, dòng công tác, mã cấu kiện, công đoạn ứng viên, câu hỏi cần xác nhận và `batch_id` echo; thành viên đợt thi công không bị hỏi ngoài phạm vi; không ghi DB |
| `GET /projects/{p}/ai/question-suggestions` | Gợi ý 1-5 câu hỏi từ cấu kiện/công đoạn/tiến độ thật của công trình |
| `POST/GET /projects/{p}/ai/conversations` | Tạo mới/liệt kê; tìm kiếm `q` |
| `PATCH/DELETE /projects/{p}/ai/conversations/{id}` | Đổi tên/xóa hội thoại |
| `POST/GET /projects/{p}/documents/{id}/extractions` | Lưu/liệt kê dữ liệu AI trích xuất theo trang (đề xuất) |
| `GET/PATCH /projects/{p}/page-extractions/{id}` | Đọc hoặc xác nhận/từ chối một extraction; không ghi đè bản đã xác nhận |
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

### `POST /projects/{p}/ai/progress-parse` — ví dụ đầy đủ (tin nhắn 22/11)

Request: `{"text":"Cọc đục ngày 22/11\nI49, 51,55,57,58,60,63,64,67,\nH65,62,53,50\nG50,65,65\nF54,55,57,64,67,69\nA155\nB153,155\nE153,155\nDầm f66-67, a-b153,b-d153","default_date":"2026-01-01","batch_id":null}`

Response (read-only; IDs lấy từ dữ liệu seed của test golden):

```json
{
  "event_date": "2026-11-22",
  "date_source": "text",
  "batch_id": null,
  "lines": [
    {
      "work_text": "Cọc đục",
      "stage_candidates": [
        {
          "stage_definition_id": "9d7a73c3-a00d-4d70-ba69-987f20c96a34",
          "name": "Đục bê tông om vỡ dày trung bình t",
          "component_type": "pile"
        },
        {
          "stage_definition_id": "bc0eee6e-a6dd-418b-9d7e-adb00d399fa0",
          "name": "Đục bê tông om vỡ dày trung bình t",
          "component_type": "pile"
        },
        {
          "stage_definition_id": "61fed7f5-1708-4edd-a81d-59cd8d7263bb",
          "name": "Đục bê tông om vỡ dày trung bình t",
          "component_type": "pile"
        },
        {
          "stage_definition_id": "6d165f57-e56d-46d3-9140-e9b719e4cb02",
          "name": "Đục bê tông om vỡ dày trung bình t",
          "component_type": "pile"
        },
        {
          "stage_definition_id": "842cc86b-4e83-48ba-a1aa-57fdb77dfe5e",
          "name": "Đục bê tông om vỡ dày trung bình t",
          "component_type": "pile"
        },
        {
          "stage_definition_id": "3452b927-fc34-44e7-b6ef-8f15a354a91b",
          "name": "Đục bê tông om vỡ dày trung bình t",
          "component_type": "pile"
        },
        {
          "stage_definition_id": "69cd90e8-881b-4721-97c7-0ad855b8b120",
          "name": "Đục bê tông om vỡ dày trung bình t",
          "component_type": "pile"
        },
        {
          "stage_definition_id": "bab662d5-166b-4b40-b8cd-d23159364210",
          "name": "Đục bê tông om vỡ dày trung bình t",
          "component_type": "pile"
        },
        {
          "stage_definition_id": "9aa7938f-fd3a-471a-a264-863ded8c748f",
          "name": "Đục bê tông om vỡ dày trung bình t",
          "component_type": "pile"
        }
      ],
      "component_type": "pile",
      "items": [
        {
          "raw": "I49",
          "code": "I49",
          "component_id": "e7115246-a45c-423b-8e1f-85284371947b",
          "zone": "Cầu chính",
          "segment": 2,
          "status_guess": "COMPLETED",
          "stage_definition_id": "9d7a73c3-a00d-4d70-ba69-987f20c96a34",
          "stage_candidates": [],
          "earlier_events": [],
          "in_batch": false
        },
        {
          "raw": "51",
          "code": "I51",
          "component_id": "4b44a083-644c-4f07-b8e4-1a8eacbb3aea",
          "zone": "Cầu chính",
          "segment": 2,
          "status_guess": "COMPLETED",
          "stage_definition_id": "bc0eee6e-a6dd-418b-9d7e-adb00d399fa0",
          "stage_candidates": [],
          "earlier_events": [],
          "in_batch": false
        },
        {
          "raw": "55",
          "code": "I55",
          "component_id": "c3e55b75-7ebc-4bb0-93b6-221e5e61530a",
          "zone": "Cầu chính",
          "segment": 2,
          "status_guess": "COMPLETED",
          "stage_definition_id": "61fed7f5-1708-4edd-a81d-59cd8d7263bb",
          "stage_candidates": [],
          "earlier_events": [],
          "in_batch": false
        },
        {
          "raw": "57",
          "code": "I57",
          "component_id": "27d5ef58-ebe1-4417-b7d6-de1ff4568221",
          "zone": "Cầu chính",
          "segment": 2,
          "status_guess": "COMPLETED",
          "stage_definition_id": "6d165f57-e56d-46d3-9140-e9b719e4cb02",
          "stage_candidates": [],
          "earlier_events": [],
          "in_batch": false
        },
        {
          "raw": "58",
          "code": "I58",
          "component_id": "c88955e8-ccce-45e8-b378-2cf754db9d54",
          "zone": "Cầu chính",
          "segment": 2,
          "status_guess": "COMPLETED",
          "stage_definition_id": "842cc86b-4e83-48ba-a1aa-57fdb77dfe5e",
          "stage_candidates": [],
          "earlier_events": [],
          "in_batch": false
        },
        {
          "raw": "60",
          "code": "I60",
          "component_id": "27b71590-97db-454b-b8ae-a0423f46e55f",
          "zone": "Cầu chính",
          "segment": 2,
          "status_guess": "COMPLETED",
          "stage_definition_id": "3452b927-fc34-44e7-b6ef-8f15a354a91b",
          "stage_candidates": [],
          "earlier_events": [],
          "in_batch": false
        },
        {
          "raw": "63",
          "code": "I63",
          "component_id": "fb8f055f-cd52-4a9f-a7cd-16040b0c2b42",
          "zone": "Cầu chính",
          "segment": 2,
          "status_guess": "COMPLETED",
          "stage_definition_id": "69cd90e8-881b-4721-97c7-0ad855b8b120",
          "stage_candidates": [],
          "earlier_events": [],
          "in_batch": false
        },
        {
          "raw": "64",
          "code": "I64",
          "component_id": "65837b47-8b5b-4ac1-a3bc-ed06bbf92005",
          "zone": "Cầu chính",
          "segment": 2,
          "status_guess": "COMPLETED",
          "stage_definition_id": "bab662d5-166b-4b40-b8cd-d23159364210",
          "stage_candidates": [],
          "earlier_events": [],
          "in_batch": false
        },
        {
          "raw": "67",
          "code": "I67",
          "component_id": "eea77142-0f35-4d23-a218-fbe2a520cf27",
          "zone": "Cầu chính",
          "segment": 2,
          "status_guess": "COMPLETED",
          "stage_definition_id": "9aa7938f-fd3a-471a-a264-863ded8c748f",
          "stage_candidates": [],
          "earlier_events": [],
          "in_batch": false
        }
      ]
    },
    {
      "work_text": "Cọc đục",
      "stage_candidates": [
        {
          "stage_definition_id": "a2c829d1-bc2b-494b-a03f-aaa398b80f6a",
          "name": "Đục bê tông om vỡ dày trung bình t",
          "component_type": "pile"
        },
        {
          "stage_definition_id": "ed90c003-f28b-4043-a0f0-517ce329d0fa",
          "name": "Đục bê tông om vỡ dày trung bình t",
          "component_type": "pile"
        },
        {
          "stage_definition_id": "f39bc757-a13f-41cf-b118-7b450ff5f35c",
          "name": "Đục bê tông om vỡ dày trung bình t",
          "component_type": "pile"
        },
        {
          "stage_definition_id": "96d1c213-294b-4d3b-a724-99198c4c4eec",
          "name": "Đục bê tông om vỡ dày trung bình t",
          "component_type": "pile"
        }
      ],
      "component_type": "pile",
      "items": [
        {
          "raw": "H65",
          "code": "H65",
          "component_id": "54947e31-c1fd-4297-9775-4ed64ad3375c",
          "zone": "Cầu chính",
          "segment": 2,
          "status_guess": "COMPLETED",
          "stage_definition_id": "a2c829d1-bc2b-494b-a03f-aaa398b80f6a",
          "stage_candidates": [],
          "earlier_events": [],
          "in_batch": false
        },
        {
          "raw": "62",
          "code": "H62",
          "component_id": "31653b0d-6c9e-42f2-a2ef-626a51cbb6fb",
          "zone": "Cầu chính",
          "segment": 2,
          "status_guess": "COMPLETED",
          "stage_definition_id": "ed90c003-f28b-4043-a0f0-517ce329d0fa",
          "stage_candidates": [],
          "earlier_events": [],
          "in_batch": false
        },
        {
          "raw": "53",
          "code": "H53",
          "component_id": "734a712e-cc1b-48bf-a6fc-2181763db4cc",
          "zone": "Cầu chính",
          "segment": 2,
          "status_guess": "COMPLETED",
          "stage_definition_id": "f39bc757-a13f-41cf-b118-7b450ff5f35c",
          "stage_candidates": [],
          "earlier_events": [],
          "in_batch": false
        },
        {
          "raw": "50",
          "code": "H50",
          "component_id": "be851920-46a4-477a-b4ea-7a1d957046ca",
          "zone": "Cầu chính",
          "segment": 2,
          "status_guess": "COMPLETED",
          "stage_definition_id": "96d1c213-294b-4d3b-a724-99198c4c4eec",
          "stage_candidates": [],
          "earlier_events": [],
          "in_batch": false
        }
      ]
    },
    {
      "work_text": "Cọc đục",
      "stage_candidates": [
        {
          "stage_definition_id": "5cf6fba0-c7eb-4e79-a65a-bfc10e2d5e60",
          "name": "Đục bê tông om vỡ dày trung bình t",
          "component_type": "pile"
        },
        {
          "stage_definition_id": "65eb7add-9c36-4dd7-9da1-15831a91135a",
          "name": "Đục bê tông om vỡ dày trung bình t",
          "component_type": "pile"
        }
      ],
      "component_type": "pile",
      "items": [
        {
          "raw": "G50",
          "code": "G50",
          "component_id": "a18b8e53-7096-4a9f-aadb-0a38fa00b127",
          "zone": "Cầu chính",
          "segment": 2,
          "status_guess": "COMPLETED",
          "stage_definition_id": "5cf6fba0-c7eb-4e79-a65a-bfc10e2d5e60",
          "stage_candidates": [],
          "earlier_events": [],
          "in_batch": false
        },
        {
          "raw": "65",
          "code": "G65",
          "component_id": "7d70666e-0e34-4a5c-a1a3-59aacc63eabe",
          "zone": "Cầu chính",
          "segment": 2,
          "status_guess": "COMPLETED",
          "stage_definition_id": "65eb7add-9c36-4dd7-9da1-15831a91135a",
          "stage_candidates": [],
          "earlier_events": [],
          "in_batch": false
        },
        {
          "raw": "65",
          "code": "G65",
          "component_id": "7d70666e-0e34-4a5c-a1a3-59aacc63eabe",
          "zone": "Cầu chính",
          "segment": 2,
          "status_guess": "COMPLETED",
          "stage_definition_id": "65eb7add-9c36-4dd7-9da1-15831a91135a",
          "stage_candidates": [],
          "earlier_events": [],
          "in_batch": false
        }
      ]
    },
    {
      "work_text": "Cọc đục",
      "stage_candidates": [
        {
          "stage_definition_id": "954d4d59-4924-40e8-b0c6-ddfd381b5d11",
          "name": "Đục bê tông om vỡ dày trung bình t",
          "component_type": "pile"
        },
        {
          "stage_definition_id": "a89a7319-07b1-4c07-8415-4f1c69552466",
          "name": "Đục bê tông om vỡ dày trung bình t",
          "component_type": "pile"
        },
        {
          "stage_definition_id": "d35f5f57-7993-4624-a6f3-d6b86770680f",
          "name": "Đục bê tông om vỡ dày trung bình t",
          "component_type": "pile"
        },
        {
          "stage_definition_id": "a31d4945-02e1-4dcc-9d37-2c1c840acb24",
          "name": "Đục bê tông om vỡ dày trung bình t",
          "component_type": "pile"
        },
        {
          "stage_definition_id": "f51e60d8-a6b2-4bd9-ac32-ad1dc057cb13",
          "name": "Đục bê tông om vỡ dày trung bình t",
          "component_type": "pile"
        },
        {
          "stage_definition_id": "e0919ca1-0f62-4c78-a8ea-b78463cb2760",
          "name": "Đục bê tông om vỡ dày trung bình t",
          "component_type": "pile"
        }
      ],
      "component_type": "pile",
      "items": [
        {
          "raw": "F54",
          "code": "F54",
          "component_id": "fdc86775-410c-4b80-96e4-9042a4f58efc",
          "zone": "Cầu chính",
          "segment": 2,
          "status_guess": "COMPLETED",
          "stage_definition_id": "954d4d59-4924-40e8-b0c6-ddfd381b5d11",
          "stage_candidates": [],
          "earlier_events": [],
          "in_batch": false
        },
        {
          "raw": "55",
          "code": "F55",
          "component_id": "2cae26f4-0cab-4269-9652-207b20bb6215",
          "zone": "Cầu chính",
          "segment": 2,
          "status_guess": "COMPLETED",
          "stage_definition_id": "a89a7319-07b1-4c07-8415-4f1c69552466",
          "stage_candidates": [],
          "earlier_events": [],
          "in_batch": false
        },
        {
          "raw": "57",
          "code": "F57",
          "component_id": "c8a0a3a2-1fec-4067-9012-31bf337b2def",
          "zone": "Cầu chính",
          "segment": 2,
          "status_guess": "COMPLETED",
          "stage_definition_id": "d35f5f57-7993-4624-a6f3-d6b86770680f",
          "stage_candidates": [],
          "earlier_events": [],
          "in_batch": false
        },
        {
          "raw": "64",
          "code": "F64",
          "component_id": "ee4a5a82-1298-474b-87c6-46d40d605d75",
          "zone": "Cầu chính",
          "segment": 2,
          "status_guess": "COMPLETED",
          "stage_definition_id": "a31d4945-02e1-4dcc-9d37-2c1c840acb24",
          "stage_candidates": [],
          "earlier_events": [],
          "in_batch": false
        },
        {
          "raw": "67",
          "code": "F67",
          "component_id": "37437686-09fb-476e-a987-5023e2ffe938",
          "zone": "Cầu chính",
          "segment": 2,
          "status_guess": "COMPLETED",
          "stage_definition_id": "f51e60d8-a6b2-4bd9-ac32-ad1dc057cb13",
          "stage_candidates": [],
          "earlier_events": [],
          "in_batch": false
        },
        {
          "raw": "69",
          "code": "F69",
          "component_id": "4e3a951f-9ff1-40b4-8cca-e50c4468851b",
          "zone": "Cầu chính",
          "segment": 2,
          "status_guess": "COMPLETED",
          "stage_definition_id": "e0919ca1-0f62-4c78-a8ea-b78463cb2760",
          "stage_candidates": [],
          "earlier_events": [],
          "in_batch": false
        }
      ]
    },
    {
      "work_text": "Cọc đục",
      "stage_candidates": [
        {
          "stage_definition_id": "a52e41bb-876e-4d86-bbab-a8d51e805b12",
          "name": "Đục bê tông om vỡ dày trung bình t",
          "component_type": "pile"
        }
      ],
      "component_type": "pile",
      "items": [
        {
          "raw": "A155",
          "code": "A155",
          "component_id": "2b638d26-28a9-4ca7-9461-c9cb7931ad57",
          "zone": "Cầu chính",
          "segment": 2,
          "status_guess": "COMPLETED",
          "stage_definition_id": "a52e41bb-876e-4d86-bbab-a8d51e805b12",
          "stage_candidates": [],
          "earlier_events": [],
          "in_batch": false
        }
      ]
    },
    {
      "work_text": "Cọc đục",
      "stage_candidates": [
        {
          "stage_definition_id": "fa6ecfd1-4e7d-4279-af37-819ab3a04e28",
          "name": "Đục bê tông om vỡ dày trung bình t",
          "component_type": "pile"
        },
        {
          "stage_definition_id": "06e437fb-fdc6-44df-8b24-5cf49d636e98",
          "name": "Đục bê tông om vỡ dày trung bình t",
          "component_type": "pile"
        }
      ],
      "component_type": "pile",
      "items": [
        {
          "raw": "B153",
          "code": "B153",
          "component_id": "48be166c-d92e-4fcf-bfa7-33f18b44b7aa",
          "zone": "Cầu chính",
          "segment": 2,
          "status_guess": "COMPLETED",
          "stage_definition_id": "fa6ecfd1-4e7d-4279-af37-819ab3a04e28",
          "stage_candidates": [],
          "earlier_events": [],
          "in_batch": false
        },
        {
          "raw": "155",
          "code": "B155",
          "component_id": "5aa9575d-2657-42e4-82d7-fddd497fd3f2",
          "zone": "Cầu chính",
          "segment": 2,
          "status_guess": "COMPLETED",
          "stage_definition_id": "06e437fb-fdc6-44df-8b24-5cf49d636e98",
          "stage_candidates": [],
          "earlier_events": [],
          "in_batch": false
        }
      ]
    },
    {
      "work_text": "Cọc đục",
      "stage_candidates": [
        {
          "stage_definition_id": "3ee8f6eb-549b-4fe9-ab5f-232f2db13319",
          "name": "Đục bê tông om vỡ dày trung bình t",
          "component_type": "pile"
        },
        {
          "stage_definition_id": "6c777d9b-7719-4074-9b89-1a17091a42a1",
          "name": "Đục bê tông om vỡ dày trung bình t",
          "component_type": "pile"
        }
      ],
      "component_type": "pile",
      "items": [
        {
          "raw": "E153",
          "code": "E153",
          "component_id": "131443bc-4e0b-4b7c-8f9c-cab9a7dc362e",
          "zone": "Cầu chính",
          "segment": 2,
          "status_guess": "COMPLETED",
          "stage_definition_id": "3ee8f6eb-549b-4fe9-ab5f-232f2db13319",
          "stage_candidates": [],
          "earlier_events": [],
          "in_batch": false
        },
        {
          "raw": "155",
          "code": "E155",
          "component_id": "37af3a19-1381-44aa-8c94-a662d6fb5951",
          "zone": "Cầu chính",
          "segment": 2,
          "status_guess": "COMPLETED",
          "stage_definition_id": "6c777d9b-7719-4074-9b89-1a17091a42a1",
          "stage_candidates": [],
          "earlier_events": [],
          "in_batch": false
        }
      ]
    },
    {
      "work_text": "Dầm đục",
      "stage_candidates": [
        {
          "stage_definition_id": "f5592f84-81a6-4825-8739-4a1ae14685b7",
          "name": "Đục bê tông om vỡ dày trung bình 50 mm",
          "component_type": "beam"
        },
        {
          "stage_definition_id": "43aaa3c2-5271-4e26-9c01-7ce0ac97a018",
          "name": "Đục bê tông om vỡ dày trung bình 20 mm",
          "component_type": "beam"
        },
        {
          "stage_definition_id": "326c33fe-6c06-4104-a16b-88a4255934d3",
          "name": "Đục bê tông om vỡ dày trung bình 70 mm",
          "component_type": "beam"
        },
        {
          "stage_definition_id": "805c7752-3327-4a3c-af94-5af68153c2bd",
          "name": "Đục bê tông om vỡ dày trung bình 100 mm",
          "component_type": "beam"
        },
        {
          "stage_definition_id": "571ce5a7-4fc4-4f0b-a142-af462fdf0375",
          "name": "Đục bê tông om vỡ dày trung bình 70 mm",
          "component_type": "beam"
        },
        {
          "stage_definition_id": "83eec469-5b1e-41e0-94d9-59a293dc57a8",
          "name": "Đục bê tông om vỡ dày trung bình 20 mm",
          "component_type": "beam"
        },
        {
          "stage_definition_id": "442d3c81-2275-425f-81cb-8a345d587b02",
          "name": "Đục bê tông om vỡ dày trung bình 50 mm",
          "component_type": "beam"
        },
        {
          "stage_definition_id": "7b2187ad-276c-4315-b005-9f1e8d92ab52",
          "name": "Đục bê tông om vỡ dày trung bình 100 mm",
          "component_type": "beam"
        },
        {
          "stage_definition_id": "f5fc04e3-3244-4433-ad53-c51f098e6e02",
          "name": "Đục bê tông om vỡ dày trung bình 70 mm",
          "component_type": "beam"
        },
        {
          "stage_definition_id": "dffcfef2-cfe1-4b70-8001-3ec2052751e0",
          "name": "Đục bê tông om vỡ dày trung bình 20 mm",
          "component_type": "beam"
        },
        {
          "stage_definition_id": "b31b101f-f292-4bac-8201-460ffdc57189",
          "name": "Đục bê tông om vỡ dày trung bình 50 mm",
          "component_type": "beam"
        },
        {
          "stage_definition_id": "07504a99-60b4-45bc-b0fb-da001556202e",
          "name": "Đục bê tông om vỡ dày trung bình 100 mm",
          "component_type": "beam"
        }
      ],
      "component_type": "beam",
      "items": [
        {
          "raw": "f66-67",
          "code": "F-66-67",
          "component_id": "e02a20ab-3ba3-49ff-b7ec-da4ee5a50539",
          "zone": "Bunke",
          "segment": 1,
          "status_guess": "COMPLETED",
          "stage_definition_id": "f5592f84-81a6-4825-8739-4a1ae14685b7",
          "stage_candidates": [
            {
              "stage_definition_id": "f5592f84-81a6-4825-8739-4a1ae14685b7",
              "name": "Đục bê tông om vỡ dày trung bình 50 mm",
              "component_type": "beam"
            },
            {
              "stage_definition_id": "43aaa3c2-5271-4e26-9c01-7ce0ac97a018",
              "name": "Đục bê tông om vỡ dày trung bình 20 mm",
              "component_type": "beam"
            },
            {
              "stage_definition_id": "326c33fe-6c06-4104-a16b-88a4255934d3",
              "name": "Đục bê tông om vỡ dày trung bình 70 mm",
              "component_type": "beam"
            },
            {
              "stage_definition_id": "805c7752-3327-4a3c-af94-5af68153c2bd",
              "name": "Đục bê tông om vỡ dày trung bình 100 mm",
              "component_type": "beam"
            }
          ],
          "earlier_events": [
            {
              "event_id": "2bcf8c67-74a7-414d-a7e5-01c10490d2e0",
              "event_date": "2026-11-20",
              "status": "COMPLETED"
            }
          ],
          "in_batch": false
        },
        {
          "raw": "a-b153",
          "code": "A-B-153",
          "component_id": "5baba0fc-1627-4025-9e82-5f87c2fbad29",
          "zone": "Bunke",
          "segment": 1,
          "status_guess": "COMPLETED",
          "stage_definition_id": "571ce5a7-4fc4-4f0b-a142-af462fdf0375",
          "stage_candidates": [
            {
              "stage_definition_id": "571ce5a7-4fc4-4f0b-a142-af462fdf0375",
              "name": "Đục bê tông om vỡ dày trung bình 70 mm",
              "component_type": "beam"
            },
            {
              "stage_definition_id": "83eec469-5b1e-41e0-94d9-59a293dc57a8",
              "name": "Đục bê tông om vỡ dày trung bình 20 mm",
              "component_type": "beam"
            },
            {
              "stage_definition_id": "442d3c81-2275-425f-81cb-8a345d587b02",
              "name": "Đục bê tông om vỡ dày trung bình 50 mm",
              "component_type": "beam"
            },
            {
              "stage_definition_id": "7b2187ad-276c-4315-b005-9f1e8d92ab52",
              "name": "Đục bê tông om vỡ dày trung bình 100 mm",
              "component_type": "beam"
            }
          ],
          "earlier_events": [],
          "in_batch": false
        },
        {
          "raw": "b-d153",
          "code": "B-D-153",
          "component_id": "f0dfb613-881e-4cec-b8a4-e87671517e2f",
          "zone": "Bunke",
          "segment": 1,
          "status_guess": "COMPLETED",
          "stage_definition_id": "f5fc04e3-3244-4433-ad53-c51f098e6e02",
          "stage_candidates": [
            {
              "stage_definition_id": "f5fc04e3-3244-4433-ad53-c51f098e6e02",
              "name": "Đục bê tông om vỡ dày trung bình 70 mm",
              "component_type": "beam"
            },
            {
              "stage_definition_id": "dffcfef2-cfe1-4b70-8001-3ec2052751e0",
              "name": "Đục bê tông om vỡ dày trung bình 20 mm",
              "component_type": "beam"
            },
            {
              "stage_definition_id": "b31b101f-f292-4bac-8201-460ffdc57189",
              "name": "Đục bê tông om vỡ dày trung bình 50 mm",
              "component_type": "beam"
            },
            {
              "stage_definition_id": "07504a99-60b4-45bc-b0fb-da001556202e",
              "name": "Đục bê tông om vỡ dày trung bình 100 mm",
              "component_type": "beam"
            }
          ],
          "earlier_events": [],
          "in_batch": false
        }
      ]
    }
  ],
  "questions": [
    {
      "id": "duplicate:G65",
      "kind": "duplicate_code",
      "message_vi": "Mã G65 xuất hiện 2 lần trong tin nhắn. Bạn muốn xử lý thế nào?",
      "options": [
        {
          "label_vi": "Bỏ trùng",
          "value": "dedupe"
        },
        {
          "label_vi": "Mã khác",
          "value": "replace_code"
        }
      ],
      "codes": [
        "G65"
      ],
      "apply": {
        "action": "dedupe",
        "codes": [
          "G65"
        ]
      }
    },
    {
      "id": "stage:e02a20ab-3ba3-49ff-b7ec-da4ee5a50539",
      "kind": "multiple_stage",
      "message_vi": "Cấu kiện F-66-67 có 4 công đoạn riêng khớp 'Dầm đục'. Chọn công đoạn đúng:",
      "options": [
        {
          "label_vi": "Đục bê tông om vỡ dày trung bình 50 mm",
          "value": "f5592f84-81a6-4825-8739-4a1ae14685b7"
        },
        {
          "label_vi": "Đục bê tông om vỡ dày trung bình 20 mm",
          "value": "43aaa3c2-5271-4e26-9c01-7ce0ac97a018"
        },
        {
          "label_vi": "Đục bê tông om vỡ dày trung bình 70 mm",
          "value": "326c33fe-6c06-4104-a16b-88a4255934d3"
        },
        {
          "label_vi": "Đục bê tông om vỡ dày trung bình 100 mm",
          "value": "805c7752-3327-4a3c-af94-5af68153c2bd"
        }
      ],
      "codes": [
        "F-66-67"
      ],
      "apply": {
        "action": "set_stage",
        "stage_definition_id": "f5592f84-81a6-4825-8739-4a1ae14685b7",
        "codes": [
          "F-66-67"
        ]
      }
    },
    {
      "id": "completed:e02a20ab-3ba3-49ff-b7ec-da4ee5a50539:2bcf8c67-74a7-414d-a7e5-01c10490d2e0",
      "kind": "completed_earlier",
      "message_vi": "F-66-67 đã có COMPLETED ngày 20/11/2026, trước ngày 22/11/2026 cho công đoạn 'Đục bê tông om vỡ dày trung bình 50 mm'. Bạn muốn ghi thế nào?",
      "options": [
        {
          "label_vi": "Ghi thêm hoàn thành",
          "value": "add_completed"
        },
        {
          "label_vi": "Ngày trước là đang làm, hôm nay xong",
          "value": "previous_was_in_progress"
        },
        {
          "label_vi": "Bỏ qua",
          "value": "skip"
        }
      ],
      "codes": [
        "F-66-67"
      ],
      "apply": {
        "action": "correct_earlier_to_in_progress",
        "event_ids": [
          "2bcf8c67-74a7-414d-a7e5-01c10490d2e0"
        ],
        "codes": [
          "F-66-67"
        ]
      }
    },
    {
      "id": "stage:5baba0fc-1627-4025-9e82-5f87c2fbad29",
      "kind": "multiple_stage",
      "message_vi": "Cấu kiện A-B-153 có 4 công đoạn riêng khớp 'Dầm đục'. Chọn công đoạn đúng:",
      "options": [
        {
          "label_vi": "Đục bê tông om vỡ dày trung bình 70 mm",
          "value": "571ce5a7-4fc4-4f0b-a142-af462fdf0375"
        },
        {
          "label_vi": "Đục bê tông om vỡ dày trung bình 20 mm",
          "value": "83eec469-5b1e-41e0-94d9-59a293dc57a8"
        },
        {
          "label_vi": "Đục bê tông om vỡ dày trung bình 50 mm",
          "value": "442d3c81-2275-425f-81cb-8a345d587b02"
        },
        {
          "label_vi": "Đục bê tông om vỡ dày trung bình 100 mm",
          "value": "7b2187ad-276c-4315-b005-9f1e8d92ab52"
        }
      ],
      "codes": [
        "A-B-153"
      ],
      "apply": {
        "action": "set_stage",
        "stage_definition_id": "571ce5a7-4fc4-4f0b-a142-af462fdf0375",
        "codes": [
          "A-B-153"
        ]
      }
    },
    {
      "id": "stage:f0dfb613-881e-4cec-b8a4-e87671517e2f",
      "kind": "multiple_stage",
      "message_vi": "Cấu kiện B-D-153 có 4 công đoạn riêng khớp 'Dầm đục'. Chọn công đoạn đúng:",
      "options": [
        {
          "label_vi": "Đục bê tông om vỡ dày trung bình 70 mm",
          "value": "f5fc04e3-3244-4433-ad53-c51f098e6e02"
        },
        {
          "label_vi": "Đục bê tông om vỡ dày trung bình 20 mm",
          "value": "dffcfef2-cfe1-4b70-8001-3ec2052751e0"
        },
        {
          "label_vi": "Đục bê tông om vỡ dày trung bình 50 mm",
          "value": "b31b101f-f292-4bac-8201-460ffdc57189"
        },
        {
          "label_vi": "Đục bê tông om vỡ dày trung bình 100 mm",
          "value": "07504a99-60b4-45bc-b0fb-da001556202e"
        }
      ],
      "codes": [
        "B-D-153"
      ],
      "apply": {
        "action": "set_stage",
        "stage_definition_id": "f5fc04e3-3244-4433-ad53-c51f098e6e02",
        "codes": [
          "B-D-153"
        ]
      }
    },
    {
      "id": "outside:Bunke:1:beam",
      "kind": "outside_scope",
      "message_vi": "3 dầm (F-66-67, A-B-153, B-D-153) thuộc Bunke - phân đoạn 1, ngoài phạm vi Cầu chính - PD2. Thi công cùng đợt?",
      "options": [
        {
          "label_vi": "Thi công cùng đợt",
          "value": "include"
        },
        {
          "label_vi": "Bỏ qua",
          "value": "skip"
        }
      ],
      "codes": [
        "F-66-67",
        "A-B-153",
        "B-D-153"
      ],
      "apply": {
        "action": "skip_codes",
        "codes": [
          "F-66-67",
          "A-B-153",
          "B-D-153"
        ]
      }
    }
  ],
  "unknown_codes": [],
  "warnings": [
    "Trạng thái mặc định là COMPLETED cho công tác đã làm; sửa nếu thực tế khác.",
    "3 cấu kiện nằm ngoài phân đoạn chính; xác nhận trước khi ghi."
  ]
}
```

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
