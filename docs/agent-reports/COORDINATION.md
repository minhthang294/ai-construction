# Bảng điều phối agent

Cập nhật: 15:26 11/11/2026 (Asia/Ho_Chi_Minh). Người điều phối giữ shared core, migration, tích hợp, kiểm thử và quyết định cuối cùng; ba agent module chỉ sửa trong `docs/AGENT_BOUNDARIES.md`.

**Cổng xác minh cuối vòng 2:** `scripts/verify_all.sh` → backend **172 passed**, frontend **29 passed**, production build **pass**. Migration head `d8e52a3c4b21`, đã áp dụng vào `data/app.db` (DB chưa có dữ liệu người dùng).

## 1. Trạng thái xác minh

| Hạng mục | Kết quả | Ghi chú |
| --- | --- | --- |
| Backend full suite | 137 passed, 1 failed | `tests/acceptance/test_exports.py::test_pyc_export_replaces_validated_cells_and_preserves_formatting` |
| Frontend test | 10/10 passed | `npm test` |
| Frontend build | passed | `npm run build` |
| Alembic | một head `bf490c940488`; upgrade DB trống OK | đã có bảng site, acceptance, engineering AI |
| `data/app.db` | `bf490c940488`, 0 bản ghi | không dùng để test |
| Hồ sơ thật | 2 PDF scan trong `~/Downloads` | 133 trang bản vẽ + 108 trang thuyết minh; chưa ingest |
| OCR tiếng Việt | đã có `vie` user-space | `TESSDATA_PREFIX=/home/thangpham/.local/share/tessdata` |

Nguyên nhân lỗi backend duy nhất: fixture acceptance đang đọc trực tiếp workbook người dùng đang mở trong LibreOffice (`/home/thangpham/Downloads/YCNT và BBNT.19.10 - nt thuc te.xlsx`). Workbook đã được lưu lại lúc 13:46, mất `xl/calcChain.xml`, nên assertion cũ không còn đúng. Không phải lỗi exporter.

## 2. Agent và phạm vi

| Agent | Session hoàn thành gần nhất | Trạng thái | Phạm vi |
| --- | --- | --- | --- |
| site-report-agent | `ses_e36f13760ffeKoaUedAuGyJNMS` | idle, đã bàn giao | `backend/app/site`, `frontend/src/features/site`, test, report |
| engineering-ai-agent | `ses_e36f13757ffeFKbEr22sLHVYm2` | idle, đã bàn giao | `backend/app/engineering_ai`, `frontend/src/features/engineering-ai`, test, report |
| acceptance-agent | `ses_e36f13748ffe03hZHjz0pRpFgd` | idle, đã bàn giao | `backend/app/acceptance`, `frontend/src/features/acceptance`, test, report |

## 3. Vòng 1

| Việc | Chủ sở hữu | Trạng thái |
| --- | --- | --- |
| Tách test acceptance khỏi workbook đang mở; dùng bản canonical/synthetic; xử lý workbook không có `calcChain`; default template trỏ bản canonical | acceptance-agent | xong: 46 acceptance test pass, typecheck pass; chờ full gate |
| Kiểm OCR thật trên mẫu 2 trang/mỗi PDF, đo thời gian/confidence, xác nhận citation và giới hạn 50 MB; không ghi DB chung | engineering-ai-agent | xong: 40 test pass, typecheck pass; báo cáo Real source readiness đã cập nhật |
| Backoff + giới hạn thử lại + nút bỏ mục hỏng cho queue offline; test logic | site-report-agent | xong: 50 backend test, 24 frontend test, build pass; chờ full gate |
| Board, script xác minh, script làm mới template, hướng dẫn OCR | điều phối viên | xong |

## 4. Chặn và quyết định cần người dùng

