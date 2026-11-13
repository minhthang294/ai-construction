# Acceptance (PYC/BBNT) Agent Report

## Codex integration update — 11/11/2026

Acceptance router and frontend page are mounted. Export history and audit use the shared `generated_documents` and `audit_logs` tables; the integrated Alembic migration omits the former module-local duplicate tables. PYC creation fills missing common project fields from `Project`; downloads are limited to acceptance kinds and the project's private export directory. Remaining integration items are recorded in the "Unresolved issues" section below.

## Vòng 3 — Chọn công việc cho nội dung PYC (12/11/2026)

- **Mục tiêu:** form tạo/sửa PYC cho chọn công việc từ danh mục core thay vì chỉ gõ tay, nhưng vẫn giữ nguyên nội dung PYC cũ ngoài danh mục.
- **Nguồn danh mục:** `listWorkItems()` (`GET /projects/{project_id}/work-items`) đã có trong `lib/api.ts`; `AcceptancePage` tải bằng một effect riêng, không đưa vào `Promise.all` chính. Nếu API lỗi/rỗng, trang vẫn tải PYC/BBNT bình thường và form hiện cảnh báo nhỏ, cho nhập tay và lưu.
- **Helper thuần:** `lib/workItemOptions.ts`
  - `buildWorkItemOptions()` gom theo tên đã chuẩn hoá khoảng trắng + case, giữ thứ tự xuất hiện đầu tiên và casing danh mục.
  - Tên chỉ có đúng 1 id → option `{id, name}`; tên trùng nhiều id → `{id: null, name}` để không gắn nhầm hạng mục.
  - `withCurrentWorkItem()` thêm nội dung PYC hiện tại vào danh sách chọn nếu ngoài danh mục (ví dụ "Sơn chống tia UV phạm vi dán sợi cọc").
  - `resolveWorkItemSelection()` trả `{content, work_item_id}`; lựa chọn rỗng/ngoài danh mục giữ nguyên nội dung đang có và bỏ liên kết.
  - `findWorkItemOption()` / `workItemNameKey()` dùng cho lookup và so sánh khi sửa tay.
- **RequestForm:**
  - `FormState`/`BLANK`/`toForm()` thêm `work_item_id`; payload submit gửi `work_item_id` (backend đã hỗ trợ).
  - Select "Chọn công việc" đặt ngay trên textarea "Nội dung nghiệm thu", kèm nhãn "Chọn từ danh mục để điền nhanh, có thể sửa lại bên dưới."
  - Chọn tên duy nhất → điền `content`, lưu `work_item_id`; chọn tên trùng → điền `content`, `work_item_id=null`.
  - Sửa tay textarea khác tên đã chọn → tự bỏ `work_item_id`; sửa khoảng trắng/case của đúng tên đó thì giữ liên kết.
  - Tên ngoài danh mục vẫn hiện trong select dưới dạng lựa chọn hiện tại và luôn hiển thị trong textarea.
- **Quyết định nhỏ:** không import helper của module site để tránh phụ thuộc chéo; logic unique-name được viết lại thuần trong acceptance. Option của tên trùng được ghi chú "(nhiều hạng mục)" trên UI. Không thêm cột/migration backend.

Files changed this round:
- `frontend/src/features/acceptance/lib/workItemOptions.ts` (mới)
- `frontend/src/features/acceptance/lib/workItemOptions.test.ts` (mới)
- `frontend/src/features/acceptance/components/RequestForm.tsx`
- `frontend/src/features/acceptance/pages/AcceptancePage.tsx`
- `docs/agent-reports/acceptance.md`

Tests:
- `cd frontend && npx vitest run src/features/acceptance` → **25 passed** (4 files).
- `cd frontend && npx tsc --noEmit -p tsconfig.json` → **exit 0**.
- Bộ test mới phủ: 41 dòng → 7 option; tên duy nhất giữ id; tên trùng id null; chuẩn hoá khoảng trắng/case; nội dung cũ ngoài danh mục vẫn hiển thị/giữ nguyên; xoá lựa chọn không xoá nội dung đã nhập.

