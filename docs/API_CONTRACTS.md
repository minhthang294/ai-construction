# API contracts v1

Cập nhật: 24/11/2026. Prefix `/api/v1`. JSON UTF-8. Auth Bearer; mọi request project-scoped kiểm membership. Ngày `YYYY-MM-DD`, timestamp ISO-8601 có múi giờ. Lỗi `{detail, code}`; `403` thiếu quyền, `404` resource không thuộc project, `409` xung đột trạng thái, `422` dữ liệu sai.

Đã bỏ 23-24/11/2026: upload/ingest tài liệu, OCR/Tesseract, embedding/sqlite-vec ingest, tìm kiếm tài liệu, cross-reference, checklist tài liệu độc lập, AI report-draft, AI gợi ý caption ảnh. Checklist 7 mục trong BBNT vẫn còn; caption ảnh do người dùng nhập/xác nhận.

## Auth, dự án, danh mục

| Route | Ý nghĩa |
| --- | --- |
| `POST /auth/login` | Cấp bearer token 12 giờ |
| `POST /auth/logout` | Thu hồi token hiện tại |
| `POST /auth/change-password` | Đổi mật khẩu người dùng hiện tại |
| `POST /users` | Tạo người dùng (admin) |
| `POST/GET /projects` | Tạo/liệt kê công trình được phép; `can_delete` cho admin/quản lý |
| `PATCH/DELETE /projects/{p}` | Sửa/xóa mềm; audit; project đã xóa trả `404` |
| `POST /projects/{p}/members` | Thêm thành viên và role |
| `POST/GET /projects/{p}/work-items` | Danh mục công việc |
| `PATCH /projects/{p}/work-items/{id}` | Sửa công việc; ghi audit |
| `POST /projects/{p}/work-items/import-preview` | Preview import Excel công việc |
| `POST /projects/{p}/work-items/import` | Ghi import đã duyệt |
| `POST/GET /projects/{p}/organizations` | Đơn vị theo công trình |
| `POST/GET /projects/{p}/personnel` | Nhân sự; chỉ tham chiếu đơn vị cùng công trình |

## Cấu kiện, tiến độ, đợt thi công, bản đồ

