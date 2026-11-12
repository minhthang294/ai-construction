# API contracts v1

Prefix `/api/v1`. JSON UTF-8. Auth Bearer; mọi request project-scoped kiểm membership. Ngày `YYYY-MM-DD`, timestamp ISO-8601 có múi giờ. Lỗi `{detail, code}`; `403` thiếu quyền, `404` resource không thuộc project, `409` xung đột trạng thái, `422` dữ liệu sai.

`POST /auth/login` cấp bearer token 12 giờ; `POST /auth/logout` thu hồi token hiện tại.

| Route | Ý nghĩa |
| --- | --- |
| `POST/GET /projects` | Tạo và liệt kê công trình được phép |
| `POST/GET /projects/{p}/work-items` | Danh mục công việc, import có preview trước khi lưu |
| `PATCH /projects/{p}/work-items/{id}` | Sửa tên/vị trí/cấu kiện/trạng thái công việc; ghi audit |
| `POST/GET /projects/{p}/organizations` và `/personnel` | Danh sách đơn vị và nhân sự theo công trình; nhân sự chỉ tham chiếu đơn vị cùng công trình |
| `PUT/GET /projects/{p}/daily-reports/{date}` | Bản nháp báo cáo, gồm `manpower[]`, `work_logs[]` (`work_item_id?`, `work_name?`, `location`, `component`, số lượng/trạng thái/ghi chú), `next_day_plans[]`, `notes`, `site_notes`; không còn giờ bắt đầu/kết thúc trên UI; upsert idempotent |
| `GET/POST /projects/{p}/manpower-presets` và `PUT/DELETE /projects/{p}/manpower-presets/{id}` | Preset nhóm nhân lực theo công trình, chỉ dùng khi người dùng chọn |
| `POST/GET /projects/{p}/photos` | Multipart upload nhiều ảnh; metadata location/component/stage và lọc `date`, `location`, `component`, `stage` |
| `GET /projects/{p}/photos/{id}/original` | Stream file sau kiểm quyền |
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
| `GET/PUT /projects/{p}/acceptance-numbering` | Cấu hình prefix/start/width/reset policy cho PYC/BBNT |
| `POST /projects/{p}/acceptance-requests/{id}/preview` | Preview dữ liệu điền template trước khi xuất |
| `POST/GET /projects/{p}/acceptance-records` | BBNT nháp và checklist |
| `POST /projects/{p}/acceptance-records/{id}/revisions` | Tạo revision BBNT mới, giữ bản cũ |
| `GET /projects/{p}/work-items/{id}/acceptance-history` | Lịch sử PYC/BBNT theo work item |
| `POST /projects/{p}/acceptance-records/{id}/confirm` | Người có quyền xác nhận, ghi audit |
| `POST /projects/{p}/acceptance-records/{id}/exports` | Excel sao chép template PYC/BBNT; PDF PYC chỉ giữ trang PYC, PDF BBNT chỉ giữ PYC + BBNT; tên tải PYC dạng `YC-<số phiếu>.pdf` |
| `GET/POST /projects/{p}/acceptance-participants` | Danh mục người tham gia theo vai trò; `PUT/DELETE .../{id}` |

`DailyReport.status`: `draft|reviewed`; `AcceptanceChecklist.state`: `yes|no|unconfirmed`; `AcceptanceRecord.result`: `approved|conditional|rejected|null`. `null` là chưa có quyết định. `PhotoEvidence` chỉ dùng ảnh với caption/category đã được người dùng xác nhận. Citation gồm `document_id`, `document_name`, `version`, `page_number`, `drawing_number?`, `revision?`, `quote`, `url`, `ocr_confidence?`.

Checklist `evidence_refs[]` chấp nhận ID ảnh cùng công trình (hoặc `photo:<id>`), `document:<id>`, `page:<page_id>` hay `page:<document_id>:<page_number>`. Ref không phân giải được hoặc trỏ sang công trình khác bị từ chối; trạng thái checklist chỉ do người dùng nhập.