Còn lại:
- Chưa chạy full `npm run build`/backend gate theo yêu cầu coordinator.
- Nếu sau này backend trả catalog phân trang hoặc hơn một trang, dropdown chỉ thấy trang đầu; hiện API trả toàn bộ danh mục dự án.
- Chưa có test component React cho tương tác select/textarea (repo chưa có React Testing Library); hành vi thuần đã được test ở helper.

## PYC export fixes — 12/11/2026

- **PDF contains only the PYC/BBNT pages.** After LibreOffice converts the validated workbook, `_select_pdf_pages()` in `service.py` uses PyMuPDF to keep:
  - PYC export: every page whose title is `PHIẾU YÊU CẦU NGHIỆM THU CÔNG VIỆC XÂY DỰNG` before the first `BIÊN BẢN NGHIỆM THU CÔNG VIỆC XÂY DỰNG` page (DM and the hidden `PYC (2)` copy are dropped).
  - BBNT export: only the BBNT block, from the first BBNT title through its continuation pages (stopping at the next PYC title, i.e. the hidden copy). The PYC page is no longer included.
  - Unrecognised pages raise `AcceptanceError(500, ..., code="pdf_page_detection_failed")` instead of silently keeping the whole PDF. The validated `.xlsx` workbook path/hash remain in export metadata.
- **Download filename.** `download_filename()` now returns `YC-<body>.<xlsx|pdf>` for `kind=pyc` and strips stored prefixes `YC-`, `PYC-`, `BBNT-`, `NT-` before joining. Examples: `YC-001.xlsx`, `YC-32.pdf`, `YC-001.pdf`; no `PYC-YC-001`. The numbered DB prefix configuration is unchanged. The frontend fallback filename uses `YC-` for PYC too.
- **Cell B6 / B5.** `_number_value()` strips the numbering prefix before writing: `YC-001` and `PYC-001` → `"001"` (string, leading zero preserved), bare `32` → `32` (number). The template label `Số: YC-` therefore prints `Số: YC-001`, not `Số: YC- YC-001`.
- **Urgency tick.** `_pyc_replacements()` treats `None`/unknown urgency as `normal`, so `D14=☑`, `D15=□`, `D16=□`; `urgent`/`very_urgent` tick their own box. `RequestForm` defaults new PYC to `normal` and maps an edited PYC with `urgency=null` to `normal` while still allowing Gấp/Rất gấp.
- **E10 content.** `_pyc_content_text()` prints `content tại subject` (Đối tượng nghiệm thu); it normalises whitespace, avoids a double `tại` when content already ends with it, keeps `content` alone when there is no subject, and prints the subject alone when content is empty.

Files changed for this round:
- `backend/app/acceptance/service.py`
- `backend/tests/acceptance/test_exports.py`
- `frontend/src/features/acceptance/components/RequestForm.tsx`
- `frontend/src/features/acceptance/lib/api.ts`
- `frontend/src/features/acceptance/lib/download.test.ts`
- `docs/agent-reports/acceptance.md`

Tests:
- `cd backend && DATABASE_URL="sqlite:////tmp/opencode/acceptance-pyc-fix-$$.db" ../.venv/bin/python -m pytest tests/acceptance -q` → **80 passed** (LibreOffice + PyMuPDF were available, so the PDF page tests ran).
- `cd frontend && npx vitest run src/features/acceptance` → **16 passed** (3 files).
- Acceptance feature typecheck (`tsc --noEmit ... src/features/acceptance/index.ts`) → **exit 0**.
- PDF tests assert PYC = 1 page, BBNT = 1 page (no PYC page), no `DANH MỤC HỒ SƠ`; the missing-title path is tested separately through `_select_pdf_pages()`.

APIs/models:
- PYC preview-image and DELETE routes were added in round 8 (see below); the round-6 filename change only affected `Content-Disposition` on the existing download route.
- No model/migration changes. The download name still comes from `generated_documents.metadata_json["number"]`.

Dependencies:
- PDF filtering requires **PyMuPDF** (`import pymupdf`). It is present in the local venv and must be installed in the deployment image. If it is missing, PDF export fails with `pdf_conversion_failed` and an install hint.

