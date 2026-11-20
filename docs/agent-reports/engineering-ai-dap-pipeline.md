# DAP — pipeline & staging candidate thiết kế (PD2)

Ngày: 18/11/2026. Phạm vi: `backend/app/engineering_ai/`, test engineering_ai, sandbox
`data/storage/design-review/dap-design.sqlite3`. Không OCR, không đọc/gửi PDF, không ghi
`data/app.db`, không sửa nguồn.

## Changed files

- `backend/app/engineering_ai/dap_design.py` — pipeline + staging chỉ vào sandbox.
- `backend/tests/engineering_ai/test_dap_design.py` — 9 test.
- `docs/agent-reports/engineering-ai-dap-pipeline.md` — báo cáo này.
- Sandbox DB: thêm bảng `design_work_items` (1.344 dòng); **giữ nguyên 75 candidate**.

## Quy ước

- `REV1` là **revision tài liệu**, không phải giai đoạn thi công.
- Giai đoạn thi công (`stage`) chưa biết → **NULL**. Pipeline không suy ra stage.
- `revision` lưu riêng khi nguồn có ghi; hiện mọi nguồn đều NULL.

## Nguồn và đối chiếu metadata

| Nguồn | Hash DB | Khớp file gốc |
|---|---|---|
| `bản vẽ scan_1.pdf` (133 trang) | `3b3a9bc6…24c9` | Có |
| `Tập 1 - thuyết minh …_0001.pdf` | `37b3ead2…5c0d` | Có |
| `THKL_DAP_Phan doan 1 Cau chinh.xlsx` | `d20ecd9c…5e1` | Có |

Nguồn có cấu trúc ngoài PD1: golden fixture `page_007` (PD2 nhóm 1), `page_022`
(H77 định lượng), và 75 candidate PD2 đã có trong sandbox. `page_008`/`page_015` là PD1;
`page_046` là dầm PD1.

## Pipeline

`build_candidate_report(...)` / `build_from_review_database(...)` / `facts_to_work_items(...)` /
`stage_review_database(...)`:

- Candidate giữ `project_id`, `zone`, `segment`, `kind`, `design_group`, `raw_code`,
  `canonical_code` (chỉ upper), `review_status=NEEDS_REVIEW`, provenance đầy đủ
  (`source_hash`, `page`, `drawing`, hoặc `sheet/row/column`).
- Từ chối: thiếu page/drawing/hash, hash lạ, zone/segment/group sai, mã không đúng mẫu,
  status khác `NEEDS_REVIEW`. Trùng mã khác nhóm/khác trang → conflict, chỉ giữ bản đầu.
- Work item từ ma trận `01_COC_*`/`02_DAM_*`: chỉ ô số trực tiếp, bỏ ô công thức và cột tổng.
  Fact từ trang vàng: chỉ nhận fact số, bắt buộc `source_page/sheet/row/column` và
  `evidence_kind=direct|joined`; identity/text fact bị bỏ qua.
- Staging chỉ chấp nhận DB trong thư mục `design-review`, từ chối `app.db`; ghi
  `INSERT OR IGNORE` vào `design_work_items`; **không UPDATE/DELETE `component_candidates`**.

## Coverage chính xác sau staging

| Nhóm | Số lượng | Nguồn |
|---|---:|---|
| Candidate cọc PD2 | 75 (nhóm 1/2/3 = 3/33/39) | sandbox, trang 7/8/15, giữ nguyên |
| Candidate dầm PD2 | 0 | — |
| Work item PD1 cọc | 1.014 | THKL `01_COC_PD1` |
| Work item PD1 dầm | 325 | THKL `02_DAM_PD1` |
| Work item PD2 cọc | 5 (H77) | golden `page_022` (TK-16) |
| Work item PD2 dầm | 0 | — |
| **Tổng work item** | **1.344** | 1.339 `direct` + 5 `joined` |

128 mã công tác, 77 tên công tác. Toàn bộ `stage IS NULL`, `revision IS NULL`,
`review_status=NEEDS_REVIEW`. Chạy staging lần hai: `inserted=0`, `existing=1.344`.

Trang cần đọc trực quan: **6, 7, 8, 15** (ghi chú p8 về F5/B1554, I49 ở p15, đánh số cầu dẫn p6).

## Missing / conflicting mappings

