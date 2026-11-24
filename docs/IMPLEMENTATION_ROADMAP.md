# Lộ trình triển khai

Cập nhật: 24/11/2026.

## Đã hoàn thành

- Shared core: auth, project/member, work item, organization/personnel, audit, migration chain.
- Cấu kiện: zone/segment, danh mục, alias, repair scope, bước thi công, tiến độ append-only, import seed có preview/commit, đợt thi công, tham số thiết kế.
- Bản đồ: nhiều sheet từ `data/storage/dap-maps/<key>/manifest.json`; vị trí nháp/duyệt trong DB; ảnh sheet private.
- Site: báo cáo ngày, manpower/preset, work log, next-day plan, ảnh + liên kết cấu kiện/work item, nhập tiến độ hàng loạt/theo ngày, void/correct, nhật ký snapshot/export.
- Overview: `latest-day`, `in-progress`, `segments`; reconciliation read-only.
- Engineering AI: chat trên page extraction + DB cấu kiện/tiến độ với citation; conversation CRUD; parser tin nhắn Zalo `progress-parse` (không gọi LLM, không ghi DB).
- Acceptance: hàng chờ nghiệm thu, PYC nháp từ cấu kiện, BBNT + checklist, numbering, revision/stale, preview/export; import lịch sử bằng `scripts/import_acceptance_workbook.py`.
- Docs: kiến trúc, API, data model, roadmap và các report agent đã cập nhật theo code hiện tại.

## Đã bỏ (23-24/11/2026)

- Upload/ingest tài liệu trong ứng dụng; OCR/Tesseract; embedding/sqlite-vec ingest.
- Tìm kiếm tài liệu và cross-reference.
- Checklist tài liệu độc lập. Checklist 7 mục trong BBNT vẫn còn.
- AI report-draft.
- AI gợi ý caption ảnh; caption ảnh do người dùng nhập/xác nhận.

## Kiểm chứng hiện tại

- Backend suite 24/11/2026: **396 passed, 6 skipped** (DB/storage tạm).
- Frontend/build chưa chạy lại trong đợt docs này.
- Không có migration mới trong đợt docs này.

## Tiếp theo

- Nạp hồ sơ thật và page extraction đã kiểm chứng; kiểm citation theo trang trước khi dùng trả lời.
- Chạy importer acceptance trên bản sao DB thật, đối chiếu PYC/BBNT và hàng chờ.
- Rà soát mã trùng/mơ hồ, corner repair chưa có trong catalog, Bunke và các vị trí bản đồ còn thiếu.
- Kiểm PWA/offline/camera trên điện thoại qua HTTPS trước khi dùng công trường.