New unresolved notes:
1. If the converted PDF has no extractable title text (for example an image-only workbook), the export now fails with `pdf_page_detection_failed`; there is no OCR fallback by design.
2. BBNT downloads still derive their number from the linked PYC number (`metadata["number"] = view.number`) as before; only the PYC filename convention was changed in this round.

## Vòng 2 — Addendum acceptance (11/11/2026)

- **AI separation:** `backend/app/acceptance/` contains no LLM/Vision/Embedding provider import or call, and no reference to the DeepSeek POC `engineering_ai.page_extraction` module or `scripts/deepseek_page_extract.py`. `test_ai_separation.py` statically scans the package and monkeypatches `provider_from_env`, `vision_from_env`, `embeddings_from_env` plus a fake `app.engineering_ai.page_extraction` module to raise; PYC/BBNT create + XLSX/PDF export still succeed. A new record has `result=null` and checklist `unconfirmed`.
- **Deterministic numbering:** `acceptance_number_sequences` model matches migration `c7d41f2b9a10`. Number allocation uses one atomic `UPDATE ... RETURNING`; unique `(project_id, kind)` and request/record number constraints protect against duplicates. Supports `never|yearly|monthly`, `prefix`, `start_number`, `width`, `date_format`, `period_key`.
- **Participant library:** CRUD for `acceptance_participant_profiles`; PYC stores profile ids plus name/organization snapshots. BBNT prefill uses the PYC's selected profiles; it never invents names or signatures.
- **BBNT reuse/stale/revision/snapshot:** creation reuses PYC project/work item/location/date/time/daily report/confirmed photos/technical document metadata. It stores `request_updated_at` and a frozen `request_snapshot_json` of printable PYC fields, returns `stale=true` + warning after PYC edits, and never mutates the old record. Preview/export/reused data for an issued record use the snapshot, not the live PYC. Records created before the snapshot column fall back to the current PYC. `POST .../revisions` copies data into `revision+1`, `supersedes_id`, `status=draft`, `result=null`, checklist `unconfirmed`, and freezes the current PYC; the previous record stays unchanged.
- **Preview + history:** `GET .../preview` returns the exact template cell mapping without writing files; `GET /projects/{p}/work-items/{id}/acceptance-history` returns PYC/BBNT number, status, revision and result.
- **Frontend:** participant library manager, profile selection in PYC, preview panel, stale warning, BBNT revision action, numbering configuration panel (PYC/BBNT prefix/start/width/reset/date format + next number), and work-item acceptance-history panel with links to open PYC/BBNT. Mobile-first stacked layout; no auto-confirmation and no AI calls.

### V2 APIs

- `GET /projects/{p}/acceptance-numbering`
- `PUT /projects/{p}/acceptance-numbering/{pyc|bbnt}`
- `GET/POST /projects/{p}/acceptance-participants`
- `GET/PATCH/DELETE /projects/{p}/acceptance-participants/{id}`
- `GET /projects/{p}/acceptance-requests/{id}/preview`
- `GET /projects/{p}/acceptance-records/{id}/preview`
- `POST /projects/{p}/acceptance-records/{id}/revisions`
- `GET /projects/{p}/work-items/{id}/acceptance-history`

### V2 schema alignment

- Models mirror migrations `c7d41f2b9a10` + `d8e52a3c4b21`: `acceptance_number_sequences`, `acceptance_participant_profiles`, request `revision` + profile ids, record `number`/`request_updated_at`/`request_snapshot_json`/`revision`/`supersedes_id`, unique `(request_id, revision)` and unique `(project_id, number)`.
- `RequestIn.number` is optional; blank triggers server-side allocation. `RecordIn.number` is optional; if no BBNT numbering config exists, the record defaults to the PYC number.
- `RecordOut` adds `number`, `revision`, `supersedes_id`, `request_updated_at`, `stale`, `stale_warning`, `reused`.

### V2 tests

