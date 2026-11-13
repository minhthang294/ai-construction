# Component QA golden fixture — 2026-11-12

Standalone, visual-confirmed fixture for Codex replay/review. No DB ids, no DB
writes, no product-module edits. Source PDF:
`/home/thangpham/Downloads/bản vẽ scan_1.pdf`; crops:
`/tmp/opencode/rag-diag/`.

## Files

- `manifest.json` — page list, replay contract, counts, gaps.
- `page_007.json` — H77 identity (TK-01).
- `page_008.json` — 45 piles, Phân đoạn 1 / Nhóm 2 / Cầu chính (TK-02).
- `page_015.json` — 39 piles, Phân đoạn 1 / Nhóm 3 / Cầu chính (TK-09);
  I49 excluded (boundary above I49).
- `page_022.json` — H77 quantities (TK-16), marked `joined` via p7 identity +
  the p22 statistics row.
- `page_046.json` — beam I-30-31 facts (TK-40).

Each page file has `page_number`, `document_name`, `model`, `prompt_version`,
`mode`, `confidence`, `warnings`, `verify_note`, `evidence`, and an
`extraction` object matching `save_page_extraction`/`validate_extraction`.
`component_facts` use the required non-empty `unit`; every fact also carries
`evidence_kind` (`direct` or `joined`), `source_page`, `source_quote`,
`source_row`, `source_column`, `source_table`, `source_sheet`, and
`join_note`.

## Visual checks

- p7: title `PHÂN ĐOẠN 2 - CẦU CHÍNH - NHÓM 1`; row
  `H77 | 0,2`; Nhóm 1 / Phân đoạn 2 / Cầu chính are merged cells.
  Crops: `p7-header.png`, `p7-table.png`, `p7-titleblock.png`.
- p8: title `PHÂN ĐOẠN 1 - CẦU CHÍNH - NHÓM 2`; 45 rows `I3`…`D151`;
  H48 confirmed in `p8-table.png`. Crops: `p8-header.png`,
  `p8-table-top.png`, `p8-table-bot.png`, `p8-table.png`,
  `p8-titleblock.png`.
- p15: title `PHÂN ĐOẠN 1 - CẦU CHÍNH - NHÓM 3`; 39 rows `I6`…`A150`;
  horizontal merged-cell rule sits directly above `I49`, so I49 is
  Phân đoạn 2. Crops: `p15-header.png`, `p15-table-top.png`,
  `p15-table-bot.png`, `p15-table.png`, `p15-boundary.png`,
  `p15-titleblock.png`.
- p22: statistics row `H77 | Cầu chính | 1 | 0,2 | 1`; quantity table
  `L1=0,2m / Cầu chính / t=1cm`: row 1 `0,003 m3`, row 4 `1,280 m2`,
  row 6 `0,304 m2`. Crops: `p22-header.png`, `p22-table.png`,
  `p22-khoiluong.png`, `p22-khoiluong-view.png`, `p22-titleblock.png`.
- p46: `Lxl = L = 1900`; `Tb 5cm` (sườn), `Tb 7cm` (đáy); fiberglass
  T1 4 tấm/1,520 m2, T2 7 tấm/2,800 m2, T3 1 tấm/0,240 m2, total
  `4,560 m2`. Crops: `p46-full.png`, `p46-table-full.png`,
  `p46-thickness-labels.png`, `p46-plan-callout.png`,
  `p46-titleblock.png`.

## Gaps / do not invent

- p46 length is reconciled conservatively: the callout says
  `Lxl = L = 1900`, and the notes define `L = Phạm vi hư hỏng`,
  `Lxl = Phạm vi xử lý hư hỏng`. The earlier diagnosis says damage length
  `L1 = 1500`, but no `1500` is visible on p46. The fixture therefore keeps
  only `chiều dài xử lý (Lxl) = 1900 mm` and **omits** `L` / `L1=1500` as
  ambiguous pending a second visual check.
- p46 has no direct volume, epoxy-area, or grinding-area row. Omitted; not
  computed from dimensions.
- p8/p15 row lengths were not transcribed; membership facts use
  `fact_name="trạng thái"`, `value="hư hỏng"`, `unit="trạng thái"` with the
  exact pile-code cell quote. Only H77 `0,2 m` is captured from p7.
- p22 quantity cells do **not** name H77. The H77 link is joined via the p22
  statistics row and p7 identity; every p22 quantity fact is marked `joined`
  and has `identity_pages: [7, 22]`.

## Replay

Map `document_name` + `page_number` to the copied DB, call
`save_page_extraction` with the payload fields, then verify with
`verify_note`. Do not import into `data/app.db`. The read-only test is
`backend/tests/engineering_ai/test_component_qa_golden_fixture.py`.
