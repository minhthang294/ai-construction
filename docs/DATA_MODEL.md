# Data model chung

Các bảng nghiệp vụ dùng khóa UUID và phạm vi `project_id` khi áp dụng. Không phải mọi tham chiếu đã có ràng buộc FK trong SQLite; service/API kiểm tra liên kết cùng công trình trước khi ghi.

| Entity | Trường chính / quan hệ |
| --- | --- |
| Project | name, client, location, report_title nullable, status |
| Organization, Personnel | project_id, name, role, organization_id |
| WorkItem | project_id, code, name, location, component, status |
| DailyReport | project_id, report_date (unique cùng project), status draft/reviewed, notes, site_notes_json tùy chọn, generated snapshot |
| ManpowerEntry | report_id, group_name, person_name nullable, count nullable, organization_id nullable; `0` khác `null` |
| ManpowerPreset | project_id, group_name, person_name/count/organization_id tùy chọn; chỉ áp dụng khi người dùng chọn |
| DailyWorkLog | report_id, work_item_id nullable, work_name nullable (tên công việc duy nhất từ danh mục), location, component, quantity nullable, unit, start/end cũ (không còn nhập trên UI), status, notes |
| NextDayPlan | report_id, plan_date, work_item_id nullable, description, location, manpower, equipment, dependency |
| SitePhoto | project_id, report_id nullable, original_path, sha256, capture_time nullable, upload_time, GPS nullable, device nullable, category, location/component/stage nullable, suggested_caption, confirmed_caption |
| PhotoWorkItemLink | photo_id, work_item_id, unique pair |
| SourceDocument | project_id, type, original_name, original_path, sha256, version, is_current (mới nhất), is_effective (đang hiệu lực), change_note, effective_at/by, status |
| DocumentPage | document_id, page_number 1-based, rendered_path nullable, ocr_text, ocr_confidence nullable, drawing_number nullable, revision nullable, tables_json |
| DocumentChunk / DocumentEmbedding | page_id, section, text, offsets, vector metadata/model; sqlite-vec là vector index bền vững, JSON là nguồn chuẩn/fallback |
| AIConversation / AICitation | project_id, title, messages; citation page_id, version, quote, drawing_number/revision, page URL |
| AcceptanceRequest | project_id, work_item_id, daily_report_id nullable, number, revision, status draft/submitted, requested_at, profile ids người yêu cầu/giám sát/chủ đầu tư |
| AcceptanceRecord | request_id, number nullable, revision, supersedes_id, request_updated_at, status draft/confirmed, result nullable, confirmer_id nullable, confirmed_at nullable |
| AcceptanceParticipant / AcceptanceChecklist | record_id, person/role; item, state yes/no/unconfirmed, evidence refs |
| AcceptanceNumberSequence | project_id, kind pyc/bbnt, prefix, start/next, width, reset policy, period key; unique project+kind |
| AcceptanceParticipantProfile | project_id, full_name, organization, position, role, active |
| GeneratedDocument | project_id, kind, source_id, path, sha256, created_by, generated_at |
| ConstructionBatch | project_id, name, note nullable, created_by/at, archived; nhóm cấu kiện thi công cùng đợt, **không đổi** khu/phân đoạn thiết kế |
| ConstructionBatchComponent | batch_id + component_id (khóa chính đôi, unique), added_by/at, reason nullable |
| ComponentMapPosition | project_id, component_id, sheet_id công khai (`<key>-<sheet.id>`), points JSON tọa độ chuẩn hóa 0..1, status `DRAFT`/`REVIEWED`, source `manual`, created_by/at, reviewed_by/at, note; unique component_id+sheet_id. Tọa độ DB thắng manifest khi cùng component + sheet |
| ProgressEvent | component_id, component_stage_id, event_date, status, quantity/unit/note/evidence; batch_id nullable (đợt đã ghi), voided_at/by/reason nullable. Sự kiện đã void bị bỏ qua ở mọi truy vấn đọc |
| ComponentDesignParameter | project_id, component_id, name (`t_cm`, `L1_m`, …), value numeric, unit, source_drawing/page/row, source_file_hash, created_by/at; unique component_id+name. `t_cm` dùng để render tên bước có `t = … cm` |
| AuditLog | project_id, actor_id, action, entity, entity_id, detail JSON, timestamp |

Lưu file và khóa ngoại riêng; không sao chép nội dung ảnh/PDF vào DB. Chỉ một migration chain ở `backend/alembic` do Codex tích hợp.
