# Kiến trúc bổ sung: Knowledge Base và Acceptance tất định

Cập nhật: 11/11/2026. Tài liệu này là quyết định kiến trúc bắt buộc cho vòng 2.

## 1. Tách hai hệ thống

- **System A — Engineering AI**: kho tri thức công trình, upload một lần, ingest nền, retrieval theo project, citation theo trang, lịch sử hội thoại, versioning.
- **System B — Acceptance**: PYC/BBNT sinh từ dữ liệu có cấu trúc và template Excel; **không import, không gọi** provider LLM, Vision hay Embedding.

Ranh giới kiểm chứng bằng test tự động:
- `tests/acceptance/test_ai_separation.py` chặn import provider AI trong package acceptance và chặn mọi lời gọi AI khi tạo/xuất PYC/BBNT.
- `tests/test_addendum_dod.py` kiểm end-to-end 15 điểm Definition of Done.

## 2. Persistent vector database

Dùng **sqlite-vec** ngay trong SQLite hiện tại (file `data/app.db`), không tạo vector store tạm:

- Extension được nạp trên mọi kết nối SQLite qua `app.core.database`.
- Mỗi cặp `(project_id, embedding_model, dimension)` có một bảng `vec0` riêng, tên băm ổn định.
- Vector vẫn có bản ghi JSON trong `engineering_ai_document_embeddings` làm nguồn chuẩn/fallback.
- Retrieval ưu tiên KNN từ sqlite-vec; nếu extension hoặc bảng không có, fallback ranker hiện tại.
- Không gửi lại toàn bộ hồ sơ; chỉ chunk/trang liên quan.

## 3. Trạng thái ingest

`pending → running → ocr_completed → indexing → ready`, lỗi `failed`. UI hiển thị đúng các nhãn này. Ingest chạy nền, idempotent, không tạo lại vector cho tài liệu không đổi.

Bổ sung pipeline:
- trích bảng native bằng PyMuPDF (`tables_json` trên trang);
- chunk theo trang và section (`section` trên chunk), không cắt qua tiêu đề;
- nhận diện loại hồ sơ mở rộng: drawing, specification, technical_guideline, construction_method, standard, material_record, test_record, acceptance_record, other.

## 4. Versioning và hiệu lực

- `is_current`: phiên bản mới nhất được tải lên.
- `is_effective`: phiên bản đang có hiệu lực để tra cứu, do người quản lý hồ sơ xác nhận.
- Phiên bản đầu tiên của một họ tài liệu là effective mặc định.
- Phiên bản mới **không** tự effective; bản cũ vẫn effective đến khi có xác nhận.
- API xác nhận hiệu lực, lưu `effective_at`, `effective_by`, `change_note`; không ghi đè file cũ.
- Retrieval mặc định chỉ dùng effective; `scope=history` cho phép tra cứu lịch sử. Có API so sánh hai phiên bản (metadata + thống kê trang/chunk, không tự kết luận thay đổi thiết kế).

## 5. Hội thoại

Lưu conversation/messages/citations trong DB. Bổ sung: tạo mới, danh sách, tìm kiếm, đổi tên, xóa, mở lại và hỏi tiếp. Xóa conversation chỉ xóa hội thoại, không xóa tài liệu/citation gốc.

## 6. Vision có kiểm soát

Khi câu hỏi cần phân tích hình ảnh, chỉ gửi **một trang render của chunk top-1** cho Vision provider nếu được cấu hình; mặc định tắt. Không gửi toàn bộ PDF. Kết quả vẫn phải có citation trang và cảnh báo OCR thấp.

## 7. Acceptance tất định

- Không AI trong package `backend/app/acceptance/`.
- Số PYC/BBNT sinh từ bảng cấu hình `acceptance_number_sequences` (prefix, start, width, reset policy, period key). Cấp số bằng một câu UPDATE ... RETURNING nguyên tử + unique constraint; có test đa luồng.
- PYC lấy project/work item/người tham gia từ DB; không tự tạo tên/chữ ký.
- BBNT tái sử dụng PYC: project, work item, vị trí, thời gian, người tham gia đã nhập, daily report, ảnh đã xác nhận, tài liệu kỹ thuật. Không bắt nhập lại.
- Lưu `request_updated_at` trên BBNT; nếu PYC thay đổi sau đó, API trả `stale=true` và cảnh báo, không tự sửa BBNT đã phát hành. Có API tạo revision BBNT mới, bản cũ giữ nguyên.
- Preview trả đúng dữ liệu sẽ điền vào template trước khi xuất.
- Excel/PDF vẫn dùng template gốc, copy file, kiểm tra mở được và ô quan trọng.

## 8. Schema bổ sung (migration do coordinator quản lý)

| Bảng | Cột/bảng mới |
| --- | --- |
| `engineering_ai_documents` | `change_note TEXT`, `is_effective BOOLEAN NOT NULL DEFAULT 1`, `effective_at DATETIME`, `effective_by VARCHAR(36)` |
| `engineering_ai_document_pages` | `tables_json TEXT` |
| `engineering_ai_document_chunks` | `section VARCHAR(255)` |
| `acceptance_number_sequences` | bảng mới: `id`, `project_id`, `kind`, `prefix`, `start_number`, `next_number`, `width`, `reset_policy`, `period_key`, `date_format`, `created_at`, `updated_at`; unique `(project_id, kind)` |
| `acceptance_participant_profiles` | bảng mới: `id`, `project_id`, `full_name`, `organization`, `position`, `role`, `active`, `created_at`, `updated_at` |
| `acceptance_requests` | `revision INTEGER NOT NULL DEFAULT 1`; `requested_by_profile_id`, `supervisor_profile_id`, `investor_profile_id` (nullable) |
| `acceptance_records` | `number VARCHAR(40)`, `request_updated_at DATETIME`, `revision INTEGER NOT NULL DEFAULT 1`, `supersedes_id VARCHAR(36)`, `request_snapshot_json TEXT` |

Migration `d8e52a3c4b21` bổ sung `request_snapshot_json` để BBNT đã phát hành giữ nguyên dữ liệu PYC tại thời điểm tạo, và partial unique index `(project_id, document_key) WHERE is_effective = 1` để mỗi họ tài liệu chỉ có một revision hiệu lực.

Không thêm cột vector vào migration; bảng `vec0` được tạo lazy và nằm trong cùng file SQLite.

## 9. Phân công vòng 2

| Chủ sở hữu | Việc |
| --- | --- |
| engineering-ai-agent | sqlite-vec, trạng thái ingest, table/section, effective revision + compare + scope, conversation CRUD/search, vision trang đơn, test/report |
| acceptance-agent | numbering nguyên tử, participant library, BBNT reuse + stale + revision, preview, work-item history, AI separation tests, test/report |
| site-report-agent | lọc ảnh theo work item, panel lịch sử nghiệm thu theo work item trong trang báo cáo, test/report |
| coordinator | migration, loader sqlite-vec, dependency, docs/API contracts, DoD test, full gate |

## 10. Definition of Done

Theo dõi tại `docs/agent-reports/COORDINATION.md`; mỗi mục phải có test hoặc bằng chứng chạy thực tế, không chỉ mô tả.