| Route | Ý nghĩa |
| --- | --- |
| `GET /projects/{p}/segments?zone=` | Phân đoạn đã nhập |
| `GET /projects/{p}/design-groups` | Nhóm thiết kế (`id, name, drawing, group_type`) |
| `GET /projects/{p}/components?q=&...` | Danh mục; `q` khớp mã/alias; lọc `zone`, `segment_id`, `type`, `group_id`, `scope`, `batch_id` |
| `GET /projects/{p}/components/{id}` | Chi tiết, phạm vi, DM liên quan, `design_parameters[]`, tên bước render `t = … cm` |
| `POST /projects/{p}/components` | Tạo thủ công; `201`; segment cùng project |
| `POST /projects/{p}/components/import-preview` | Upload seed XLSX; preview; không ghi DB |
| `POST /projects/{p}/components/import-commit` | Commit đã duyệt; idempotency; audit |
| `GET/POST /projects/{p}/stage-definitions?type=` | Định nghĩa bước theo project + `pile/beam` |
| `POST /projects/{p}/components/{id}/repair-scopes` | Đề xuất scope `NEEDS_REVIEW` |
| `POST /projects/{p}/components/{id}/repair-scopes/{scope_id}/review` | Duyệt/từ chối scope |
| `POST /projects/{p}/components/{id}/stages` | Gắn bước vào cấu kiện + scope |
| `GET/POST /projects/{p}/components/{id}/progress-events` | Lịch sử/ghi tiến độ append-only |
| `GET /projects/{p}/progress` | Tổng hợp tiến độ; lọc `q`, `zone`, `segment_id`, `type`, `group_id`, `scope`, `origin`, `stage_definition_id`, `construction_status`, `acceptance_status`, `batch_id` |
| `POST /projects/{p}/progress/design-quantities` | Tra khối lượng thiết kế; tối đa 500 component id |
| `POST /projects/{p}/progress/bulk-preview` | Preview ghi hàng loạt; trả matched/ambiguous/missing/warnings/`can_commit` |
| `POST /projects/{p}/progress/bulk` | Commit hàng loạt; `reviewed: true`, `idempotency_key`; ghi event + audit |
| `POST /projects/{p}/progress/daily-preview` | Preview nhiều công tác cùng ngày |
| `POST /projects/{p}/progress/daily` | Ghi nhiều công tác cùng ngày trong một transaction |
| `POST /projects/{p}/progress/batches/{id}/undo` | Void cả đợt trong ngày; `{reason}`; audit |
| `POST /projects/{p}/progress/events/{id}/correct` | Void sự kiện cũ + tạo sự kiện mới; `{status, reason}` |
| `GET /projects/{p}/progress/summary` | Tổng hợp project-scoped trên cấu kiện đã duyệt |
| `GET /projects/{p}/reconciliation/issues` | Đối soát read-only; `issues[]` + `counts` |
| `GET/POST /projects/{p}/construction-batches` | Danh sách/tạo đợt thi công; `component_count`, `primary_zone` |
| `GET/PATCH /projects/{p}/construction-batches/{id}` | Chi tiết/sửa đợt; audit |
| `POST /projects/{p}/construction-batches/{id}/components/preview` | Preview mã; matched/ambiguous/missing/already_in_batch |
| `POST /projects/{p}/construction-batches/{id}/components` | Thêm cấu kiện đã chọn; audit từng cấu kiện |
| `DELETE /projects/{p}/construction-batches/{id}/components/{component_id}?reason=` | Bỏ cấu kiện khỏi đợt |
| `GET /projects/{p}/drawing-map` | Gộp mọi `data/storage/dap-maps/<key>/manifest.json` (bỏ `expansion`); lọc `batch_id`, `zone`, `segment`; marker trả `design_group`, `current_work`, `origin`, `position_*`, `review_count` |
| `PUT /projects/{p}/components/{id}/map-position` | Lưu vị trí nháp; tọa độ 0..1; cọc 1 điểm, dầm ≥2 điểm |
| `POST /projects/{p}/components/{id}/map-position/review?sheet_id=` | Duyệt vị trí; `project_manager` |
| `GET /projects/{p}/drawing-map/{sheet_id}/image` | Ảnh sheet private; chặn path traversal |
| `GET /projects/{p}/overview/latest-day` | Ngày gần nhất có tiến độ/báo cáo; works, manpower, photo_count, acceptance_today |
| `GET /projects/{p}/overview/in-progress` | Cấu kiện có event mới nhất còn `IN_PROGRESS`/`BLOCKED` |
| `GET /projects/{p}/overview/segments` | Tiến độ + nghiệm thu theo zone/segment |

Mỗi giá trị trả về từ `progress/design-quantities` gồm `quantity` (số hoặc `null`), `unit`, `scope` (`COMPONENT`, `SHARED` hoặc `SUBGROUP`), `scope_label`, `drawing`, `page` và `note`. Khối lượng dùng chung cho cụm hoặc phân nhóm được tra theo phạm vi đã ghi. API yêu cầu quyền thành viên công trình và chỉ đọc số liệu thiết kế.

## Báo cáo ngày, ảnh, nhật ký

| Route | Ý nghĩa |
| --- | --- |
| `GET/PUT /projects/{p}/daily-reports/{date}` | Bản nháp báo cáo ngày; manpower/work_logs/next_day_plans/notes; upsert idempotent |
| `GET/POST /projects/{p}/manpower-presets` | Preset nhóm nhân lực |
| `PUT/DELETE /projects/{p}/manpower-presets/{id}` | Sửa/xóa preset |
| `POST/GET /projects/{p}/photos` | Upload/liệt kê ảnh; metadata location/component/stage; `component_ids`, `work_item_ids`; lọc `date`, `location`, `component`, `component_id`, `stage`, `work_item_id`, `report_id`, `category` |
| `GET /projects/{p}/photos/{id}/original` | Stream ảnh sau kiểm quyền |
| `PATCH /projects/{p}/photos/{id}` | Sửa metadata/caption/liên kết |
| `DELETE /projects/{p}/photos/{id}` | Xóa ảnh; `409` nếu đang là bằng chứng |
| `POST/GET /projects/{p}/daily-reports/{date}/exports` | Export `zalo/pdf/docx/zip` |
| `GET /projects/{p}/generated-documents/{doc_id}/download` | Tải file đã sinh |
| `GET /projects/{p}/journals/{date}/preview` | Preview nhật ký; `preview_sha256`, `snapshot_eligible` |
| `POST/GET /projects/{p}/journals/{date}/snapshots` | Tạo/liệt kê snapshot bất biến |
| `POST/GET /projects/{p}/journals/{date}/exports` | Export từ snapshot đã duyệt |

