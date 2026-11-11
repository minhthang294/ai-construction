# Lộ trình triển khai

1. Audit nguồn: đã thấy repository trống và Excel mẫu; PDF/bản vẽ chưa có.
2. Codex tạo shared contracts, auth, schema/migration, backend/frontend skeleton, các điểm mount router/navigation.
3. Ba OpenCode agent triển khai độc lập theo boundaries và ghi report, chạy trong pane herdr riêng. Vì thư mục không phải Git repo, không dùng worktree/merge giả; kiểm file trực tiếp và chỉ tạo Git sau khi có quyết định phù hợp.
4. Codex review, gắn router/navigation, kiểm quyền project, migration, xuất template và test liên module.
5. Nạp hồ sơ thật khi có, kiểm OCR/citation theo trang và duyệt bởi kỹ sư. Chưa có hồ sơ thì AI chỉ trả trạng thái thiếu nguồn.
6. Kiểm end-to-end mobile/offline/PYC/BBNT bằng dữ liệu thử tách biệt và không ghi đè template gốc.

## Trạng thái 11/11/2026

- Các module backend/frontend đã tích hợp; ba agent OpenCode Go đã chạy trong ba pane riêng. Migration đầu và migration bổ sung cho preset/ghi chú/ảnh/liên kết PYC đã áp dụng.
- Luồng API tổng hợp với PDF tổng hợp, citation theo trang, báo cáo, ảnh và PYC/BBNT đã kiểm tự động; PWA shell/cache và queue offline có test logic.
- Hồ sơ thật đã có trong `~/Downloads`: bản vẽ scan 133 trang và thuyết minh 108 trang; chưa ingest. OCR tiếng Việt đã cài user-space; quy trình nạp và kiểm chứng ở `docs/REAL_DATA_INGESTION.md`.
- Vòng 1 sau bàn giao: test acceptance tách khỏi workbook đang mở, queue offline có backoff/giới hạn thử lại/nút bỏ mục, canonical template được làm mới. Chạy `scripts/verify_all.sh` trước khi kết luận.
- Vòng 2 theo addendum: tách System A (knowledge base bền vững, sqlite-vec, effective revision, conversation) và System B (PYC/BBNT tất định, numbering, không AI); theo dõi tại `docs/agent-reports/COORDINATION.md` và kiến trúc tại `docs/ADDENDUM_ARCHITECTURE.md`.
- Cổng xác minh 15:26 11/11/2026: `scripts/verify_all.sh` → 172 backend test, 29 frontend test, build pass; migration `d8e52a3c4b21`; DoD integration test 3/3 pass (gồm OCR thật).
- Chưa nạp hồ sơ thật vào `data/app.db` và chưa có admin; quy trình ở `docs/REAL_DATA_INGESTION.md`.
- Cần thử PWA/offline và camera trên điện thoại qua HTTPS trước khi đưa ra công trường.