New files: `test_ai_separation.py`, `test_numbering.py`, `test_participants.py`, `test_reuse_revision.py`, `test_preview_history.py`, `test_addendum_models.py`.
AI boundary tests include `test_deepseek_page_extraction_poc_is_not_imported_or_invoked` (static scan + fake module that raises).
Snapshot test: confirmed BBNT preview/export keeps the old location after PYC edit; revision 2 previews the new location.

Result:
- `cd backend && DATABASE_URL="sqlite:////tmp/opencode/acceptance-r4-$$.db" ../.venv/bin/python -m pytest tests/acceptance -q` → **67 passed**.
- Acceptance feature TypeScript check → **exit 0**.
- Full frontend build `cd frontend && npm run build` → **exit 0**.
- Full backend gate remains coordinator-owned.

### V2 unresolved

1. Shared migrations `c7d41f2b9a10` + `d8e52a3c4b21` are coordinator-owned and not edited here; any future schema change must update both migrations and these models.
2. Records created before `request_snapshot_json` existed deliberately fall back to the live PYC. A data backfill is a coordinator decision if legacy freeze is required.
3. The canonical template snapshot can drift; refresh remains coordinator-owned.
4. PDF tests skip if LibreOffice is absent; clear-error path is always tested.
5. Full backend suite remains coordinator-owned; acceptance tests alone were run here.

## Scope implemented

- Project-scoped PYC drafts (`acceptance_requests`): create, list, get, patch, submit-ready validation, duplicate-number protection.
- Project-scoped BBNT drafts (`acceptance_records`): one record per PYC, participants (max 6), explicit tri-state checklist (`yes` / `no` / `unconfirmed`), quality/compliance fields, draft editing.
- Human-only confirmation endpoint:
  - Requires a real user id (no AI/system actor).
  - Requires the confirmer role through `require_confirmer` (shared core resolves admin override; currently project managers).
  - Rejects confirmation while any checklist item is `unconfirmed`, or while `design_compliance` / `technical_compliance` is unset.
  - Rejects `approved` when either quality field is `no`; `conditional` / `rejected` require a conclusion note.
  - Writes an audit row with actor, result and timestamp; a confirmed BBNT can no longer be edited or re-confirmed.
- Excel export:
  - Copies the original workbook byte-for-byte and edits only worksheet XML cells that receive validated values.
  - Preserves drawings/logos, media, printer settings, styles, themes, merged cells, row/column sizing, hidden-sheet structure.
  - Removes the stale `xl/calcChain.xml` + relationship/override and sets `fullCalcOnLoad="1"` so Excel recalculates.
  - Scrubs old personnel and old approval values from hidden `PYC (2)` and `BB LM bt`.
  - A PYC export resets the companion `BBNT` sheet to a blank safe state (no old personnel, signatures, checklist ticks or approval conclusion).
  - A BBNT export is allowed only after human confirmation.
  - Source workbook is never opened for writing; export refuses to overwrite the template.
- PDF export (`format=pdf`) for both PYC and BBNT:
  - Runs the same validated-workbook pipeline first, then converts that workbook with LibreOffice headless.
  - Keeps the validated `.xlsx` intermediate on disk and records its path/hash in export metadata.
  - Preserves the original template; conversion never writes to the source workbook.
  - Returns `503 pdf_converter_unavailable` with an actionable message when LibreOffice/`soffice` is missing or `ACCEPTANCE_LIBREOFFICE` is invalid.
  - Conversion timeout/failure returns `500` with `pdf_conversion_timeout` / `pdf_conversion_failed`.
- `work_item_id` ownership validation against the shared `WorkItem` table (same-project only).
- Optional `daily_report_id` on PYC, validated against the site `DailyReport` table (same-project only).
- Read-only linked daily report endpoint + PYC/BBNT UI summary. Linking never changes report data and never confirms acceptance.
- Typed checklist evidence validation:
  - bare `<photo_id>` or `photo:<photo_id>` → project-owned `SitePhoto` with a human-confirmed caption or user-selected category.
  - `document:<document_id>` → project-owned Engineering AI `SourceDocument`.
  - `page:<page_id>` → project-owned Engineering AI `DocumentPage`.
  - `page:<document_id>:<page_number>` or `page:<document_id>#<page_number>` → resolved page in a project-owned source document.
  - Arbitrary unresolved IDs and unknown `type:` prefixes are rejected.