- Thiếu work item định lượng cho 74 cọc PD2 còn lại; thiếu toàn bộ dầm PD2.
- PD3–PD18 và cầu dẫn (PD4–18) chưa có bảng cấu kiện/công tác.
- Dải p9–14, p16–20 chưa có candidate; p22 chỉ xác nhận H77, không đủ định danh cho bảng khối lượng.
- p8: 2 dòng nhóm 2 mơ hồ (“F5”, “B1554”); p15: ranh giới PD2 bắt đầu tại I49.
- `stage` chưa xác định; `revision` chưa có nguồn ghi rõ.
- 2.023 ô công thức trong THKL bị bỏ (không tính toán); sheet 03–06 không nằm trong danh mục công tác.

## Tests

Env: `DATABASE_URL` SQLite tạm trong `%TEMP%`; sandbox mở read-only khi đọc.

- `..\.venv\Scripts\python.exe -m pytest tests\engineering_ai\test_dap_design.py -q`
  → **9 passed**.
- `..\.venv\Scripts\python.exe -m pytest tests\engineering_ai -q`
  → **148 passed** (1 warning Starlette/httpx).

Test staging dùng bản copy DB trong `tmp_path`: xác nhận idempotent, 75 candidate không đổi,
`stage` NULL, và DB gốc không bị sửa.

## Sourcing check PD2 dầm / phần còn lại (18/11)

Không có nguồn cấu trúc nào cho dầm PD2. Không ghi sandbox trong lần kiểm này.

- 9 workbook khối lượng trong `~/Downloads` đều PD1 (`01_COC_PD1`, `02_DAM_PD1`); quét mã dầm
  chỉ thấy mã PD1 (`F-1-11` … `I-19-21`), không có “phân đoạn 2”/PD2.
- Fixture: `page_046` là dầm `I-30-31`, Nhóm I, Cầu chính, **segment NULL** (PD1);
  `page_007`/`page_022` là cọc PD2; `page_008`/`page_015` là PD1.
- Sandbox: `component_candidates` = 75 PILE, **0 BEAM**; `design_work_items` = 1.344
  (1.014 PD1 cọc, 325 PD1 dầm, 5 H77); toàn bộ dầm có `page` NULL vì chỉ có provenance THKL.
- `data/app.db`: 0 document/page/extraction; không có nguồn extraction ẩn.
- Không suy nhóm dầm từ nhóm cọc (theo `02_GHI_CHU_TRICH_XUAT.md`).

### Trang/dòng còn cần đọc

| Bản vẽ | PDF trang | Dữ liệu cần | Ghi chú |
|---|---:|---|---|
| TMB-01 | 6 | nhãn PD1–18 cầu dẫn | đã có ghi chú, cần xác nhận ranh giới |
| TK-01 | 7 | dòng H77 (nhóm 1, PD2) | đã có candidate; chỉ p22 được stage số |
| TK-02 | 8 | các dòng PD2 nhóm 2 | hiện chỉ có 45 dòng PD1; cần số dòng, gồm 2 dòng mơ hồ F5/B1554 |
| TK-03…TK-08 | 9–14 | phần tiếp nhóm 2 | cần dòng thuộc PD2 |
| TK-09 | 15 | PD2 nhóm 3 từ I49 | cần số dòng đến hết block |
| TK-10…TK-14 | 16–20 | phần tiếp nhóm 3 | cần dòng thuộc PD2 |
| TK-15…TK-30 | 21–36 | chi tiết cọc | H77 đã có p22 dòng 1/4/6; cần 74 mã còn lại (trang/dòng/ô) |
| TK-31, TK-32 | 37–38 | mặt bằng/ký hiệu dầm | cần mã dầm + segment + nhóm theo dòng |
| TK-33…TK-85 | 39–91 | chi tiết dầm | cần dòng/ô số cho từng mã PD2 (Lxl, t sườn/đáy, diện tích) |
| TK-88…TK-97 | 94–103 | dầm cầu dẫn | PD4–18, chưa bóc mã |
| TK-98 | 104 | phạm vi sửa dầm cầu dẫn | chưa có mã/dòng |
| TK-99…TK-105 | 105–111 | dầm nhóm I/II cầu dẫn | không suy nhóm từ cọc |
| Thuyết minh | 1–2, 33 | Rev1; quy tắc sửa dầm (mục 4.3) | p3 là NCKT mở rộng, tách phạm vi |
| chưa rõ | 112–133 | chưa có trong chỉ mục | cần lập chỉ mục trước |

`page_046` (dầm PD1) đủ nguồn nhưng chưa stage vì trùng phạm vi THKL PD1 và sẽ tạo định nghĩa
công tác song song; cần quyết định trước khi nhập.
