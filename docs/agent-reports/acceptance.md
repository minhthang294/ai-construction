# Acceptance (PYC/BBNT) Agent Report

## Codex integration update — 11/11/2026

Acceptance router and frontend page are mounted. Export history and audit use the shared `generated_documents` and `audit_logs` tables; the integrated Alembic migration omits the former module-local duplicate tables. PYC creation fills missing common project fields from `Project`; downloads are limited to acceptance kinds and the project's private export directory. Remaining integration items are recorded in the "Unresolved issues" section below.

## Vòng 2 — Addendum acceptance (11/11/2026)

- **AI separation:** `backend/app/acceptance/` contains no LLM/Vision/Embedding provider import or call. `test_ai_separation.py` statically scans the package and monkeypatches `provider_from_env`, `vision_from_env`, `embeddings_from_env` to raise; PYC/BBNT create + XLSX/PDF export still succeed. A new record has `result=null` and checklist `unconfirmed`.
- **Deterministic numbering:** `acceptance_number_sequences` model matches migration `c7d41f2b9a10`. Number allocation uses one atomic `UPDATE ... RETURNING`; unique `(project_id, kind)` and request/record number constraints protect against duplicates. Supports `never|yearly|monthly`, `prefix`, `start_number`, `width`, `date_format`, `period_key`.
- **Participant library:** CRUD for `acceptance_participant_profiles`; PYC stores profile ids plus name/organization snapshots. BBNT prefill uses the PYC's selected profiles; it never invents names or signatures.
- **BBNT reuse/stale/revision/snapshot:** creation reuses PYC project/work item/location/date/time/daily report/confirmed photos/technical document metadata. It stores `request_updated_at` and a frozen `request_snapshot_json` of printable PYC fields, returns `stale=true` + warning after PYC edits, and never mutates the old record. Preview/export/reused data for an issued record use the snapshot, not the live PYC. Records created before the snapshot column fall back to the current PYC. `POST .../revisions` copies data into `revision+1`, `supersedes_id`, `status=draft`, `result=null`, checklist `unconfirmed`, and freezes the current PYC; the previous record stays unchanged.
- **Preview + history:** `GET .../preview` returns the exact template cell mapping without writing files; `GET /projects/{p}/work-items/{id}/acceptance-history` returns PYC/BBNT number, status, revision and result.
- **Frontend:** participant library manager, profile selection in PYC, preview panel, stale warning, BBNT revision action, responsive existing form.

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
Snapshot test: confirmed BBNT preview/export keeps the old location after PYC edit; revision 2 previews the new location.

Result:
- `cd backend && DATABASE_URL="sqlite:////tmp/opencode/acceptance-v2-$$.db" ../.venv/bin/python -m pytest tests/acceptance -q` → **66 passed**.
- Acceptance feature TypeScript check → **exit 0**.
- Full backend/frontend gate remains coordinator-owned.

### V2 unresolved

1. Shared migrations `c7d41f2b9a10` + `d8e52a3c4b21` are coordinator-owned and not edited here; any future schema change must update both migrations and these models.
2. Records created before `request_snapshot_json` existed deliberately fall back to the live PYC. A data backfill is a coordinator decision if legacy freeze is required.
3. Numbering config UI is not added; API is complete and UI auto-numbers with defaults/config.
4. Work-item history API is implemented; dedicated history UI is not added.
5. The canonical template snapshot can drift; refresh remains coordinator-owned.
6. PDF tests skip if LibreOffice is absent; clear-error path is always tested.

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
- `cd backend && DATABASE_URL="sqlite:////tmp/opencode/acceptance-v2-$$.db" ../.venv/bin/python -m pytest tests/acceptance -q` → `66 passed`.
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
- PDF export: LibreOffice headless (`libreoffice` or `soffice`) plus `subprocess`; not a Python package dependency. Configure with `ACCEPTANCE_LIBREOFFICE`; timeout via `ACCEPTANCE_PDF_TIMEOUT` (default 120s).
- Frontend: React 19, TypeScript, Vite, Tailwind. No additional packages added.
- Test-only: `openpyxl`, Pillow (for workbook inspection/synthetic fixture). PDF tests skip if LibreOffice is absent.