- Export history + download endpoints, including PYC exports generated from a BBNT record.
- Frontend acceptance feature: PYC form, BBNT editor, participants editor, tri-state checklist, human confirmation dialog, Excel/PDF export/download UI.

## Files changed

Backend:
- `backend/app/acceptance/__init__.py`
- `backend/app/acceptance/dependencies.py`
- `backend/app/acceptance/errors.py`
- `backend/app/acceptance/models.py`
- `backend/app/acceptance/router.py`
- `backend/app/acceptance/schemas.py`
- `backend/app/acceptance/service.py`
- `backend/app/acceptance/template.py`
- `backend/tests/acceptance/conftest.py`
- `backend/tests/acceptance/test_exports.py`
- `backend/tests/acceptance/test_records.py`
- `backend/tests/acceptance/test_requests.py`
- `backend/tests/acceptance/test_template.py`
- `backend/tests/acceptance/test_ai_separation.py`
- `backend/tests/acceptance/test_numbering.py`
- `backend/tests/acceptance/test_participants.py`
- `backend/tests/acceptance/test_reuse_revision.py`
- `backend/tests/acceptance/test_preview_history.py`
- `backend/tests/acceptance/test_addendum_models.py`

Frontend:
- `frontend/src/features/acceptance/index.ts`
- `frontend/src/features/acceptance/types.ts`
- `frontend/src/features/acceptance/lib/api.ts`
- `frontend/src/features/acceptance/components/TriStateChecklist.tsx`
- `frontend/src/features/acceptance/components/ParticipantsEditor.tsx`
- `frontend/src/features/acceptance/components/RequestForm.tsx`
- `frontend/src/features/acceptance/components/ConfirmDialog.tsx`
- `frontend/src/features/acceptance/components/ParticipantLibrary.tsx`
- `frontend/src/features/acceptance/components/NumberingPanel.tsx`
- `frontend/src/features/acceptance/components/AcceptanceHistoryPanel.tsx`
- `frontend/src/features/acceptance/pages/AcceptancePage.tsx`

Report:
- `docs/agent-reports/acceptance.md`

## APIs implemented (under `/api/v1`)

- `POST /projects/{p}/acceptance-requests`
- `GET /projects/{p}/acceptance-requests`
- `GET /projects/{p}/acceptance-requests/{id}`
- `GET /projects/{p}/acceptance-requests/{id}/daily-report`
- `PATCH /projects/{p}/acceptance-requests/{id}`
- `POST /projects/{p}/acceptance-requests/{id}/exports`
- `GET /projects/{p}/acceptance-requests/{id}/exports`
- `POST /projects/{p}/acceptance-records`
- `GET /projects/{p}/acceptance-records?request_id=...`
- `GET /projects/{p}/acceptance-records/{id}`
- `PATCH /projects/{p}/acceptance-records/{id}`
- `POST /projects/{p}/acceptance-records/{id}/confirm`
- `POST /projects/{p}/acceptance-records/{id}/exports`
- `GET /projects/{p}/acceptance-records/{id}/exports`
- `GET /projects/{p}/acceptance-exports?kind=...`
- `GET /projects/{p}/acceptance-exports/{id}/download`

All module errors return `{detail, code}`. Contract codes include `request_not_found`, `record_not_found`, `record_exists`, `record_not_confirmed`, `record_already_confirmed`, `record_confirmed`, `human_required`, `checklist_required`, `checklist_unconfirmed`, `design_compliance_required`, `technical_compliance_required`, `result_inconsistent`, `conclusion_note_required`, `work_item_not_found`, `daily_report_not_found`, `daily_report_unavailable`, `evidence_photo_not_found`, `evidence_photo_unconfirmed`, `evidence_document_not_found`, `evidence_page_not_found`, `evidence_ref_invalid`, `pdf_converter_unavailable`, `pdf_conversion_timeout`, `pdf_conversion_failed`.

