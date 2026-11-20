# Sprint 1 — báo cáo điều phối

## Files thay đổi

- `backend/app/core/component_models.py`, `component_seed.py`, `component_router.py`: schema danh mục, đọc seed, preview/commit, tạo thủ công và truy vấn theo project.
- `backend/alembic/versions/170f7a3596cf_component_inventory.py`, `backend/alembic/env.py`, `backend/app/main.py`: migration và đăng ký router.
- `backend/tests/test_component_import.py`, `test_component_seed_preview.py`, `test_component_conflicts.py`, `test_component_migration.py`: kiểm tra seed, import, xung đột và migration.
- `frontend/src/features/site/components/ComponentCatalogImport.tsx`, `frontend/src/features/site/lib/componentImport*`, `frontend/src/features/site/lib/api.ts`, `frontend/src/features/site/index.ts`, `frontend/src/app/App.tsx`: preview/duyệt, form nhập tay, hợp đồng API và điều hướng.
- `backend/app/acceptance/dm_sync.py`, `backend/tests/acceptance/test_dm_sync.py`, `scripts/start.sh`: tránh xóa dữ liệu ở dòng DM, tránh trùng số có 0 đầu, không tự chọn workbook nguồn để ghi.
- `.gitignore`, `scripts/run_opencode_agents.ps1`, `docs/API_CONTRACTS.md`, `docs/2026-11-18-component-inventory-design.md`: bảo vệ PDF private, cấu hình OpenCode và hợp đồng.

## Trạng thái tích hợp

- **Giao diện nhập tay đã có, đang tích hợp:** form tạo cấu kiện trong `ComponentCatalogImport.tsx` (chỉ dùng phân đoạn đã import, bắt buộc chọn loại/phạm vi), app shell đã mount ở trang Cấu kiện. Backend `POST /projects/{p}/components` tạo bản ghi `verification=NEEDS_REVIEW`, `record_origin=MANUAL_ENTRY`.
- Chưa có kết luận QA cho endpoint tạo thủ công và chưa kiểm UI trên trình duyệt.

## Kiểm thử

- SQLite tạm: nâng migration, hạ về `a7c3e9f2b641`, nâng lại; không chạy trên DB sản xuất.
- Seed private: 130 cấu kiện, 949 liên kết, 18 phân đoạn; 45/39 cọc nhóm 2/3 và 34 phạm vi phát sinh chưa gán nhóm.
- API: preview không ghi DB, nhập lại cùng/khác idempotency key, alias `I40-42`, viewer không được commit, từ chối nội dung không khớp workbook.
- Hai yêu cầu cùng idempotency key đồng thời được trả cùng kết quả và chỉ tạo một bộ cấu kiện; kiểm thử quyền khác công trình và engineer.
- **QA tổng hợp:** `backend/tests/test_component_synthetic_e2e.py` gồm 4 test (preview chỉ đọc, commit idempotent và giới hạn phân đoạn 1, thay đổi nguồn cần review thủ công, phân quyền/cô lập project); theo `component-qa.md` QA đã chạy **4 passed**.
- Tổng số test toàn bộ backend + frontend để QA cuối chốt; báo cáo này không kết luận.

## Unresolved mappings / manual review

- 34 phạm vi phát sinh chưa có nhóm bản vẽ xác nhận; không tự gán.
- Seed có 949 liên kết trỏ tới 78 dòng DM khác nhau (dòng 6–83), trong khi ghi chú đầu vào nêu 79 dòng công việc thuộc phân đoạn 1. Cần đối chiếu workbook nguồn để xác định dòng còn lại; không tự tạo liên kết.
- Kiểm tra nguồn và công tác trước đó của cọc I36; kiểm tra số BBNT trùng/thiếu. Ngày trong seed không phải sự kiện thực tế.
- Phân đoạn 2–18 mới có khung, không có danh mục cấu kiện được tự tạo.
- UI preview chưa sửa trực tiếp candidate; commit chỉ chấp nhận bản dữ liệu trùng workbook. Hash lưu trong DB là hash của seed, không phải hash workbook DM gốc hoặc PDF.
- **Chưa lưu file nguồn upload vào source storage.** Workbook đã thay đổi khi cấu kiện đã tồn tại sẽ yêu cầu đối chiếu thủ công. **Chưa kiểm UI bằng trình duyệt hoặc E2E.**
- **Rủi ro DM sync** (chi tiết trong `docs/agent-reports/acceptance-dm-review-2026-11-18.md`): cột B "SỐ BIÊN BẢN" đang nhận số PYC; workbook dùng chung và khóa chỉ theo số nên có thể ghi đè dòng của project khác. Chưa sửa vì cần quyết định A (khóa dòng ổn định), B (workbook theo project), C (ý nghĩa cột B).
- PDF bản vẽ và thuyết minh chưa được định vị trong `data/`; không khẳng định chúng không có ở vị trí private khác.
- Người dùng cho phép đưa file Excel vào Git; file nghiệm thu gốc đã được Git theo dõi trước đó. Chưa thực hiện commit hoặc push.

Ba phiên OpenCode đã rà soát trong pane Herdr; acceptance và site-report đã triển khai phần trong phạm vi được giao. Không có commit, push hoặc thay đổi database sản xuất.