## Unresolved issues / requests to Codex

1. The integrated Alembic chain must add `acceptance_requests.daily_report_id` (nullable indexed `String(36)`); this agent did not edit shared migrations.
2. Reconcile `AcceptanceGeneratedDocument` / `AcceptanceAuditLog` with shared `GeneratedDocument` / `AuditLog` if the integration note above is not yet reflected in the deployed schema.
3. Add an explicit shared permission grant for "người được cấp quyền nghiệm thu" if project-manager-only confirmation is too narrow.
4. Add a shared `{detail, code}` exception handler for non-acceptance errors.
5. `work_item_id`, `daily_report_id`, photo, and Engineering AI evidence checks import shared/site module models lazily. If those modules are unavailable in an isolated deployment, validation is skipped rather than guessing.
6. Evidence clients must use the supported typed forms (`photo:`, `document:`, `page:`) or a valid bare photo id. Opaque refs are no longer accepted.
7. PDF output depends on the server's LibreOffice version and installed fonts. The validated intermediate `.xlsx` is retained on disk and recorded in export metadata, but there is no separate API download route for it.
8. No component test runner is configured (no jsdom/@testing-library); acceptance verification is TypeScript compilation. At the time of this run the full `npm run build` was reported blocked by the site module's missing `site_notes` field in `SiteReportPage.tsx`, outside the acceptance edit boundary; re-check after the site agent's changes.
9. PDF integration tests skip automatically when LibreOffice is not installed; the clear-error path (`pdf_converter_unavailable`) is always tested.
10. The canonical template `data/templates/acceptance-original.xlsx` is a repo snapshot and can drift from the user's latest workbook (for example the new `DM` rows 38–39 and YC number 34). Refreshing it requires closing LibreOffice and running `scripts/refresh_acceptance_template.sh`; that script is coordinator-owned. Tests intentionally run against the canonical snapshot, not the live `~/Downloads` file.

## Run instructions

1. Install backend deps in a venv, e.g.:
   - `uv venv .venv`
   - `uv pip install fastapi sqlalchemy pytest httpx openpyxl pillow`
2. Run acceptance tests:
   - `cd backend`
   - `DATABASE_URL="sqlite:////tmp/opencode/acceptance-v2-$$.db" ../.venv/bin/python -m pytest tests/acceptance -q`
3. Run the full backend suite (coordinator gate):
   - `cd backend`
   - `DATABASE_URL="sqlite:////tmp/opencode/acceptance-full-$$.db" ../.venv/bin/python -m pytest tests -q`
4. Frontend checks:
   - `cd frontend`
   - Acceptance feature typecheck:
     `npx tsc --noEmit --jsx react-jsx --target ES2022 --module ESNext --moduleResolution Bundler --lib ES2022,DOM,DOM.Iterable --strict --skipLibCheck --isolatedModules src/features/acceptance/index.ts`
   - Full build: `npm run build` (re-check after the site module's type fix; it was blocked when this module ran)
5. Runtime template selection:
   - Default: `data/templates/acceptance-original.xlsx`, resolved from the package location (works from any working directory).
   - Override with `ACCEPTANCE_TEMPLATE=/path/to/template.xlsx`
   - Missing default → `template_missing` error; there is no silent fallback to `~/Downloads`.
   - Export output: `ACCEPTANCE_STORAGE` (default `/tmp/opencode/acceptance-storage`)
6. PDF conversion:
   - Install LibreOffice with headless support (`libreoffice` or `soffice` on `PATH`).
   - Or set `ACCEPTANCE_LIBREOFFICE=/path/to/libreoffice`
   - Optional timeout: `ACCEPTANCE_PDF_TIMEOUT=120`