Export accepts `format=xlsx|pdf`; both formats use the copied validated workbook. PDF conversion uses LibreOffice headless when available.

## Models needed / shared integration

Module-local tables (deliberately prefixed to avoid collisions):
- `AcceptanceRequest`
- `AcceptanceRecord`
- `AcceptanceParticipant`
- `AcceptanceChecklist`
- `AcceptanceGeneratedDocument`
- `AcceptanceAuditLog`

Shared-core dependencies:
- Auth/user (`get_current_user`), project membership/role (`require_project_member`, `require_project_role`), DB session (`get_db`) and `Base`.
- Shared `GeneratedDocument` / `AuditLog` should replace `AcceptanceGeneratedDocument` / `AcceptanceAuditLog` once their fields are aligned.
- Migrations for the module-local tables, or a mapping of the Pydantic contracts onto existing shared ORM models.

## Exact schema changes (V1/V2 integration)

- `acceptance_requests.daily_report_id`: new nullable `String(36)` column, indexed. No FK is declared because site reports are module-local.
- `RequestIn.daily_report_id: Optional[str]` (create payload).
- `RequestUpdate.daily_report_id: Optional[str]` (patch payload; `null` clears the link).
- `RequestOut.daily_report_id: Optional[str]`.
- New `DailyReportLinkOut`: `id`, `project_id`, `report_date`, `status`, `notes`.
- `ChecklistIn.evidence_refs` remains `List[str]`; values are now validated as documented typed refs. No database column change.
- New route: `GET /projects/{p}/acceptance-requests/{id}/daily-report` → `DailyReportLinkOut | null`.
- New error codes: `daily_report_not_found`, `daily_report_unavailable`, `evidence_document_not_found`, `evidence_page_not_found`, `evidence_ref_invalid`.

## Export cell mapping

PYC validated cells: `C1`, `C2`, `C3`, `B6`, `F6`, `B7`, `B10`, `D10`, `E10`, `H10`, `I10`, `K10`, `D14`, `D15`, `D16`, `A20`, `E20`, `H20`.

BBNT validated cells: `B1`, `B2`, `B3`, `B5`, `D5`, `B6`, `A8`, `A11`, `A14`; participants `B9/D9` through `B16/D16`; times `B18`, `B19`, `D18`, `D19`; checklist ticks `D24:E30`; quality `A32`, `A33`, `A34`; conclusion `A36`, `A37`; signatures `A43`.

Scrubbed hidden sheets:
- `PYC (2)`: `C1`, `C2`, `C3`, `B6`, `F6`, `B7`, `B10`, `D10`, `E10`, `H10`, `I10`, `K10`, `D14`, `D15`, `D16`, `A20`, `E20`, `H20`.
- `BB LM bt`: `A12`, `A13`, `A15`, `A16`.

PDF export applies the same mapping first, then converts that copied workbook. PDFs therefore contain only validated cells and the same scrubbed hidden sheets as the XLSX artifact.

## Tests

`backend/tests/acceptance` has 45 tests:
- Requests: create/list/get, duplicate number, project scoping, submit validation, schema rejection, `work_item_id` same-project ownership on create/update, `daily_report_id` same-project validation, linked daily-report read/null responses.
- Records: explicit `unconfirmed` seed, duplicate prevention, checklist resolution required, human/role gate, confirmation audit fields, approved inconsistency, conditional reason, confirmed immutability, checklist replacement, photo project/confirmation checks, typed document/page refs, malformed/unresolved ref rejection.
- Exports:
  - PYC replaces only validated cells and preserves formatting/package parts; output never has a calcChain, and a source calcChain is asserted removed only when present.
  - Missing fields leave no old defaults.
  - BBNT export requires confirmation.
  - Confirmed BBNT replaces personnel/ticks/conclusions and scrubs hidden sheets.
  - Record can export PYC + history.
  - PYC-only export resets BBNT to a blank safe state.
  - PDF export creates a real PDF from the validated workbook, retains workbook metadata, and leaves the template untouched.
  - Confirmed BBNT PDF export works; unconfirmed BBNT PDF export returns `409`.
  - Missing LibreOffice returns `503 pdf_converter_unavailable` without persisting a document.
  - Missing/invalid template errors.