## Engineering AI

| Route | Ý nghĩa |
| --- | --- |
| `GET /projects/{p}/documents` | Danh sách hồ sơ nguồn; chỉ đọc, không upload/ingest |
| `GET /projects/{p}/documents/{id}` | Chi tiết hồ sơ + pages |
| `POST /projects/{p}/documents/{id}/effective` | Xác nhận revision hiệu lực; lưu effective_at/by |
| `GET /projects/{p}/documents/{id}/versions` | Danh sách version, is_current/is_effective |
| `GET /projects/{p}/documents/{id}/original` | Tải file gốc private |
| `GET /projects/{p}/documents/{id}/pages/{n}` | Metadata trang, `text`/`ocr_text` legacy nếu có và URL render; không có pipeline OCR mới |
| `GET /projects/{p}/documents/{id}/pages/{n}/render` | Ảnh render trang |
| `POST /projects/{p}/documents/{id}/pages/{n}/extractions` | Lưu dữ liệu AI trích xuất theo trang |
| `GET /projects/{p}/documents/{id}/extractions` | Liệt kê extraction; lọc `page`, `status` |
| `GET/PATCH /projects/{p}/page-extractions/{id}` | Đọc/duyệt hoặc từ chối extraction |
| `POST /projects/{p}/ai/chat` | Chat + citation; `scope=effective/history`; thiếu nguồn trả câu từ chối |
| `POST /projects/{p}/ai/progress-parse` | Parser Zalo read-only; không gọi LLM, không ghi DB |
| `GET /projects/{p}/ai/question-suggestions` | Gợi ý 1-5 câu hỏi từ dữ liệu thật |
| `GET/POST /projects/{p}/ai/conversations` | Liệt kê/tạo; `q` chỉ lọc tiêu đề |
| `GET/PATCH/DELETE /projects/{p}/ai/conversations/{id}` | Đọc/đổi tên/xóa hội thoại |

## Acceptance

| Route | Ý nghĩa |
| --- | --- |
| `GET /projects/{p}/acceptance-numbering` | Cấu hình numbering PYC/BBNT |
| `PUT /projects/{p}/acceptance-numbering/{kind}` | Sửa numbering `pyc` hoặc `bbnt` |
| `GET/POST /projects/{p}/acceptance-participants` | Danh mục người tham gia |
| `GET/PATCH/DELETE /projects/{p}/acceptance-participants/{id}` | Chi tiết/sửa/xóa |
| `POST/GET /projects/{p}/acceptance-requests` | Tạo/liệt kê PYC |
| `GET /projects/{p}/acceptance/pending` | Hàng chờ nghiệm thu |
| `POST /projects/{p}/acceptance/requests/from-components` | Tạo PYC nháp từ cấu kiện |
| `GET/PATCH/DELETE /projects/{p}/acceptance-requests/{id}` | Chi tiết/sửa/xóa PYC |
| `GET /projects/{p}/acceptance-requests/{id}/daily-report` | Báo cáo ngày liên kết |
| `GET/PUT /projects/{p}/acceptance-requests/{id}/component-links` | Liên kết cấu kiện |
| `POST/GET /projects/{p}/acceptance-requests/{id}/exports` | Export PYC |
| `GET /projects/{p}/acceptance-requests/{id}/preview` | Preview template PYC |
| `GET /projects/{p}/acceptance-requests/{id}/preview-image` | Ảnh preview PYC |
| `POST/GET /projects/{p}/acceptance-records` | Tạo/liệt kê BBNT |
| `GET/PATCH /projects/{p}/acceptance-records/{id}` | Chi tiết/sửa BBNT |
| `GET/PUT /projects/{p}/acceptance-records/{id}/component-links` | Liên kết cấu kiện |
| `GET /projects/{p}/acceptance-records/{id}/preview` | Preview BBNT |
| `POST /projects/{p}/acceptance-records/{id}/revisions` | Tạo revision BBNT mới |
| `POST /projects/{p}/acceptance-records/{id}/confirm` | Xác nhận BBNT; audit |
| `POST/GET /projects/{p}/acceptance-records/{id}/exports` | Export BBNT |
| `GET /projects/{p}/acceptance-exports` | Lịch sử export |
| `GET /projects/{p}/acceptance-exports/{id}/download` | Tải export |
| `GET /projects/{p}/work-items/{id}/acceptance-history` | Lịch sử PYC/BBNT theo work item |

