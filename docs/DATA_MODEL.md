# Data model chung

Cập nhật: 24/11/2026. Khóa UUID; phạm vi `project_id` khi áp dụng. Service/API kiểm tra liên kết cùng công trình trước khi ghi. Không lưu nội dung nhị phân PDF/ảnh trong DB; chỉ lưu metadata, hash và đường dẫn private. Một migration chain ở `backend/alembic`.

## Dự án và danh mục

| Entity | Trường chính / quan hệ |
| --- | --- |
| Project | name, client, location, report_title nullable, status |
| ProjectMember | project_id, user_id, role |
| Organization, Personnel | project_id, name/role/organization_id |
| WorkItem | project_id, code, name, location, component, status `planned/in_progress/completed/pending_acceptance/rectify` |
| AuditLog | project_id, actor_id, action, entity, entity_id, detail JSON, timestamp |

## Báo cáo ngày và ảnh

| Entity | Trường chính / quan hệ |
| --- | --- |
| DailyReport | project_id, report_date (unique cùng project), status `draft/reviewed`, notes, site_notes_json, snapshot |
| ManpowerEntry | report_id, group_name, person_name?, count?, organization_id?; `0` khác `null` |
| ManpowerPreset | project_id, group_name, person_name/count/organization_id? |
| DailyWorkLog | report_id, work_item_id?, work_name?, location, component, quantity?, unit, status, notes |
| NextDayPlan | report_id, plan_date, work_item_id?, description, location, manpower, equipment, dependency |
| SitePhoto | project_id, report_id?, original_path, sha256, capture_time?, upload_time, GPS?, device?, category?, location/component/stage?, confirmed_caption?, suggested_caption? (legacy), mime/size/filename, client_upload_id? |
| PhotoWorkItemLink | photo_id + work_item_id (unique) |
| SitePhotoComponent | photo_id + component_id (khóa chính đôi), project_id, created_by/at |
| SiteProgressBulkBatch | project_id, idempotency_key, payload_hash, result_json, created_by/at |
| GeneratedDocument | project_id, kind, source_id?, path, sha256, template_sha256?, format?, report_date?, metadata_json, created_by/at |

## Cấu kiện và thi công

| Entity | Trường chính / quan hệ |
| --- | --- |
| StructureZone | project_id, name, name_key |
| Segment | zone_id, number, source_code |
| DesignGroup | project_id, group_type, name, drawing, source, source_page |
| StructuralComponent | project_id, segment_id, design_group_id?, type `pile/beam`, raw_code, canonical_code, source_id/hash/row, verification, record_origin, created_by/at; unique project+segment+type+canonical_code |
| ComponentAlias | component_id, project_id, segment_id, type, alias; unique project+segment+type+alias |
| RepairScope | component_id, kind `DESIGN_SCOPE/ADDITIONAL_SCOPE`, verification, revision, approval_reference?, reviewed_by/at |
| ComponentWorkLink | component_id, source_hash, dm_row, seed_sheet/row, work, raw_location |
| ComponentImportBatch | project_id, idempotency_key, payload_hash, result |
| StageDefinition | project_id, component_type, code, name, position |
| ComponentStage | component_id, stage_definition_id, repair_scope_id, design_quantity JSON?, created_by/at |
| ProgressEvent | component_id, component_stage_id, event_date, status `IN_PROGRESS/COMPLETED/BLOCKED`, quantity/unit/note?, evidence_refs, batch_id?, created_by/at, voided_at/by/reason? |
| ComponentDesignParameter | project_id, component_id, name (`t_cm`, `L1_m`…), value, unit, source_drawing/page/row/file_hash, created_by/at; unique component+name |
| ConstructionBatch | project_id, name, note?, created_by/at, archived |
| ConstructionBatchComponent | batch_id + component_id (khóa chính đôi), added_by/at, reason? |
| ComponentMapPosition | project_id, component_id, sheet_id công khai (`<key>-<sheet.id>`), points JSON chuẩn hóa 0..1, status `DRAFT/REVIEWED`, source `manual`, created_by/at, reviewed_by/at, note?; unique component+sheet |

## Engineering AI

| Entity | Trường chính / quan hệ |
| --- | --- |
| SourceDocument | project_id, type, original_name/key, original_path, sha256, version, is_current, is_effective, change_note, effective_at/by, status, page_count, drawing_number?, revision? |
| DocumentPage | document_id, page_number 1-based, rendered_path?, text?, ocr_text? (legacy), tables_json?, ocr_confidence? (legacy), extraction_method, drawing_number?, revision?, width/height?, needs_review |
| PageExtraction | page_id, document_id, page_number, page_sha256?, model, prompt_version, mode, status `proposed/verified/rejected`, confidence?, extraction_json, warnings_json?, created_by, verified_by/at, verify_note? |
| AIConversation | project_id, title?, messages_json, created_by/at, updated_at |
| AICitation | project_id, conversation_id, message_index, chunk_id?, document_id, page_id, document_name, version, page_number, drawing_number?, revision?, quote, url, ocr_confidence? (legacy) |

`DocumentChunk` và `DocumentEmbedding` còn trong schema cũ nhưng không thuộc luồng ingest/retrieval hiện tại. Không còn upload tài liệu, OCR/Tesseract, embedding ingest, tìm kiếm tài liệu hay cross-reference (bỏ 23-24/11/2026).

## Acceptance

| Entity | Trường chính / quan hệ |
| --- | --- |
| AcceptanceRequest | project_id, work_item_id?, daily_report_id?, number, status `draft/submitted`, requested_at, revision, profile ids, project/client/location/request fields, content/subject/field/urgency, signature names, org names, notes |
| AcceptanceRecord | request_id, number?, request_updated_at?, request_snapshot_json?, revision, supersedes_id?, status `draft/confirmed`, result?, confirmer_id?, confirmed_at?, record_date/time, compliance fields, notes |
| AcceptanceParticipant | record_id, role, organization?, person_name, position?, sort_order |
| AcceptanceChecklist | record_id, item, state `yes/no/unconfirmed`, evidence_refs JSON, note?, sort_order |
| AcceptanceNumberSequence | project_id, kind `pyc/bbnt`, prefix, start/next, width, reset_policy, period_key?, date_format; unique project+kind |
| AcceptanceParticipantProfile | project_id, full_name, organization?, position?, role, active |
| ComponentAcceptanceLink | project_id, component_id, stage_id?, scope_id?, request_id? hoặc record_id? (đúng một target); unique theo component/stage/scope/target |

Checklist BBNT vẫn là một phần của acceptance record. “Checklist tài liệu độc lập” đã bỏ 23-24/11/2026. AI không tạo/sửa checklist hoặc kết luận nghiệm thu.