- Template: style-preserving cell replace/clear/insert, sorted row insert, template validation, canonical real-template validation, CWD-independent canonical default path, clear `template_missing` error when the canonical default is absent, and a fixture guard proving tests use the repo canonical copy rather than `~/Downloads`.

Results:
- `cd backend && DATABASE_URL="sqlite:////tmp/opencode/acceptance-r4-$$.db" ../.venv/bin/python -m pytest tests/acceptance -q` → `67 passed`.
- Acceptance feature TypeScript check → exit `0`:
  `npx tsc --noEmit --jsx react-jsx --target ES2022 --module ESNext --moduleResolution Bundler --lib ES2022,DOM,DOM.Iterable --strict --skipLibCheck --isolatedModules src/features/acceptance/index.ts`
- Full backend suite and full frontend build are run by the coordinator after all module agents finish; this agent did not run them.
- Full frontend build was previously blocked outside this boundary:
  `src/features/site/pages/SiteReportPage.tsx(73,30): error TS2741: Property 'site_notes' is missing ...`
  The remaining failure belongs to the site module.

Template isolation:
- Canonical template: `data/templates/acceptance-original.xlsx` (repo-owned). Resolved from the package location via `Path(__file__).resolve().parents[3]`, so it works from any CWD. Size `180112` bytes, SHA-256 `d5dd46880dc8572e3986e8fcaacea332354c6b59c714b8f19d2a1786df3ffc90`.
- Previous canonical snapshot archived at `data/templates/archive/acceptance-original-e204c40603fc75219e0690ce548d176b64b1b08c27df10d2629ab7c70f8ee382.xlsx`, SHA-256 `e204c40603fc75219e0690ce548d176b64b1b08c27df10d2629ab7c70f8ee382`.
- `backend/tests/acceptance/conftest.py` copies the canonical workbook into each test's `tmp_path` and sets `ACCEPTANCE_TEMPLATE` to that copy. If the canonical file is absent it builds the synthetic workbook instead. Tests never read the user's workbook in `~/Downloads`, so an open/edited LibreOffice file cannot change test results.
- The canonical workbook currently has no `xl/calcChain.xml` (it was saved by LibreOffice). The export test now always asserts the output has no calcChain, and only asserts that the source lost calcChain when the source actually contained it.

## Dependencies

- Backend: FastAPI, SQLAlchemy, Pydantic v2, pytest, httpx. XLSX export uses only Python stdlib (`zipfile`, XML string editing) — no `openpyxl` at runtime.
- PDF export: LibreOffice headless (`libreoffice` or `soffice`) plus `subprocess`; not a Python package dependency. Configure with `ACCEPTANCE_LIBREOFFICE`; timeout via `ACCEPTANCE_PDF_TIMEOUT` (default 120s). Page filtering after conversion requires **PyMuPDF** (`pymupdf`).
- Frontend: React 19, TypeScript, Vite, Tailwind. No additional packages added.
- Test-only: `openpyxl`, Pillow (for workbook inspection/synthetic fixture). PDF tests skip if LibreOffice is absent.

## Vòng 8 — xoá PYC, ảnh xem trước, PDF BBNT một trang

- **Xoá PYC:** thêm `DELETE /projects/{p}/acceptance-requests/{id}` (editor). PYC không có BBNT xoá trực tiếp; PYC có BBNT trả `409 request_has_records` trừ khi `?force=true`. Khi force, BBNT liên quan, participants/checklist và lịch sử export được xoá; file export trong thư mục riêng của source cũng bị dọn. Audit ghi lại `records_deleted` và `forced`.
- **Ảnh xem trước PYC:** thêm `GET /projects/{p}/acceptance-requests/{id}/preview-image` trả PNG. Endpoint dựng workbook tạm bằng đúng `copy_and_fill`, convert LibreOffice, lọc trang PYC, render PNG 150 dpi; không tạo bản ghi export/history. Frontend fetch có Bearer token và hiển thị `<img>` thay cho JSON; BBNT preview vẫn giữ dạng cells.
- **PDF BBNT:** `_select_pdf_pages(kind="bbnt")` chỉ giữ trang BBNT và các trang continuation, không còn kèm trang PYC.
- **E10:** `content + " tại " + subject`; nếu subject trống thì chỉ in content.