Import lịch sử PYC/BBNT từ workbook là script `scripts/import_acceptance_workbook.py` (preview mặc định, `--commit`, idempotent, không sửa workbook), không phải route HTTP. Script chỉ xác nhận khi workbook có số/ngày hợp lệ và ghi audit.

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

`DailyReport.status`: `draft|reviewed`; `AcceptanceChecklist.state`: `yes|no|unconfirmed`; `AcceptanceRecord.result`: `approved|conditional|rejected|null`. `null` là chưa có quyết định. Ảnh chỉ dùng caption/category đã được người dùng xác nhận; không có AI gợi ý caption. Citation gồm `document_id`, `document_name`, `version`, `page_number`, `drawing_number?`, `revision?`, `quote`, `url`; `ocr_confidence?` chỉ còn là trường legacy từ dữ liệu cũ, không có pipeline OCR hiện tại.

Import cấu kiện hiện chỉ hỗ trợ cấu trúc workbook seed. `reviewed` là xác nhận của người gọi API; commit chỉ chấp nhận dữ liệu khớp workbook gửi lại. Giao diện cho phép xem trước, lọc và duyệt, nhưng chưa sửa từng candidate: cần sửa workbook và xem lại. Import chỉ bổ sung và không xóa cấu kiện thiếu trong file. Không tạo tiến độ hay nghiệm thu từ ngày có trong seed.

Tạo cấu kiện thủ công ghi `verification=NEEDS_REVIEW`, `record_origin=MANUAL_ENTRY`, phạm vi `NEEDS_REVIEW` và để trống SHA nguồn, dòng nguồn, người/ngày duyệt cùng `approval_reference` thay vì suy diễn. `raw_code`, `canonical_code` và alias dùng chung một không gian định danh duy nhất theo project + segment + type; trùng trả `409`. Import giữ idempotency và vẫn yêu cầu đối chiếu thủ công khi gặp cấu kiện thủ công cùng mã.

Phạm vi sửa chữa: đề xuất luôn tạo bản ghi mới với `verification=NEEDS_REVIEW`; `DESIGN_SCOPE` và `ADDITIONAL_SCOPE` có dải `revision` riêng. Duyệt `VERIFIED` phải có `approval_reference` (bắt buộc với `ADDITIONAL_SCOPE`, tùy chọn với `DESIGN_SCOPE`); `REJECTED` không cần. Chỉ scope `NEEDS_REVIEW` được duyệt một lần, sau đó trả `409`; mọi lần duyệt ghi `reviewed_by`, `reviewed_at` và audit `repair_scope_reviewed`.

Bước thi công: `StageDefinition` thuộc project và đúng một loại cấu kiện; `ComponentStage` gắn định nghĩa với cấu kiện và đúng một `RepairScope` của cấu kiện đó. Cùng một định nghĩa bước có thể gắn lại cho phạm vi sửa chữa khác của cùng cấu kiện, nhưng không lặp trong cùng một phạm vi. Không có bộ bước mặc định cho mọi cọc/dầm; client chọn định nghĩa. Định nghĩa/bước trùng, sai project hoặc sai loại trả `409`/`404`; ghi audit khi tạo.

`ProgressEvent` là append-only: không có `PATCH`/`DELETE`, sửa sai bằng cách thêm event mới. Event bắt buộc `event_date` do người dùng nhập (không suy ra từ seed hay AI), `status` thuộc `IN_PROGRESS|COMPLETED|BLOCKED`; `quantity` không âm; `evidence_refs[]` tối đa 20, mỗi chuỗi 1–120 ký tự. Bằng chứng phải phân giải được trong cùng project: ảnh đã xác nhận (`<id>` hoặc `photo:<id>`), `document:<id>`, `page:<page_id>` hay `page:<document_id>:<page_number>`; sai project/không tồn tại trả `404`, ảnh chưa xác nhận hoặc ref sai định dạng trả `422`. Bảng `component_progress_events` dùng chung với luồng cập nhật hàng loạt của module site (`component_progress_batches` giữ idempotency cho bulk); trạng thái hiện tại của bước là status của event có `created_at` lớn nhất, timeline hiển thị theo `event_date`. Tiến độ thi công chỉ đọc/ghi bảng tiến độ, không tạo, sửa hay suy ra trạng thái nghiệm thu và không ghi vào module acceptance. Quyền ghi đề xuất/bước/tiến độ là `project_manager|engineer`; duyệt phạm vi là `project_manager`; đọc là member.