1. **Bản mẫu canonical**: đã làm mới lúc 14:19 từ workbook người dùng lưu lúc 14:18 (`SHA-256 d5dd4688…`), bản cũ `e204c406…` giữ tại `data/templates/archive/`. Khi người dùng sửa workbook lần nữa, đóng LibreOffice rồi chạy lại `scripts/refresh_acceptance_template.sh`; script từ chối chạy nếu workbook còn mở.
2. **Chưa có tài khoản quản trị**: `data/app.db` có 0 user, nên chưa thể đăng nhập. Người dùng chạy `scripts/bootstrap_admin.sh` để tạo admin (mật khẩu không lưu vào shell history).
3. **Ingest hồ sơ thật**: hồ sơ thật đã sẵn sàng nhưng chưa nạp vào `data/app.db`. Cần admin/project thật; đặt `ENGINEERING_AI_MAX_PDF_BYTES` ≥ 70 MB cho file thuyết minh 66 MB và `TESSDATA_PREFIX` cho `vie`. Quy trình: `docs/REAL_DATA_INGESTION.md`. Ước tính 10–15 phút cho 241 trang.
4. **Git**: thư mục chưa phải Git repo; không có lịch sử thay đổi để review/rollback. Cần quyết định khởi tạo Git trước khi làm tiếp khối lượng lớn.
5. **Quyền xác nhận nghiệm thu**: hiện chỉ admin/project_manager; nếu cần vai trò riêng phải sửa shared auth.
6. **Kiểm PWA/camera trên điện thoại thật** vẫn chờ HTTPS và thiết bị.

## 5. Vòng 2 — addendum bắt buộc

Kiến trúc và schema chi tiết tại `docs/ADDENDUM_ARCHITECTURE.md`. Migration mới: `c7d41f2b9a10` (đã upgrade thử DB trống thành công). `sqlite-vec` đã thêm dependency và loader connection.

| Việc | Chủ sở hữu | Trạng thái |
| --- | --- | --- |
| sqlite-vec persistent vector store; ingest status; table/section extraction; effective revision; compare; conversation CRUD/search; vision một trang | engineering-ai-agent | xong: 47 test pass, typecheck/build pass |
| Numbering nguyên tử; participant library; BBNT reuse + stale + revision; preview; work-item history; AI separation tests; snapshot BBNT | acceptance-agent | xong: 66 test pass, typecheck pass |
| Lọc ảnh theo work item; panel lịch sử nghiệm thu trong trang báo cáo | site-report-agent | xong: 51 backend test, 29 frontend test, build pass; đã nối callback App.tsx |
| Migration, loader, API contracts, DoD test, full gate | điều phối viên | xong: migration `c7d41f2b9a10` + `d8e52a3c4b21`; full gate 172 backend + 29 frontend + build pass |

## 6. Definition of Done (addendum)

| # | Yêu cầu | Bằng chứng |
| --- | --- | --- |
| 1 | Upload PDF thành công | `tests/test_addendum_dod.py` upload 201 |
| 2 | File lưu bền vững | file gốc tồn tại sau request; DB path kiểm lại |
| 3 | OCR/index hoàn thành | `test_real_ocr_pipeline_indexes_scanned_page` + status ready/chunk/vector |
| 4 | Đóng/mở lại vẫn truy cập | client/session mới đọc document gốc 200 |
| 5 | Hỏi nhiều lần không upload lại | hai chat cùng conversation, citation vẫn có |
| 6 | Citation mở đúng trang | citation page 2 + render URL 200 |
| 7 | Revision mới giữ revision cũ | versions {1,2}, file v1 vẫn 200, effective chỉ sau xác nhận |
| 8 | Cô lập project | project khác 404/search rỗng |
| 9 | PYC không gọi AI | `tests/acceptance/test_ai_separation.py` |
| 10 | BBNT không gọi AI | cùng test, monkeypatch provider raise |
| 11 | BBNT lấy lại PYC | `reused.work_item_id/location`, participants prefill |
| 12 | Excel/PDF đúng template | PYC xlsx mở được, ô B6/C1 đúng; PDF test khi có LibreOffice |
| 13 | Không trùng số | `test_numbering.py` 12 thread + DoD 6 số khác nhau |
| 14 | Không tự kết luận | record mới result null, checklist toàn unconfirmed |
| 15 | Lịch sử/truy xuất | work-item acceptance-history + conversation history |

## 7. Cổng xác minh

```bash
scripts/verify_all.sh
```

Script dùng DB và storage tạm dưới `/tmp/opencode`, không đọc/ghi `data/app.db` hay file người dùng.