Files: `backend/app/acceptance/service.py`, `backend/app/acceptance/router.py`, `frontend/src/features/acceptance/lib/api.ts`, `frontend/src/features/acceptance/pages/AcceptancePage.tsx`, `backend/tests/acceptance/test_requests.py`, `backend/tests/acceptance/test_exports.py`.

## Unresolved issues / requests to Codex

1. The integrated Alembic chain must add `acceptance_requests.daily_report_id` (nullable indexed `String(36)`); this agent did not edit shared migrations.
2. Reconcile `AcceptanceGeneratedDocument` / `AcceptanceAuditLog` with shared `GeneratedDocument` / `AuditLog` if the integration note above is not yet reflected in the deployed schema.
3. Add an explicit shared permission grant for "người được cấp quyền nghiệm thu" if project-manager-only confirmation is too narrow.
4. Add a shared `{detail, code}` exception handler for non-acceptance errors.
5. `work_item_id`, `daily_report_id`, photo, and Engineering AI evidence checks import shared/site module models lazily. If those modules are unavailable in an isolated deployment, validation is skipped rather than guessing.
6. Evidence clients must use the supported typed forms (`photo:`, `document:`, `page:`) or a valid bare photo id. Opaque refs are no longer accepted.
7. PDF output depends on the server's LibreOffice version and installed fonts. The validated intermediate `.xlsx` is retained on disk and recorded in export metadata, but there is no separate API download route for it.
8. No component test runner is configured (no jsdom/@testing-library); acceptance verification is the feature TypeScript check plus full `npm run build`, both passing.
9. PDF integration tests skip automatically when LibreOffice is not installed; the clear-error path (`pdf_converter_unavailable`) is always tested.
10. The canonical template `data/templates/acceptance-original.xlsx` is a repo snapshot and can drift from the user's latest workbook (for example the new `DM` rows 38–39 and YC number 34). Refreshing it requires closing LibreOffice and running `scripts/refresh_acceptance_template.sh`; that script is coordinator-owned. Tests intentionally run against the canonical snapshot, not the live `~/Downloads` file.

## Run instructions

1. Install backend deps in a venv, e.g.:
   - `uv venv .venv`
   - `uv pip install fastapi sqlalchemy pytest httpx openpyxl pillow`
2. Run acceptance tests:
   - `cd backend`
   - `DATABASE_URL="sqlite:////tmp/opencode/acceptance-r4-$$.db" ../.venv/bin/python -m pytest tests/acceptance -q`
3. Run the full backend suite (coordinator gate):
   - `cd backend`
   - `DATABASE_URL="sqlite:////tmp/opencode/acceptance-full-$$.db" ../.venv/bin/python -m pytest tests -q`
4. Frontend checks:
   - `cd frontend`
   - Acceptance feature typecheck:
     `npx tsc --noEmit --jsx react-jsx --target ES2022 --module ESNext --moduleResolution Bundler --lib ES2022,DOM,DOM.Iterable --strict --skipLibCheck --isolatedModules src/features/acceptance/index.ts`
   - Full build: `npm run build`
5. Runtime template selection:
   - Default: `data/templates/acceptance-original.xlsx`, resolved from the package location (works from any working directory).
   - Override with `ACCEPTANCE_TEMPLATE=/path/to/template.xlsx`
   - Missing default → `template_missing` error; there is no silent fallback to `~/Downloads`.
   - Export output: `ACCEPTANCE_STORAGE` (default `/tmp/opencode/acceptance-storage`)
6. PDF conversion:
   - Install LibreOffice with headless support (`libreoffice` or `soffice` on `PATH`).
   - Or set `ACCEPTANCE_LIBREOFFICE=/path/to/libreoffice`
   - Optional timeout: `ACCEPTANCE_PDF_TIMEOUT=120`