`progress/summary` chỉ tính cấu kiện `verification=VERIFIED`; trạng thái thi công của cấu kiện là status của event có `created_at` lớn nhất (`NOT_STARTED` nếu chưa có). `acceptance.linked` đếm cấu kiện có link PYC/BBNT; `acceptance.confirmed` chỉ đếm link tới BBNT `status=confirmed`. Hai tỷ lệ độc lập, cùng chia cho số cấu kiện đã duyệt; không suy ra nghiệm thu từ thi công. `reconciliation/issues` là read-only, project-scoped; loại issue gồm `ACCEPTANCE_WITHOUT_PROGRESS`, `WORK_WITHOUT_ACCEPTANCE`, `MISSING_SOURCE`, `UNVERIFIED_COMPONENT`, `DUPLICATE_OR_AMBIGUOUS_CODE`, `ACCEPTANCE_BEFORE_PROGRESS`; mỗi issue có cấu kiện, khu, phân đoạn, mô tả và mã tham chiếu liên quan.

Bulk progress: mỗi dòng preview trả `stage_options` (các bước cùng định nghĩa), `stage_ambiguous` và `stage_id` đã chọn. Nếu một cấu kiện có hơn một bước cùng `stage_definition_id`, client phải gửi `stage_selections` cho đúng cấu kiện; server không tự chọn bước đầu tiên. Preview và commit phải dùng cùng `stage_selections`; commit thiếu lựa chọn, lựa chọn không thuộc cấu kiện/định nghĩa hoặc cấu kiện đã đổi trả `409`. `evidence_refs` được kiểm project-scoped ở cả preview và commit bằng `app.core.evidence.validate_evidence_refs`; ref sai project/không tồn tại `404`, ảnh chưa xác nhận hoặc sai định dạng `422`.

Tổng hợp tiến độ của site trả `construction_status` (`NOT_STARTED|IN_PROGRESS|COMPLETED|BLOCKED`) và `acceptance_status` riêng. `acceptance_status` chỉ lấy từ liên kết tường minh `component_acceptance_links`: không có liên kết `NOT_LINKED`; có PYC/BBNT nhưng chưa xác nhận `PENDING`; BBNT đã xác nhận theo `result` thành `APPROVED|CONDITIONAL|REJECTED|CONFIRMED`. `acceptance_count` là số BBNT đã xác nhận. Không suy ra nghiệm thu từ tiến độ. Bulk progress bắt buộc `reviewed: true`, giữ nguyên đúng `component_ids[]` đã xem trước và một `stage_definition_id`; cấu kiện chưa gắn bước bị từ chối, không tự gắn bước. `component_progress_batches` chỉ lưu idempotency/result của bulk; event vẫn append-only trong `component_progress_events`. Nhật ký ngày: preview trả `blank_sections`, `warnings`, `preview_sha256`, `snapshot_eligible`, chứng cứ ảnh đã xác nhận và chỉ lấy BBNT `confirmed` đúng ngày xác nhận; không tạo sự kiện thi công/nghiệm thu giả. Snapshot yêu cầu `reviewed: true` + đúng `preview_sha256`; báo cáo ngày nháp chặn snapshot (`409`). Snapshot lưu JSON bất biến cùng bản sao ảnh chứng cứ đã xác nhận; tham chiếu ảnh chưa xác nhận/không phân giải bị bỏ và ghi cảnh báo, không tự liên kết. Export chỉ đọc snapshot đã duyệt, kiểm hash file/tham chiếu; PDF/DOCX nêu danh mục chứng cứ, ZIP kèm bytes; không đọc lại dữ liệu live và không tạo nghiệm thu.

Checklist BBNT `evidence_refs[]` chấp nhận ID ảnh cùng công trình (hoặc `photo:<id>`), `document:<id>`, `page:<page_id>` hay `page:<document_id>:<page_number>`. Ref không phân giải được hoặc trỏ sang công trình khác bị từ chối; trạng thái checklist chỉ do người dùng nhập. Không còn checklist tài liệu độc lập (bỏ 23-24/11/2026).
