# Engineering AI Agent Report

## 2026-11-23 — UI fix wave 1 (Hỏi AI + Nghiệm thu quick wins)

Implemented the owner-approved quick wins from
`docs/agent-reports/ux-audit-ai-acceptance.md` without touching
`frontend/src/app`, `frontend/src/features/site` or `frontend/src/style.css`.

Hỏi AI:
- Hero reduced to one title row; the duplicate “Hỏi đáp có citation” intro and
  duplicated chat header copy were removed. Suggestions scroll in one compact
  row on phones and wrap on desktop, so the composer and chips are on the first
  390 px screen (`EngineeringAIPage.tsx`, `ChatPanel.tsx`,
  `QuestionSuggestions.tsx`).
- Suggestions are fetched once by the page and passed down; the empty-source
  banner now distinguishes: documents → unverified-extraction note; components/
  progress only → “vẫn trả lời từ database cấu kiện và tiến độ”; neither →
  the refusal warning. No more “every question will be refused” when DB data
  exists.
- “citation” is now “nguồn/nguồn trích dẫn” in field-facing copy.
- Rename/Delete are hidden until a conversation exists.
- Chips, citation actions, history actions and retry are ≥44 px with 14 px text;
  citation metadata/badges were enlarged.

Nghiệm thu:
- Vietnamese status labels and a colour legend replace raw
  draft/submitted/confirmed/revision (`lib/statusLabels.ts` + test); request,
  record, result, revision and delete/revision prompts all use them.
- Numbering configuration and participant library moved into a closed-by-default
  `Cài đặt nghiệm thu` `<details>`; the history panel stays outside.
- Empty PYC card replaced with one line under “+ Tạo PYC nháp”.
- PYC and BBNT forms have a sticky bottom action bar with inline success/error;
  BBNT export/preview/revision moved into a compact `Xuất hồ sơ & xem trước`
  disclosure so the bar stays small on phones.
- `recordsByRequest` is precomputed with `useMemo` instead of `records.find` in
  each row.
- Tabs use `aria-pressed`; the confirm dialog traps focus, focuses on open,
  closes on Escape and restores focus; `MenuButton` has `aria-haspopup`.
- Larger text/touch targets for history, participant library, numbering inputs
  and preview close.

Files: engineering-ai page/chat/citation/suggestion components;
acceptance page, RequestForm, ParticipantsEditor, ParticipantLibrary,
NumberingPanel, AcceptanceHistoryPanel, TriStateChecklist, ConfirmDialog,
`lib/statusLabels.ts` (+ test); `frontend/src/ui/MenuButton.tsx`.

Verification (temp DB/storage):
```bash
cd backend
DATABASE_URL=sqlite:///<tmp>/app.db SITE_REPORT_STORAGE=<tmp>/site \
ENGINEERING_AI_STORAGE=<tmp>/engineering ACCEPTANCE_STORAGE=<tmp>/acceptance \
../.venv/Scripts/python -m pytest tests/engineering_ai tests/acceptance -q
# 223 passed, 6 skipped, 0 failed

cd frontend && npm test          # 34 files, 210 passed
cd frontend && npm run build     # tsc -b + vite build OK
```

Unresolved: the app shell still owns the component-navigation listener for
`engineering-ai:open-component`; PYC success appears as a sticky status after
the editor closes (the editor unmounts, so the message cannot live inside its
bar). Large PYC lists remain unpaginated.

## 2026-11-23 — fix: per-component stages, action-verb matching, recent-usage suggestion

Real-data bug fixed without changing the API shape (additive only):

- Candidates now come only from each component's own `component_stages` joined
  to `component_stage_definitions`. Project-wide definitions that are not
  attached can never appear (covered by a seeded unattached `999 mm` definition).
- Work is matched against the START of the stage name (action verb), not a
  substring. `đục` matches `Đục ...`; `Tẩy gỉ ... vùng đục` and
  `Vệ sinh ... sau khi đục` no longer match.
- Refinement: phrases with extra verbs (`đục om vỡ`, `đục hà bám`, `đục lỗ`)
  keep only own stages containing those tokens; bare `đục`/`đục bê tông` prefer
  the om-vỡ variant.
- Suggested default stage = the stage name most recently used in non-voided
  events: the component's own latest event first, else the project-wide latest
  for the same component type + verb, mapped back to an own stage by name.
  A suggestion is pre-selected (`stage_definition_id` on the item and in
  `apply.stage_definition_id`) and listed first. A `multiple_stage` question is
  produced only when the component's own refined candidates are still >1.
- `completed_earlier` is evaluated only for the selected/suggested stage, and
  its options/event ids refer to that stage.
- Duplicate option labels are disambiguated with the stage code when two own
  definitions share a name.
- Fixture rebuilt to mirror real structure: each pile owns the four stages
  (`Đục hà bám 10 mm`, `Đục bê tông om vỡ`, `Tẩy gỉ ... vùng đục`,
  `Vệ sinh ... sau khi đục`); each beam owns 20/50/70/100 mm om-vỡ stages; plus
  unattached definitions for other groups. Recent events drive 50 mm for
  F-66-67 and 70 mm for A-B-153.

Real-copy check (read-only copy, project `DAP - PD1 da duyet`, message
`Cọc đục ngày 23/11 / I69,70, H67 / Dầm f66-67, a-b153`):
- I69, I70 → `1d07eccd-…` "Đục bê tông om vỡ dày trung bình t", one candidate,
  no `multiple_stage` question.
- H67 → unknown code question + `unknown_codes=["H67"]`.
- F-66-67 → selected `2d0769f3-…` "…50 mm"; own candidates 50 + 70 → compact
  `multiple_stage` with 50 first; `completed_earlier` for the 22/11 50 mm event.
- A-B-153 → selected `fdd0ba71-…` "…70 mm"; own candidate only → no
  `multiple_stage`; `outside_scope` (Bunke – PD1 vs Cầu chính – PD2);
  `completed_earlier` for its 22/11 70 mm event.
- No writes were made; the copy was opened with SQLite `mode=ro`.

Tests: golden now asserts own-stage candidates, unattached definitions excluded,
F-66-67 50 / A-B-153 70 preselect, 4 mm options with suggestion first,
per-item earlier events. Added duplicate-name label uniqueness test. Contract
JSON example regenerated from the new golden fixture.

Verification (temp DB/storage):
```bash
cd backend
DATABASE_URL=sqlite:///<tmp>/app.db SITE_REPORT_STORAGE=<tmp>/site \
ENGINEERING_AI_STORAGE=<tmp>/engineering ACCEPTANCE_STORAGE=<tmp>/acceptance \
../.venv/Scripts/python -m pytest tests/engineering_ai -q   # 121 passed
../.venv/Scripts/python -m pytest tests -q                  # 355 passed, 6 skipped, 0 failed

cd frontend && npm test          # 207 passed (33 files)
cd frontend && npm run build     # OK
```

Frontend: no change required — `frontend/src/features/site/lib/progressPaste.ts`
already reads item `stage_definition_id`, `stage_candidates`, `apply.event_ids`
and question `codes`.

Unresolved: if no own stage starts with the verb, no candidate is returned and
the line warns for manual choice; the suggestion cannot use a definition that is
not attached to the component. When several own definitions share the same name,
labels include the stage code but the UI still shows a long list.

## 2026-11-23 — wave 3b: progress-parse output ready for the paste UI

`POST /ai/progress-parse` now returns everything the paste-message UI needs
without a second lookup; it stays read-only.

Per item (`ProgressParseItemOut`):
- `stage_definition_id`: set when the line has exactly one candidate stage.
- `stage_candidates`: the candidate list when there is more than one (empty
  otherwise).
- `earlier_events`: `[{event_id, event_date, status}]` from the earlier-COMPLETED
  check (newest first); same events feed the question.
- `in_batch`: `true` when the component belongs to the requested
  `construction_batch_components` batch.
- Existing `raw/code/component_id/zone/segment/status_guess` unchanged.

Every question now has `codes` (target canonical codes) and `apply`:
- duplicate: `{"action":"dedupe","codes":[...]}`
- completed earlier:
  `{"action":"correct_earlier_to_in_progress","event_ids":[...],"codes":[...]}`
- multiple stages:
  `{"action":"set_stage","stage_definition_id":null,"codes":[...]}`; the UI
  substitutes the chosen option value (a stage-definition id)
- outside: `{"action":"skip_codes","codes":[...]}`
- unknown code: `{"action":"skip_codes","codes":[...]}`
- `đang` status: `{"action":"set_status","codes":[...]}`

Tests updated: golden message asserts per-item stage fields, the F-66-67 item's
`earlier_events`, all `in_batch=false`, every question carries `codes` + the four
`apply.action` values, plus the option values. Batch test asserts `A-B-153`
`in_batch=true` and is absent from the outside question while the two other
beams remain. Work text now drops the date word (`Cọc đục`, `Dầm đục`).

`docs/API_CONTRACTS.md` has the full request/response JSON example generated from
the seeded golden 22/11 message (29 items, 6 questions, stage ids, earlier event,
apply hints). It is validated as JSON.

Verification (temp DB/storage):
```bash
cd backend
DATABASE_URL=sqlite:///<tmp>/app.db SITE_REPORT_STORAGE=<tmp>/site \
ENGINEERING_AI_STORAGE=<tmp>/engineering ACCEPTANCE_STORAGE=<tmp>/acceptance \
../.venv/Scripts/python -m pytest tests/engineering_ai -q   # 120 passed
../.venv/Scripts/python -m pytest tests -q                  # 354 passed, 6 skipped, 0 failed
```

Unresolved: for multiple-stage questions `apply.stage_definition_id` is null on
purpose; the client must copy the selected option `value` into it before calling
the existing daily endpoint. `earlier_events` lists all earlier COMPLETED events
for the component/stage candidates, so the UI can offer per-event correction.

## 2026-11-23 — follow-up: voided events, batch-aware parse, test shim removed

- Voided progress events (`component_progress_events.voided_at`) are now excluded
  from every engineering-AI read:
  `database_chat._related_rows`/aggregate count, `suggestions._load_project`, and
  `progress_parse` event load. Chat daily/latest/pending/stage answers,
  suggestion chips and the parser's “earlier COMPLETED” question therefore
  ignore corrections.
- Tests added: a voided COMPLETED does not move chat's “latest day” or complete a
  pending stage; a voided future event does not change suggestion dates; a voided
  earlier COMPLETED does not generate a parse `completed_earlier` question.
- The temporary conftest stub for `component_progress_batches` is removed. The
  engineering test app now imports `app.site.models` so the core FK target is
  registered; tests pass without the shim.
- `progress-parse` accepts optional `batch_id` and echoes it. Components in that
  construction batch (`component_progress_events` batch semantics; read from
  `construction_batch_components`) are exempt from the outside-zone/segment
  question, while non-batch components still raise “Thi công cùng đợt / Bỏ qua”.
  A batch id from another project adds a warning and grants no exemption.
  Tested by putting `A-B-153` in a Bunke batch: it is not flagged, `F-66-67` and
  `B-D-153` still are, and `batch_id` is returned.

Files: `backend/app/engineering_ai/{database_chat.py, suggestions.py,
progress_parse.py, router.py, schemas.py}`,
`backend/tests/engineering_ai/{conftest.py, test_database_chat.py,
test_progress_parse.py}`, `docs/API_CONTRACTS.md`.

Verification (temp DB/storage):
```bash
cd backend
DATABASE_URL=sqlite:///<tmp>/app.db SITE_REPORT_STORAGE=<tmp>/site \
ENGINEERING_AI_STORAGE=<tmp>/engineering ACCEPTANCE_STORAGE=<tmp>/acceptance \
../.venv/Scripts/python -m pytest tests/engineering_ai -q
# 120 passed

../.venv/Scripts/python -m pytest tests -q
# 354 passed, 6 skipped, 0 failed
```

Unresolved: batch membership is only used to waive the outside-zone question; it
is not written into the parse items (the UI still sends the chosen batch to the
existing daily endpoint). `voided_at` filtering assumes callers never need the
correction history; reporting corrections would need a separate read.

## 2026-11-23 — wave 3a: deterministic Zalo progress parser (read-only)

New `POST /api/v1/projects/{p}/ai/progress-parse` (`progress_parse.py`) turns a
pasted field/Zalo message into a reviewed-entry draft. It only selects rows; it
never calls `add`/`commit` or the answer provider.

Request: `{text, default_date?}`. Response: `{event_date, date_source, lines[
{work_text, stage_candidates[{stage_definition_id,name,component_type}],
component_type, items[{raw, code, component_id|null, zone, segment,
status_guess}]}], questions[{id, kind, message_vi, options[{label_vi,value}]}],
unknown_codes, warnings}`.

Deterministic rules implemented:
- Dates `22/11`, `ngày 22/11`, optional year; missing year uses the year of
  `default_date` (or today), otherwise `default_date` and `date_source`.
- Pile shorthand: a bare number reuses the last letter prefix per type
  (`I49, 51,55`, `G50,65,65`, prefix also carries across consecutive lines).
- Lines starting with `Dầm` switch to beams; beam shorthand `f66-67` ->
  `F-66-67`, `a-b153` -> `A-B-153`, `b-d153` -> `B-D-153`; direct canonical
  beam codes are accepted. Matching is case-insensitive against
  `canonical_code`, `raw_code` and `component_aliases`, project-scoped.
- Work phrase (`Cọc đục`, `đục bê tông`, `đục om vỡ`) is fuzzy-matched to stage
  definitions of the matched component type.
- Questions instead of guesses: duplicate code (dedupe/replace), previous
  COMPLETED on an earlier date (add / correct previous / skip), more than one
  candidate stage (list stage options), components outside the majority
  zone/segment of the message (include/skip), unknown codes, and `đang`
  status confirmation. Default status is COMPLETED for past-tense work.
- Expected zone/segment is inferred from the majority of resolved pile items;
  no zone/segment is guessed when no pile resolves.
- No LLM fallback was wired (optional in the task): unreadable/unmatched input
  produces warnings (`cần chọn tay`, `Không đọc được mã`, missing date) and no
  invented codes.

Golden test (`test_progress_parse.py`) uses the exact 9-line message with seeded
PD2 Cầu chính piles (26 unique) and 3 Bunke beams. It asserts the date
`2026-11-22`, unique component ids 26/3, all statuses COMPLETED, and exactly the
four question kinds `duplicate_code` (G65), `completed_earlier` (F-66-67,
20/11), `multiple_stage` (3 beam chipping stages) and `outside_scope` (Bunke).
Further tests cover no DB writes, project scope + alias matching, unknown codes,
`đang` status question, `default_date`/missing date, and bare-date chat.

`database_chat.py`: a date token alone now counts as a progress question, so
`Ngày 21/11 làm gì?` answers daily progress without requiring `PD2` or the word
`tiến độ`. Existing date/segment, latest-day, pending-stage and current-stage
answers are unchanged.

Files: `backend/app/engineering_ai/{progress_parse.py (new),
database_chat.py, router.py, schemas.py}`,
`backend/tests/engineering_ai/{conftest.py, test_progress_parse.py (new),
test_database_chat.py}`, `docs/API_CONTRACTS.md` (two engineering rows).

Conftest note (resolved in the follow-up section above): the engineering test
app imports `app.site.models` so the `component_progress_events.batch_id` FK
target (`component_progress_batches`) is registered; there is no test-only stub
anymore.

Verification at the time:
```bash
cd backend
DATABASE_URL=sqlite:///<tmp>/app.db SITE_REPORT_STORAGE=<tmp>/site \
ENGINEERING_AI_STORAGE=<tmp>/engineering ACCEPTANCE_STORAGE=<tmp>/acceptance \
../.venv/Scripts/python -m pytest tests/engineering_ai -q
# 115 passed

../.venv/Scripts/python -m pytest tests -q
# 346 passed, 6 skipped, 2 failed — both outside this module and from the other
# agent's then in-progress core/site edit (drawing-map Depends bug and a
# progress-batches undo route without the editor guard). Both are fixed now:
# the follow-up run is 354 passed / 0 failed.
```

Frontend: no files changed in this wave; the endpoint is ready for the typed
client when the entry-review UI is added.

Unresolved:
- Question `options[].value` values are stable protocol strings
  (`dedupe`, `replace_code`, `add_completed`, `previous_was_in_progress`,
  `skip`, `include`, stage ids, status values); the UI must map labels to the
  existing `progress/daily-preview` and `progress/daily` payloads.
- Outside-scope detection uses design zone/segment only; the new construction
  batches (other agent) are not consulted.
- One date is parsed for the whole message; mixed-date messages need splitting.
- No LLM fallback/no provider call, by design; provider-backed review of
  unreadable lines remains future work.

## 2026-11-23 — wave 2: data-driven chat UX (suggestions, compact citations, mobile composer)

Chat (Hỏi AI) is now mobile-first and suggestion-driven from the project's real
data.

Backend:
- New read-only `GET /projects/{p}/ai/question-suggestions` (`suggestions.py`)
  builds 1-5 chips from `structural_components`, `structure_segments`,
  `component_stage_definitions`/`component_stages`, `component_progress_events`
  and design groups. Examples: `PD2 còn bao nhiêu cọc chưa đục bê tông?`,
  `Cọc F67 đang ở bước nào?`, `Tiến độ ngày 21/11?`,
  `Mở bản vẽ nhóm cọc 2 PD2`, `Công trình có bao nhiêu cọc?`. No static/OCR-era text.
  Endpoint returns `[]` when the project has no components.
- `database_chat.py` now answers progress questions before component lookup:
  daily progress by date and/or `PDn` (`Tiến độ ngày 21/11 PD2`, bare
  `21/11 PD2`, `Tiến độ ngày gần nhất?`), pending stage counts
  (`PD2 còn bao nhiêu cọc chưa đục bê tông?`) and current component stage
  (`Cọc F67 đang ở bước nào?`). Answers list stage/status/quantity with
  progress-event record-id citations and keep the "không phải nghiệm thu"
  warning. `service.ask` tries this DB path before component-fact lookup and
  falls back to the DB for component questions that extractions cannot answer.

Frontend:
- `QuestionSuggestions` fetches the endpoint and renders compact chips; the
  block is hidden once the conversation has messages.
- `CitationCard` is compact: drawing citations show version/page/drawing and a
  3-line quote plus "Xem trang"; database component rows show
  `Cấu kiện <code>` + table + record id and a "Mở cấu kiện" button.
- Database citations emit `engineering-ai:open-component` with
  `{projectId, recordId, citation}` on `window`; the app shell owns navigation
  and can listen for it. Non-component DB rows (progress events, stages) show
  the table and record id without a button.
- Composer is sticky at the bottom on mobile (`lg:static` on desktop), Enter
  sends, Shift+Enter adds a newline, send is disabled while busy, and a failed
  request keeps the question with a "Thử lại" retry that does not duplicate the
  user message.
- Conversation history collapses on mobile behind a toggle (search remains);
  desktop always shows the list.
- Added `lib/citations.ts` + test for citation display; removed the old static
  question library and its test.

Files changed: `backend/app/engineering_ai/{suggestions.py (new),
database_chat.py, service.py, router.py, schemas.py}`,
`backend/tests/engineering_ai/test_database_chat.py`,
`frontend/src/features/engineering-ai/{types.ts, lib/api.ts,
lib/citations.ts (new), lib/citations.test.ts (new),
components/QuestionSuggestions.tsx, components/CitationCard.tsx,
components/ChatPanel.tsx, pages/EngineeringAIPage.tsx}`; deleted
`frontend/src/features/engineering-ai/lib/questionSuggestions.ts` and its test.

Verification:
```bash
cd backend
DATABASE_URL=sqlite:///<tmp>/app.db SITE_REPORT_STORAGE=<tmp>/site \
ENGINEERING_AI_STORAGE=<tmp>/engineering ACCEPTANCE_STORAGE=<tmp>/acceptance \
../.venv/Scripts/python -m pytest tests -q
# 338 passed, 6 skipped, 0 failed

cd frontend && npm test   # 200 passed (32 files)
cd frontend && npm run build  # tsc -b + vite build OK
```

Unresolved:
- Component navigation is emitted as a browser CustomEvent only; the app shell
  (owned elsewhere) must add the listener/route. Until then the card still
  shows the component code, table and record id.
- Progress date parsing accepts `d/m`, `d-m` and optional year; other date
  wording (e.g. "hôm qua") is not parsed.
- Suggestions depend on existing stage definitions/progress; a project with
  components but no stages gets fewer chips.

## 2026-11-23 — chat-only module; OCR and non-chat AI removed

Owner decision applied: the module now keeps only AI chat (Hỏi đáp), page
navigation, component lookup and read-only source metadata/renders. No new PDFs
are ingested and no OCR/chunk/embedding pipeline runs.

Removed API routes:
- `POST /projects/{p}/documents` (upload), `POST .../documents/{id}/reingest`,
  `GET .../documents/{id}/compare/{other_id}`
- `POST /ai/search`, `/ai/cross-references`, `/ai/inspection-checklists`,
  `/ai/daily-report-drafts`, `/ai/photo-suggestions`

Kept routes: document list/get (read-only), effective confirmation, versions,
original PDF, page metadata, page render image, page-extraction save/list/get/
verify, chat and conversation CRUD.

Removed backend files (no callers remain):
`ocr.py`, `extraction.py`, `chunking.py`, `fts.py`, `retrieval.py`,
`vector_store.py`, `crossref.py`, `inspection.py`, `vision.py`, `dap_design.py`.
`storage.py` now only resolves existing original/render paths; `embeddings.py`
keeps only `fold_text`/`tokenize`; `constants.py`, `schemas.py`, `router.py`,
`service.py` and `dependencies.py` were trimmed accordingly (no model columns,
tables or existing data were changed; there are no migrations).

Behaviour changes:
- `page_navigation.py` no longer reads `page.text`/`page.ocr_text`; it matches
  extraction title/summary/component facts plus page/document metadata
  (drawing number, revision, document name/type).
- `page_extraction.numeric_cross_check` and its OCR comparison helpers were
  removed; human extraction review is the only verification path.
- Chat no longer accepts/uses `vision` and returns no `vision_used/vision_note`.
- Page API still exposes legacy page fields for old rows, but the UI no longer
  displays text/OCR confidence; the viewer shows only the render image plus the
  page-extraction review panel.

Frontend:
- `EngineeringAIPage` is chat-first, mobile-first: chat is the main view, the
  read-only document list is a collapsed section, and clicking an extraction/
  database citation opens the image-only `PageViewer` in place.
- Deleted `CrossReferencePanel`, `DailyReportDraftPanel`, `InspectionChecklistPanel`,
  `PhotoSuggestionPanel`, `VersionComparePanel`, `DocumentUploadPanel`,
  `lib/tabNavigation*`; `DocumentList` no longer offers reingest/effective
  actions; `types.ts`/`api.ts` only expose retained endpoints.

Tests (deleted/rewritten because the feature under test was removed):
- Deleted: `test_assistive_apis.py`, `test_cross_reference.py`,
  `test_dap_design.py`, `test_embeddings.py`, `test_ocr_vision.py`.
- `conftest.py`: no upload/OCR/vision/embedding fixtures; added
  `add_source_document`/`add_page_extraction` for existing-data seeding.
- `test_retrieval_chat.py`: chat-only; removed search/OCR/vision tests; added a
  guard that removed routes return 404.
- `test_documents.py`: read-only list/get/page/render/effective/versions plus
  removed upload/reingest/compare route guards.
- `test_page_extraction_api.py`: extraction save/list/verify/scope only;
  removed render-hash/reingest/search tests.
- `test_component_search.py`, `test_page_extraction.py`: removed tests for the
  deleted retrieval-boost and numeric OCR cross-check helpers.
- `test_addendum_dod.py` (coordinator-owned): System A now seeds a verified
  extraction and chats/cites it; System B only guards the answer provider.
- `tests/test_integrated_workflow.py` and `tests/acceptance/test_ai_separation.py`:
  engineering-AI assertions only — removed upload/search/vision/embedding calls,
  seeded an existing document/page for acceptance evidence refs.

Dependencies now unused by this module (left in shared requirements/package.json
for the orchestrator): Tesseract binary + `vie` trained data, and the
`ENGINEERING_AI_OCR_*`, `ENGINEERING_AI_EMBEDDING_*`, `ENGINEERING_AI_VISION_*`
environment variables. PyMuPDF/Pillow/sqlite-vec remain used by site/acceptance/
core, so their shared requirements lines cannot be removed by this module.

Verification:
```bash
cd backend
DATABASE_URL=sqlite:///<tmp>/app.db SITE_REPORT_STORAGE=<tmp>/site \
ENGINEERING_AI_STORAGE=<tmp>/engineering ACCEPTANCE_STORAGE=<tmp>/acceptance \
../.venv/Scripts/python -m pytest tests -q
# 331 passed, 6 skipped, 0 failed

cd frontend && npm test   # 195 passed (31 files)
cd frontend && npm run build  # tsc -b + vite build OK
```

Unresolved:
- Existing page/chunk/embedding rows and their columns remain in the DB but are
  no longer read; a future migration may drop them.
- Existing pages need a render image to be viewable; if a page has no render the
  viewer shows only the extraction panel.
- Page-extraction review still requires an editor role; no auto-verification.

## 2026-11-23 — chat answers from AI extractions and the component database

Owner decision applied: chat answers from AI-extracted structured data and the
component database, never from raw OCR chunks. WIP commit `43ed7b8` had bypassed
page navigation and component lookup and broken 47 tests; both are restored.

- Chat order: `answer_page_navigation` -> `answer_component_query` -> new
  `answer_structured_question` (extractions first, then component DB). Navigation
  and exact component lookup are unchanged.
- Generic fallback reads `PageExtraction.extraction_json` only (component facts,
  key values, page title/summary) joined to its document/page. Verified rows are
  preferred; proposed rows are labelled and capped at 0.4 confidence. No
  `DocumentChunk`/`document_chunks` text is read for chat.
- Provider answers must cite `[n]` and their technical values must appear in the
  cited extraction quotes; otherwise a deterministic extracted-data answer is
  used. Low-OCR pages still add the fixed warning and cap confidence.
- Component DB path (`database_chat.answer_database_question`): exact whole-token
  code matches (canonical or alias) return the component plus repair scopes,
  work links, stages and progress rows. If a code matches nothing the answer is
  the fixed refusal plus a "name a specific code" warning; it never dumps the
  project. Aggregate/count questions return deterministic counts (type, segment,
  design groups, stages, progress events) with at most 5 representative row
  citations. Size caps: 40 000 chars of context, 20 matched components, 40
  related rows, 5 aggregate citations.
- Code matching normalises separators for comparison but matches whole tokens:
  `A2` does not match `A23`; alias `I40-42` matches question `I-40-42`.
- Every chat answer must carry citations. Extraction citations carry document,
  page, drawing, revision and extraction record id; database citations carry the
  row record id (`source=database`, `record_id=<row id>`). `CitationOut` gained
  optional `record_id`/`source`; the citation card renders a record badge and no
  page-open button for database rows.
- Progress rows are labelled "không phải nghiệm thu" and every database answer
  carries `Tiến độ thi công không phải nghiệm thu; database chưa có kết luận
  nghiệm thu.` No acceptance table is read and acceptance is never inferred.
- Vision (opt-in) now sends the first cited extract/page render instead of the
  OCR top-1 chunk; it is still only one rendered page.

Changed files:
- `backend/app/engineering_ai/database_chat.py` (rewritten: extraction + DB
  context, whole-token matching, aggregate/no-dump, record-id citations)
- `backend/app/engineering_ai/service.py` (restore navigation/component order;
  structured fallback; citation invariant; vision takes a cited page)
- `backend/app/engineering_ai/schemas.py` (optional `record_id`, `source`)
- `frontend/src/features/engineering-ai/types.ts`,
  `components/CitationCard.tsx`, `components/ChatPanel.tsx` (database citation
  display and updated chat copy)
- `backend/tests/engineering_ai/test_database_chat.py` (new)
- `backend/tests/engineering_ai/test_retrieval_chat.py`
- `backend/tests/engineering_ai/test_documents.py`
- `backend/tests/engineering_ai/test_opencode_provider.py`
- `backend/tests/engineering_ai/conftest.py`
- `backend/tests/test_addendum_dod.py`

Tests changed and why (OCR-chunk chat expectations rewritten, not deleted):
- `test_retrieval_chat.py`: `test_chat_returns_citations_and_provider_answer` ->
  `test_chat_answers_from_ai_extracted_page_data`; uncited/invented/valid
  provider tests now seed a verified extraction and assert extraction citations;
  `test_chat_vision_sends_only_top_one_rendered_page` ->
  `test_chat_vision_sends_only_cited_top_page`; low-OCR and conversation
  create/search tests now seed an extraction. The old assertions that a citation
  quote is a substring of page text no longer apply: chat cites extraction data,
  not OCR text (search still does).
- `test_documents.py::test_duplicate_same_bytes_...`: chat still checks
  effective/history version scoping, but now seeds one extraction per revision
  because chat no longer reads chunk text.
- `test_opencode_provider.py`: the provider-error service fallback test now calls
  `answer_structured_question` (the removed `_grounded_answer` was the OCR-chunk
  path) and asserts the extracted-data fallback.
- `conftest.py`: added `add_page_extraction` and `cover_extraction` helpers.
- `test_addendum_dod.py` (coordinator-owned): the chat DoD step now seeds one
  verified page extraction for page 2 before asking; chat assertions were not
  weakened.
- New `test_database_chat.py`: whole-token `A2`/`A23`, alias `I40-42`/`I-40-42`,
  aggregate answer without a full project dump, unmatched code refusal, and chat
  exact-code fallback to a database row citation.

Verification (temporary DB/storage, never `data/app.db`):

```bash
cd backend
DATABASE_URL=sqlite:///<tmp>/app.db SITE_REPORT_STORAGE=<tmp>/site \
ENGINEERING_AI_STORAGE=<tmp>/engineering ACCEPTANCE_STORAGE=<tmp>/acceptance \
../.venv/Scripts/python -m pytest tests -q
# 374 passed, 7 skipped, 0 failed
```

Frontend type-check: `cd frontend && npx tsc -b` (exit 0).

Unresolved:
- The generic extraction fallback is lexical (accent-folded token overlap), not
  semantic; an ambiguous question returns up to 5 best-matching extraction pages.
- Aggregate database answers cite up to 5 representative rows, not a dedicated
  aggregate record; the counts themselves are deterministic over all rows.
- Component DB data is current state, not document-versioned; `scope` only
  applies to extraction/document selection.
- Database answers are deterministic and do not call the answer provider.
- `record_id` survives in conversation message JSON but there is no
  `AICitation` column for it; add one only if citation analytics need it.

## Status and source truth

- **Real source scans are now available** in `/home/thangpham/Downloads` (133-page drawing, 108-page report), but they have **not been ingested**. Only four pages were measured and a temporary 2-page cut was piped through the API. Project knowledge remains unverified until an engineer reviews citations from the actual uploaded documents.
- The module never seeds documents, pages, chunks, citations, dimensions, quantities, approvals or project conclusions. Tests create **synthetic PDFs only** to exercise extraction/OCR/retrieval; they are not project records.
- Every chat response includes the warning that the project AI knowledge base is not verified. With no retrieved page, `answer` is exactly:
  `Không tìm thấy thông tin này trong hồ sơ công trình hiện có.`
- Low OCR confidence adds exactly:
  `Thông tin chưa đủ độ tin cậy, cần kiểm tra trực tiếp bản vẽ gốc.`
- No demo/project data is written to the database by this module.

## Scope implemented

- Private PDF upload per project with magic-byte validation, size/page limits, SHA-256, duplicate suppression and version metadata.
- Upload and photo-suggestion routes cap reads at the configured maximum before buffering/validation/model calls; oversized payloads return `413` without reading further.
- Real per-page extraction with PyMuPDF; pages with no/insufficient text layer are rendered to PNG and processed by OCR.
- OCR abstraction with a Tesseract implementation, optional Vietnamese language pack, and an explicit no-OCR fallback that marks pages `needs_review` instead of inventing text.
- Page/chunk storage with exact character offsets; deterministic local embedding per chunk; optional SQLite FTS5 index with graceful fallback.
- Project-scoped hybrid retrieval (BM25-style accent-folded lexical ranking + vector cosine + FTS boost). Only `ready` and `is_current` documents of the requested project are considered.
- Verbatim page citations including document, version, page, drawing number, revision, quote, URL, OCR confidence, chunk/page ids and score.
- Chat with conversation persistence, citations, confidence, exact no-source refusal and low-OCR warning.
- Provider-answer grounding gate: measured values, units, grades, diameters and classes in the generated text must appear in the cited quote(s); unsupported values replace the answer with the extractive citation answer and a warning.
- Mockable answer/embedding/OCR/vision providers; server-side env only, no hardcoded keys.
- Vision endpoint that only proposes photo category/caption/regions and requires engineer confirmation; it does not mutate SitePhoto or acceptance records.
- Cross-reference endpoint comparing two explicitly selected pages, returning both page citations and review-only discrepancy suggestions. It flags explicit numeric/unit/grade differences only, never says which page is correct or that the design is wrong.
- Optional multilingual/Vietnamese embedding API support with query/document prefixes, dedicated API key, dimension validation and model-scoped vectors.
- Read-only daily-report draft API from a provided or linked `DailyReport` (draft/reviewed): only copies recorded manpower/work/plans, preserves `0` vs `null` and null quantities, and lists missing fields without filling them.
- Read-only inspection-checklist suggestion API for a linked or inline work item: each suggestion carries a page citation, status is always `unconfirmed`, and no-source returns the fixed refusal.
- Persistent sqlite-vec store per `(project_id, model, dimension)` with stable hashed `vec0` tables; JSON vectors remain canonical/fallback. Ingest writes vectors and retrieval applies KNN candidates before project/effective filtering.
- Ingest status order `pending → running → ocr_completed → indexing → ready`, with retry idempotency and failed status.
- Native PyMuPDF table extraction (`tables_json`) and section-aware chunking (`section`) that never crosses a heading boundary.
- Effective-revision workflow: first version effective, new version non-effective until confirmation; versions, compare and `effective|history` retrieval scope.
- Conversation create/list/search/rename/delete/reopen/continue with project isolation.
- Optional chat Vision analysis of only the top-1 chunk's rendered page; default off, citation still required.
- In-process per-project/user rate limiting before upload, ingest, search, chat, cross-reference, report-draft, inspection and vision calls.
- Frontend feature for document upload/list, page/render viewer, cited chat, cross-reference panel, report-draft panel, inspection checklist panel, citation cards and photo suggestions.

## Files changed

Backend (all inside the allowed module):
- `backend/app/engineering_ai/__init__.py`
- `backend/app/engineering_ai/constants.py` (new)
- `backend/app/engineering_ai/schemas.py` (new)
- `backend/app/engineering_ai/providers.py` (new)
- `backend/app/engineering_ai/embeddings.py` (new)
- `backend/app/engineering_ai/ocr.py` (new)
- `backend/app/engineering_ai/chunking.py` (new)
- `backend/app/engineering_ai/extraction.py` (new)
- `backend/app/engineering_ai/fts.py` (new)
- `backend/app/engineering_ai/retrieval.py` (new)
- `backend/app/engineering_ai/vision.py` (new)
- `backend/app/engineering_ai/rate_limit.py` (new)
- `backend/app/engineering_ai/crossref.py` (new)
- `backend/app/engineering_ai/inspection.py` (new)
- `backend/app/engineering_ai/grounding.py` (new)
- `backend/app/engineering_ai/vector_store.py` (new)
- `backend/app/engineering_ai/page_extraction.py` (pure POC tile/merge/validation/numeric check; new)
- `backend/app/engineering_ai/service.py` (new)
- `backend/app/engineering_ai/router.py` (new)
- `backend/app/engineering_ai/dependencies.py` (extended with `project_access`, OCR/language/page-limit getters)
- `backend/app/engineering_ai/models.py` (addendum fields `change_note/is_effective/effective_at/effective_by`, `tables_json`, `section`; unique project/key/version constraint; `PageExtraction` matching migration `e2f6a1c9d430`)
- `backend/app/engineering_ai/storage.py` (existing private storage reused)

Tests:
- `backend/tests/engineering_ai/__init__.py`
- `backend/tests/engineering_ai/conftest.py`
- `backend/tests/engineering_ai/test_documents.py`
- `backend/tests/engineering_ai/test_retrieval_chat.py`
- `backend/tests/engineering_ai/test_cross_reference.py`
- `backend/tests/engineering_ai/test_embeddings.py`
- `backend/tests/engineering_ai/test_assistive_apis.py`
- `backend/tests/engineering_ai/test_ocr_vision.py`
- `backend/tests/engineering_ai/test_page_extraction.py` (POC tile/merge/validate/numeric check)
- `backend/tests/engineering_ai/test_page_extraction_api.py` (save/upsert/scope/verify/retrieval isolation)
- `backend/tests/engineering_ai/test_opencode_provider.py` (OpenCode DeepSeek provider mock/subprocess fallback)
- `backend/tests/engineering_ai/test_documents.py` (extended for statuses/vectors/tables/sections/effective/compare)

Frontend:
- `frontend/src/features/engineering-ai/index.ts`
- `frontend/src/features/engineering-ai/types.ts`
- `frontend/src/features/engineering-ai/lib/api.ts`
- `frontend/src/features/engineering-ai/components/DocumentUploadPanel.tsx`
- `frontend/src/features/engineering-ai/components/DocumentList.tsx`
- `frontend/src/features/engineering-ai/components/PageViewer.tsx`
- `frontend/src/features/engineering-ai/components/CitationCard.tsx`
- `frontend/src/features/engineering-ai/components/ChatPanel.tsx`
- `frontend/src/features/engineering-ai/components/CrossReferencePanel.tsx`
- `frontend/src/features/engineering-ai/components/DailyReportDraftPanel.tsx`
- `frontend/src/features/engineering-ai/components/InspectionChecklistPanel.tsx`
- `frontend/src/features/engineering-ai/components/PageExtractionPanel.tsx`
- `frontend/src/features/engineering-ai/components/VersionComparePanel.tsx`
- `frontend/src/features/engineering-ai/components/PhotoSuggestionPanel.tsx`
- `frontend/src/features/engineering-ai/pages/EngineeringAIPage.tsx`

Report:
- `docs/agent-reports/engineering-ai.md`

No shared core, migration, site, acceptance or frontend app files were edited.

## APIs implemented (under `/api/v1`)

- `POST /projects/{p}/documents` — multipart PDF upload (`file`, optional `type`). Returns 201 on new bytes, 200 on duplicate hash. Starts asynchronous ingest.
- `GET /projects/{p}/documents?include_history=true|false` — version/status/hash metadata.
- `GET /projects/{p}/documents/{id}` — document detail plus page summaries.
- `POST /projects/{p}/documents/{id}/reingest` — 202 retry; 409 while running; idempotently rebuilds pages/chunks/FTS.
- `GET /projects/{p}/documents/{id}/original` — private PDF stream after project check.
- `GET /projects/{p}/documents/{id}/pages/{n}` — page JSON: extracted/OCR text, method, confidence, drawing/revision, warnings, render/original URLs.
- `GET /projects/{p}/documents/{id}/pages/{n}/render` — rendered PNG for scan/OCR pages.
- `POST /projects/{p}/documents/{id}/effective` — `{change_note}`; confirms effective revision, writes `effective_by/effective_at`, leaves other family versions non-effective.
- `GET /projects/{p}/documents/{id}/versions` — version metadata/history for the document family.
- `GET /projects/{p}/documents/{id}/compare/{other_id}` — metadata/page/chunk/table statistics; no design conclusion.
- `POST /projects/{p}/ai/search` — `{query, top_k, scope?}` → citations. `scope=effective` by default; `history` includes all ready revisions.
- `POST /projects/{p}/ai/chat` — `{message, conversation_id?, top_k?, scope?, vision?}`. Vision is opt-in and only reads the top-1 rendered page.
- `POST /projects/{p}/ai/conversations` — create conversation.
- `GET /projects/{p}/ai/conversations?q=` — project-scoped history with text search.
- `PATCH/DELETE /projects/{p}/ai/conversations/{id}` — rename/delete; source documents/pages remain.
- `POST /projects/{p}/documents/{d}/pages/{n}/extractions` — validate/save or upsert page extraction by `(page_id, model, prompt_version, mode)`; status `proposed`, actor recorded, rendered-page SHA-256 when available.
- `GET /projects/{p}/documents/{d}/extractions?page=&status=` — project/document-scoped extraction list.
- `GET /projects/{p}/page-extractions/{id}` — one project-scoped extraction.
- `PATCH /projects/{p}/page-extractions/{id}` — `{status: verified|rejected, note?}`; writes verifier/timestamp/note, never auto-verifies.
- `POST /projects/{p}/ai/cross-references` — `{first:{document_id,page_number}, second:{document_id,page_number}, topic?}` → two page citations plus review-only suggestions. Each suggestion carries both citation objects, verbatim quotes, observation, confidence and `requires_engineer_review=true`; empty suggestions never mean the pages agree.
- `POST /projects/{p}/ai/daily-report-drafts` — exactly one of `{report_id}`, `{report_date}` or `{report}`. Returns a copy of recorded manpower/work/plans, summary lines, missing fields and `no_invented_quantities=true`. No report is written.
- `POST /projects/{p}/ai/inspection-checklists` — exactly one of `{work_item_id}` or `{work_item:{code?,name?,location?,component?}}`, optional `focus`, `top_k`. Each suggestion has a page citation, `status=unconfirmed`, `auto_approved=false`; no sources returns the fixed refusal.
- `GET /projects/{p}/ai/conversations/{id}` — messages with citations.
- `POST /projects/{p}/ai/photo-suggestions` — image upload; returns unconfirmed proposal and disclaimer. No SitePhoto write.

All routes call `Depends(project_access)` before DB/file/model access. `project_access` is a thin overridable dependency around the shared `require_project_member`.

`POST /ai/cross-references`, `POST /ai/daily-report-drafts`, `POST /ai/inspection-checklists`, `POST /ai/photo-suggestions`, document effective/versions/compare and conversation create/patch/delete are module extensions; Codex should add them to the shared API contract when integrating.

## Per-page extraction and OCR behavior

1. Validate header `%PDF-`, size (`ENGINEERING_AI_MAX_PDF_BYTES`, default 50 MB), page count (`ENGINEERING_AI_MAX_PAGES`, default 500), reject encrypted PDFs.
2. The router first calls `UploadFile.read(limit + 1)`; data beyond the configured limit returns `413` before PDF validation or storage. Photo suggestions use the same bounded read against `ENGINEERING_AI_MAX_IMAGE_BYTES` before any vision call.
3. Compute SHA-256; duplicate `(project_id, sha256)` returns the existing record. New bytes under the same normalized file name increment `version`; previous family row becomes `is_current=false`, new versions start `is_effective=false` (first family version is effective).
4. Extract text per page with PyMuPDF. If the text layer is shorter than `ENGINEERING_AI_MIN_NATIVE_TEXT` (default 60 chars) or is sparse relative to embedded images, render the page at `ENGINEERING_AI_RENDER_DPI` (default 200) and run OCR.
5. Native tables are extracted with `page.find_tables()` into `tables_json`; failures never remove text/OCR.
6. Tesseract command: `tesseract <png> stdout -l <languages> --psm 3 tsv`, parse word confidences (0–1 average). If Vietnamese data is missing, retry with `eng` and record a warning. If OCR is unavailable/fails, keep empty text, add a warning and `needs_review=true`.
7. Parse drawing number/revision only from actual matched text (patterns for `Bản vẽ/Drawing No/DWG/BV`, `Rev/Hiệu chỉnh`). No filename-based invented metadata.
8. Chunk within detected sections (never across headings), with exact page offsets, `section`, vectors and FTS mirroring.
9. Ingest statuses: `pending → running → ocr_completed → indexing → ready|failed`. Retries delete/rebuild pages, chunks, JSON vectors, sqlite-vec rows and FTS rows; no duplicate records.

## Retrieval, citations and answer policy

- Scope is enforced at query level: `DocumentChunk.project_id == project`, page/document project match, `status=ready`, `is_current=true`.
- Ranking uses accent-folded BM25-style term scoring, exact phrase bonus, local embedding cosine and a small FTS5 match boost. **Vector similarity alone cannot create a citation**; a lexical or FTS hit is required, preventing false citations from hash collisions.
- Quote is a verbatim substring of the stored chunk, selected around the best query-token window.
- Default provider is deterministic extractive: it only quotes retrieved chunks with `[n]` labels. No external model is called.
- Optional OpenAI-compatible provider is enabled only when `ENGINEERING_AI_PROVIDER=openai_compatible` and URL/model/key are all present server-side. Provider answers without valid `[n]` citations are discarded and replaced by the extractive answer with a warning.
- Provider answers with valid citations still pass a technical-value gate (`grounding.py`): explicit measurements/units, grades, diameters and classes are extracted from the answer and must all appear in the cited quote(s). An invented value (e.g. `75 mm` when the cited quote says `50 mm`) replaces the answer with the extractive citation answer and adds `Câu trả lời của provider chứa giá trị kỹ thuật không có trong citation; đã thay bằng trích dẫn trực tiếp.`
- A legitimate value present in the cited quote (e.g. `50 mm`) is retained; the provider answer is not replaced. Numeric equivalence is normalized only for decimal/thousands formatting and unit spelling (`50mm` = `50 mm`, `1.500 mm` = `1500 mm`), not physical unit conversion.
- Provider failures degrade to the extractive answer; they never produce an ungrounded answer.
- `confidence` is a bounded heuristic (0–0.85, capped at 0.40 for low-OCR evidence) and intentionally not presented as a verified engineering conclusion.
- Chat persists user/assistant messages and `AICitation` rows. Cross-project conversation ids return 404.

## Cross-reference / discrepancy suggestions

`POST /projects/{p}/ai/cross-references` accepts two explicit project-scoped page references and an optional topic. The comparator in `crossref.py` is deterministic and conservative:

1. Split each page into verbatim sentence quotes.
2. Keep only sentences with explicit unit values (`mm`, `cm`, `m`, `m²`, `m³`, `kg`, `MPa`, `kN`, `%`, `độ`) or concrete/steel grades (`C25`, `C30`, ...). Bare dates, drawing numbers and page numbers are ignored.
3. Require at least two shared meaningful topic tokens (diacritics folded) on both sentences.
4. Flag only when both sides have values and the value sets are different with no common value. Identical or overlapping values produce no suggestion.
5. Return at most five candidates, each with the **two verbatim quotes** as separate citations, a textual-overlap confidence, and observation `... không kết luận trang nào đúng hay thiết kế sai.`

Safety rules:
- Every successful response includes exactly two top-level page citations, even when `suggestions=[]`.
- Empty suggestions return: `Không phát hiện khác biệt văn bản rõ ràng giữa hai trang; không kết luận hồ sơ đồng nhất, đã được duyệt hoặc đúng thiết kế.`
- `status` is always `needs_engineer_review`; each suggestion has `requires_engineer_review=true`.
- Low-OCR pages add the fixed review warning and cap suggestion confidence at 0.40.
- Same page, missing page, blank/insufficient text, or cross-project page returns 404/422. No automatic full-document pair discovery exists yet.

## Daily-report draft assist

`POST /projects/{p}/ai/daily-report-drafts` is a read-only assist:

- Source is exactly one of a linked `report_id`, a linked `report_date`, or an inline `report` object. The linked source must be a `DailyReport` of the same project with status `draft` or `reviewed`.
- The endpoint copies `manpower[]`, `work_logs[]`, `next_day_plans[]` and notes without changing values. It preserves `count=0` as zero and `count=null` as unknown; null quantities remain null.
- Missing fields are reported individually (`section`, optional `index`, `field`, message). The service never chooses a substitute quantity, unit, person, location or plan.
- `summary_lines` are assembled only from recorded values; missing counts are written as `chưa ghi số lượng`, not as `0`.
- No `DailyReport` or child row is inserted, updated or deleted. This was verified by a linked reviewed-report test.
- Linked mode imports the Site Report ORM models read-only; Codex must keep those models in the shared migration chain and ensure project membership is checked before the route (already done via `project_access`).

## Inspection-checklist suggestions

`POST /projects/{p}/ai/inspection-checklists` is a read-only assist for one linked `work_item_id` or inline work item:

1. Build a query from code, name, location, component and optional focus.
2. Retrieve current, ready, project-scoped pages through the same grounded retrieval pipeline.
3. Choose a verbatim sentence with inspection/technical hints and query overlap; fall back to the retrieval quote.
4. Return one suggestion per page, each with `item` prompt, verbatim `criterion`, and a full `citation` (document, version, page, drawing/revision, quote, URL, OCR confidence).
5. `status` is always `unconfirmed`, `auto_approved=false`, `requires_engineer_review=true`. No acceptance checklist is written and no `yes`/approved state is generated.
6. With no retrieved source, `suggestions=[]`, `no_source=true`, `has_sources=false` and `message` is exactly `Không tìm thấy thông tin này trong hồ sơ công trình hiện có.`

## Embeddings and retrieval limitation

- **Default:** `HashingEmbeddingProvider` (signed feature hashing over unigrams/bigrams). It is deterministic, key-free and offline, but it is **not semantic**: it does not understand Vietnamese synonyms, paraphrases, abbreviations, cross-language meaning, or long-range context. Recall depends primarily on lexical overlap; the hash vector only adds a weak signal. Hash collisions alone cannot create a citation because a lexical/FTS hit is required.
- **Optional multilingual/Vietnamese API:** set `ENGINEERING_AI_EMBEDDING_PROVIDER=multilingual` (aliases: `vietnamese`, `openai_compatible`, `openai`) plus an embedding endpoint/model, true dimension and key. OpenAI-style JSON (`{model,input}` → `{data:[{embedding}]}`) is the default; `ENGINEERING_AI_EMBEDDING_REQUEST_STYLE=inputs` supports TEI/HuggingFace-style `{inputs}` endpoints and common vector response shapes. Any multilingual Vietnamese-capable model (E5/BGE-family, vLLM/TEI/LM Studio/OpenAI-compatible gateway) can be used.
- Asymmetric E5-style prefixes are supported server-side: `ENGINEERING_AI_EMBEDDING_QUERY_PREFIX` for search queries and `ENGINEERING_AI_EMBEDDING_DOCUMENT_PREFIX` for ingested chunks. The provider name includes a prefix digest so query/document config changes do not mix incompatible vectors.
- Vectors are loaded only when `DocumentEmbedding.model == current provider.name`. After changing embedding model/dimension/prefix, **re-ingest the documents**; otherwise retrieval safely falls back to lexical ranking without old vectors.
- A configured endpoint returning the wrong dimension raises and falls back to local hashing during ingest; search degrades to lexical/vector-less retrieval rather than failing.

## Environment configuration (server-side only)

| Variable | Default | Purpose |
| --- | --- | --- |
| `ENGINEERING_AI_STORAGE` | `/tmp/opencode/engineering-ai-storage` | Private storage root; production must point to a protected volume |
| `ENGINEERING_AI_MAX_PDF_BYTES` | 52428800 | Upload limit |
| `ENGINEERING_AI_MAX_IMAGE_BYTES` | 15728640 | Vision upload limit |
| `ENGINEERING_AI_MAX_PAGES` | 500 | PDF page limit |
| `ENGINEERING_AI_MIN_NATIVE_TEXT` | 60 | OCR fallback threshold |
| `ENGINEERING_AI_RENDER_DPI` | 200 | Scan render resolution |
| `ENGINEERING_AI_OCR_ENGINE` | `tesseract` | `none` disables OCR |
| `ENGINEERING_AI_OCR_CMD` | `tesseract` | OCR binary |
| `ENGINEERING_AI_OCR_LANGUAGES` | `vie+eng` | Tesseract language pack list |
| `ENGINEERING_AI_PROVIDER` | `extractive` | `extractive`, `openai_compatible`, or `opencode_deepseek`/`opencode`/`deepseek` |
| `ENGINEERING_AI_OPENCODE_MODEL` | `opencode-go/deepseek-v4.1-flash` | Only the allow-listed OpenCode DeepSeek model is accepted |
| `ENGINEERING_AI_CHAT_URL` | unset | Full chat-completions endpoint |
| `ENGINEERING_AI_MODEL` | unset | Chat model id |
| `ENGINEERING_AI_API_KEY` | unset | Server-side key; never exposed to frontend |
| `ENGINEERING_AI_TIMEOUT` | 60 | Provider timeout seconds |
| `ENGINEERING_AI_EMBEDDING_PROVIDER` | `local` | `local` or `multilingual`/`vietnamese`/`openai_compatible` |
| `ENGINEERING_AI_EMBEDDING_URL` / `_MODEL` / `_DIM` | unset / unset / 256 | OpenAI-compatible multilingual endpoint, model and true dimension |
| `ENGINEERING_AI_EMBEDDING_API_KEY` | falls back to `ENGINEERING_AI_API_KEY` | Optional dedicated embedding key |
| `ENGINEERING_AI_EMBEDDING_QUERY_PREFIX` | empty | Optional E5 query prefix (e.g. `query: `) |
| `ENGINEERING_AI_EMBEDDING_DOCUMENT_PREFIX` | empty | Optional E5 document prefix (e.g. `passage: `) |
| `ENGINEERING_AI_EMBEDDING_REQUEST_STYLE` | `openai` | `openai` (`model`+`input`) or `inputs` for TEI/HuggingFace-style endpoints |
| `ENGINEERING_AI_VISION_PROVIDER` | `none` | Optional `openai_compatible` |
| `ENGINEERING_AI_VISION_URL` / `_MODEL` | unset | Optional vision config |
| `ENGINEERING_AI_RATE_LIMIT_PER_MINUTE` | 60 | Per project/user/scope in-process limit |
| `ENGINEERING_AI_INGEST_STALE_SECONDS` | 900 | Allow retry of a stuck pending/running ingest after this age |
| `ENGINEERING_AI_MIN_SCORE` | 0.08 | Retrieval score floor |

No key, endpoint or model is hardcoded. Missing provider config falls back to the offline extractive provider.

## Models needed / shared integration

Module-local tables (prefixed `engineering_ai_`; currently isolated Base with shared-core fallback):
- `SourceDocument`: `project_id, type, original_name, document_key, original_path, sha256, version, is_current, status, mime_type, size_bytes, page_count, drawing_number, revision, ocr_languages, warnings_json, page_stats_json, error_message, created_by, ingest_started_at/finished_at, created_at/updated_at`; unique `(project_id, sha256)` and `(project_id, document_key, version)`.
- `DocumentPage`: `document_id, page_number, rendered_path, text, ocr_text, ocr_confidence, extraction_method, drawing_number, revision, width, height, needs_review, warnings_json`.
- `DocumentChunk`: `page_id, document_id, page_number, chunk_index, text, start_offset, end_offset, char_count`.
- `DocumentEmbedding`: `chunk_id, page_id, document_id, model, dim, vector_json`.
- `AIConversation`: `project_id, title, messages_json, created_by`.
- `AICitation`: `conversation_id, message_index, chunk_id, document_id, page_id, document_name, version, page_number, drawing_number, revision, quote, url, ocr_confidence`.
- Runtime FTS table `engineering_ai_chunks_fts` is created lazily (optional). It is not part of the migration chain yet.
- Cross-reference suggestions need no additional table: they cite existing `DocumentPage` rows and reuse citation response objects; they are not persisted as findings or conclusions.
- Daily-report draft reads existing Site Report tables (`daily_reports`, `manpower_entries`, `daily_work_logs`, `next_day_plans`) and writes none. Inspection checklist reads shared `WorkItem` (when linked) and writes no acceptance/checklist rows.
- No new migration is needed for either assist API; Codex must preserve the Site Report/shared tables and relationships in the single migration chain.

Requests to Codex:
1. Add models/tables and FTS setup to the single migration chain; reconcile with any shared `SourceDocument/DocumentPage/DocumentChunk/AICitation` models.
2. Mount `app.engineering_ai.router` under `/api/v1` in `backend/app/main.py`.
3. Wire `EngineeringAIPage` into `frontend/src/app` navigation (`documents`/`ai` menu items already exist).
4. Add shared `{detail, code}` error envelope. This module currently raises FastAPI `HTTPException` with `detail` only, matching the existing site module; 429 includes `Retry-After`.
5. Replace in-process rate limiting with a shared store for multi-worker deployment.
6. Add audit log entries for document upload/reingest/AI chat/cross-reference through the shared audit service; this module does not write `AuditLog` directly.
7. Site Report should call photo suggestions only as proposals and apply category/caption to `SitePhoto` after explicit engineer confirmation.
8. Keep the Site Report ORM models (`DailyReport`, `ManpowerEntry`, `DailyWorkLog`, `NextDayPlan`) and shared `WorkItem` available to this module: report-draft linking and linked inspection work items read them directly, without writing.
9. Install/verify Tesseract Vietnamese traineddata (`vie`) on the deployment host; if absent, OCR retries `eng` and pages are marked for review.
9. Decide policy for old-version document retention/deletion; search uses only current versions, but old-version page URLs remain readable for citation history.
10. If stronger semantic retrieval is required, configure a multilingual/Vietnamese embedding endpoint and re-ingest; the default local hashing embedder is deterministic but not semantic. Configure the model's true dimension and E5-style prefixes if applicable.
11. Add cross-reference/report-draft/inspection navigation/UI actions to the app shell as needed; their panels are exported from the feature barrel. The report-draft and inspection endpoints do not persist drafts or checklist states.

## Real source readiness (measured 11/11/2026)

### Source inventory

| File | Pages | Bytes | Text layer | Default 50 MiB gate |
| --- | ---: | ---: | ---: | --- |
| `/home/thangpham/Downloads/bản vẽ scan_1.pdf` | 133 | 49,315,384 | 0 chars on sampled pages; 1 image/page | allowed (49.3 MB < 52,428,800 B) |
| `/home/thangpham/Downloads/Tập 1 - thuyết minh báo cáo KTKT sửa chữa nứt cọc dầm cầu cảng_0001.pdf` | 108 | 66,405,004 | 0 chars on sampled pages; 1 image/page | **blocked** (413) |

### Real OCR measurements (200 DPI, Tesseract 5.5.4, `vie+eng`)

`TESSDATA_PREFIX=/home/thangpham/.local/share/tessdata`; word count is `\S+` tokens; confidence is the Tesseract TSV word-average.

| PDF | Page | Render | OCR | Total | Words | Confidence | Warnings |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| bản vẽ scan | 3 | 0.23 s | 1.76 s | 1.99 s | 191 | 0.6943 | none |
| bản vẽ scan | 6 | 0.26 s | 1.69 s | 1.95 s | 349 | 0.6678 | none |
| thuyết minh | 5 | 0.28 s | 2.80 s | 3.07 s | 382 | 0.7507 | none |
| thuyết minh | 10 | 0.28 s | 1.48 s | 1.77 s | 570 | 0.9548 | none |

The drawing samples are usable but noisy (`0.67–0.69` average confidence), close enough to the 0.60 review threshold that engineers must visually check dimensions. Page 10 is clean (`0.95`); page 5 is a table-of-contents page with dotted-leader noise.

### Full pipeline sample: real 2-page cut

- Input: `/tmp/opencode/eng-ai-real-sample-2p.pdf` (1,789,736 B), pages 5 and 10 from the real report PDF.
- Temp only: in-memory SQLite + `/tmp/opencode/eng-ai-real-e2e-storage`; fake project `real-sample-project`; no `data/app.db`, no shared storage, no original copied.
- API upload: `201`; document `ready`; 2 pages; both `extraction_method=ocr`; 3,164 and 2,640 chars; OCR confidence `0.7507` and `0.9548`; no warnings.
- Ingest wall time in TestClient: **4.87 s** (render + OCR + chunk + local embedding + FTS + DB).
- Search `"bê tông"`: 5 citations across pages 1–2; every returned quote was verified as a **substring of the cited page text**. Citation URLs resolved to the correct document/page.
- In a real server, `POST /documents` returns while ingest runs in the background; poll `GET /documents/{id}` for `pending → running → ocr_completed → indexing → ready` (or `failed`).

### 50 MiB limit confirmation

- Default `storage.max_pdf_bytes()` = **52,428,800 B (50 MiB)**.
- Report PDF = **66,405,004 B** → API returned **413** in **0.1 s** with `Tệp PDF vượt quá dung lượng cho phép.` The bounded-read fix means no unbounded buffering in the route.
- Set `ENGINEERING_AI_MAX_PDF_BYTES=73400320` (70 MiB) or larger before real ingest; also raise the reverse-proxy/body-size limit above 70 MB. `ENGINEERING_AI_MAX_PAGES=500` already covers 133/108 pages.

### Migration/FTS check (read-only)

- Alembic head: `d8e52a3c4b21` after coordinator migrations `c7d41f2b9a10` and `d8e52a3c4b21`.
- `data/app.db` has all six `engineering_ai_*` tables (`documents`, `document_pages`, `document_chunks`, `document_embeddings`, `conversations`, `citations`) and the unique constraints including `(project_id, document_key, version)`. All counts are 0; no real data was written.
- FTS is **not** in the migration: `engineering_ai_chunks_fts` is created lazily by `ensure_fts()` during ingest. A temp file-DB ingest confirmed: before ingest `[]`; after ingest the FTS5 table plus shadow tables existed with 6 rows for 6 chunks. The first real ingest will create this virtual table inside `data/app.db` outside Alembic.
- If FTS creation is unavailable (SQLite without FTS5/DDL restrictions), ingest continues and retrieval falls back to lexical/vector ranking; no page/chunk data is lost. Coordinator may pre-create FTS in a migration/script if schema changes must stay Alembic-only.

### Full-ingest estimate

- OCR/render extrapolation: 133 drawing pages × ~2.0 s = ~4.4 min; 108 report pages × ~2.4 s = ~4.3 min → **~8.8 min**.
- Chunk/embed/FTS overhead measured at ~0.1–0.2 s for 2 pages (6 chunks); for 241 pages around **700–750 chunks** and roughly **10–30 s** additional.
- Practical estimate: **10–12 minutes** of OCR pipeline, plan **12–15 minutes** wall time; run sequentially (drawing then report) and poll status.
- Disk: sampled renders average ~1.7 MB/page; 241 scanned pages ≈ **0.4 GB** of PNG renders, plus **0.116 GB** original PDFs. Reserve **≥1 GB** free under `ENGINEERING_AI_STORAGE`.

### Reproduction commands

```bash
cd backend

# OCR sample measurement (outputs PNGs under /tmp/opencode/real-ocr-measure)
TESSDATA_PREFIX=/home/thangpham/.local/share/tessdata \
  ../.venv/bin/python /tmp/opencode/eng-ai-real-ocr-check.py

# Real 2-page cut -> API -> citation check (temp DB/storage only)
TESSDATA_PREFIX=/home/thangpham/.local/share/tessdata \
ENGINEERING_AI_STORAGE=/tmp/opencode/eng-ai-real-e2e-storage \
  ../.venv/bin/python /tmp/opencode/eng-ai-real-e2e-check.py

# Migration head (read-only)
../.venv/bin/python -m alembic -c alembic.ini heads
```

## Addendum vòng 2 (A–G)

### A. Persistent vector store

- `vector_store.py` uses `sqlite-vec` v0.1.9 in the same SQLite file. Each `(project_id, model, dimension)` gets a stable `vec_ea_<sha256[:24]>` `vec0` table.
- `CREATE VIRTUAL TABLE` is lazy on first ingest; no temporary/in-memory vector store per app open. Ingest upserts `(chunk_id, document_id, page_id, vector)`; retry deletes old chunk vectors first.
- Retrieval asks sqlite-vec for KNN candidates, then joins/filters project + `effective|history` scope in ORM rows. KNN boosts rank; lexical/FTS evidence is still required for a citation.
- JSON `DocumentEmbedding.vector_json` remains canonical fallback. If the extension/table/query fails, the existing lexical/vector ranker is used.
- Tests cover: vectors persisted and returned by KNN after ingest; monkeypatched unavailable extension still returns lexical search results and creates no vec table.

### B. Ingest status

`pending → running → ocr_completed → indexing → ready`, failure `failed`. Pages are committed and `ocr_completed` is recorded before chunk/vector indexing; `indexing` is committed before writes; retry is idempotent. `status_hook` exists only for tests/diagnostics. UI labels `ocr_completed`, `indexing` and polls all non-terminal states.

Tests assert exact status order on first ingest and retry, and unchanged page/chunk counts after retry.

### C. Tables and sections

- `DocumentPage.tables_json` stores native `page.find_tables()` results (`bbox`, row/col counts, rows). Test PDF with grid asserts table cell `50` is exposed by the page API.
- `DocumentChunk.section` is populated by `chunk_text_with_sections()`; headings (`1. VAT LIEU`, `2. THI CONG`) start sections and chunking never crosses them. Test asserts offsets/sections and no chunk contains both headings.
- Scanned/OCR pages still work; table extraction is best-effort and cannot break text/OCR. `find_tables()` adds CPU on native pages; the earlier full-ingest estimate should retain 10–15 minutes of headroom.

### D. Effective revisions and scope

- First family version: `is_current=true`, `is_effective=true`. New version: `is_current=true`, `is_effective=false`; old effective stays effective until confirmation.
- `POST /documents/{id}/effective` requires `change_note`, writes `effective_by/effective_at`, sets other family versions non-effective.
- `GET /documents/{id}/versions` and `GET /documents/{id}/compare/{other_id}` expose metadata/page/chunk/table statistics only. Compare disclaimer rejects design conclusions.
- `search/chat` accept `scope=effective|history`; default effective. Tests cover old revision kept, new revision not automatically effective, history search/chat finding it, confirmation switching effective scope, version list and compare.

### E. Conversation management

- Create/list/search (`q`)/rename/delete/reopen/continue, all project-scoped. Citations stay inside conversation messages; deleting a conversation deletes its conversation citations but not documents/pages/renders.
- UI adds conversation sidebar, search, new/rename/delete, reopen and continue, plus effective/history scope selector.
- Tests cover CRUD/search, cross-project 404s for read/chat/patch/delete.

### F. Vision one page

- `ChatRequest.vision=true` is opt-in. Service sends **only** the rendered PNG of the top-1 cited chunk's page; it never sends the full PDF.
- Default provider `none` sends nothing. Citation remains mandatory; low OCR still adds the fixed warning.
- Response includes `vision_used`, `vision_note`; warnings include `Vision chỉ nhận một trang...`. Mock test asserts one provider call on a scanned page, no call by default.

### G. UI

- Status labels updated for `ocr_completed`/`indexing`; effective badge, confirm-effective action, version compare panel, scope selector, conversation management and opt-in vision control added.
- Feature typecheck clean; full `npm run build` also passed after site changes.

## OpenCode DeepSeek answer provider (vòng 5)

`providers.py` adds `OpenCodeDeepSeekProvider` with the exact name `opencode_deepseek:deepseek-v4.1-flash`:

- Calls `opencode api` through the module-level `_opencode_call`; no key is read or hardcoded.
- Creates `POST /api/session` with exactly `{"title":"Construction AI answer","model":{"providerID":"opencode-go","id":"deepseek-v4.1-flash"}}`, sends `{text, files: []}`, waits, reads assistant text parts, and always attempts session deletion.
- The combined system/user prompt is grounded like the OpenAI provider and explicitly says `Không gọi tool; chỉ trả lời từ nguồn.`; it requires `[n]` citations and the exact no-source sentence.
- `ENGINEERING_AI_PROVIDER=opencode_deepseek|opencode|deepseek` selects it. `ENGINEERING_AI_OPENCODE_MODEL` defaults to `opencode-go/deepseek-v4.1-flash`; any other model is rejected and falls back to extractive.
- Timeout is `ENGINEERING_AI_TIMEOUT` (default 120s). Missing binary, API error, timeout, invalid JSON or empty answer raises `ProviderError`; existing service fallback returns the extractive citation answer.
- Tests mock `_opencode_call`/`subprocess.run`: session/model body, prompt citation/no-source/no-tool instructions, success answer, timeout `ProviderError`, extractive fallback, aliases and model allow-list. No network/model call occurs in tests.

## Page extraction enrichment (vòng 4)

Executable storage for POC/tiled page extraction, without model calls:

- `PageExtraction` model matches migration `e2f6a1c9d430` exactly: project/document/page/page-number, rendered-page SHA-256, model, prompt version, mode, proposed/verified/rejected status, confidence, extraction JSON, warnings, creator/verifier/timestamps/note; unique `(page_id, model, prompt_version, mode)`.
- POST validates the POC schema (`validate_extraction`) before saving, computes SHA-256 from the private rendered page when present, resets upserts to `proposed`, and records the current actor as creator.
- GET list/detail are project-scoped; PATCH verify/reject records `verified_by`, `verified_at`, `verify_note`.
- Unverified extraction is **not** retrieval text: search/chat still use only `DocumentPage`/`DocumentChunk` content and citations. A test stores an invented token in extraction JSON and confirms search does not find it.
- UI `PageExtractionPanel` inside the page viewer shows summary/key values/warnings/confidence/status, marks data as AI-extracted pending original-page comparison, and exposes explicit confirm/reject buttons with notes. No automatic verification.

## POC tile extraction helpers

`backend/app/engineering_ai/page_extraction.py` is pure logic for the coordinator to wire into `scripts/deepseek_page_extract.py`; this module calls no model, DB, storage or migration.

- `Tile(label,left,top,right,bottom)`: pixel rectangle with `width`, `height`, `area` helpers.
- `plan_page_tiles(width,height,grid=2,overlap=0.06,include_title_block=True)`: row-major overlapping tiles plus a bottom-right title-block tile; no empty/too-small tiles; all coordinates clipped to the page.
- `merge_extractions(parts, full_page=None)`: full page wins for page type/title/drawing number/revision/summary; key values, table rows and warnings are merged/deduped; key values dedupe on normalized `name+value+unit+quote`; size caps; conflicts add warnings and reduce confidence; output matches the POC schema. Only `drawing_number`/`revision` differences are page-level metadata conflicts; tile title/page_type is not treated as a page conflict because tiles only see a region.
- Tile warning noise filter: full-page warnings are always kept. Tile warnings containing crop-context phrases (`vùng crop`, `đây là vùng`, `trong vùng`, `không đủ ngữ cảnh`, `bị cắt`, `không thấy số hiệu bản vẽ`, `không thấy revision`, `không xác định được revision`) are dropped. Warnings about conflicting numbers/units, blurry text, hidden stamps or uncertain symbols remain.
- `numeric_cross_check(value, ocr_text)`: compares model key-value numbers against OCR numbers and warns on absence or unit mismatch; never changes the model number. Warnings are de-duplicated and capped at 20, followed by `Còn N cảnh báo số/đơn vị khác` when more remain.

Recommended coordinator use:

```python
from app.engineering_ai.page_extraction import (
    plan_page_tiles, merge_extractions, validate_extraction, numeric_cross_check,
)

tiles = plan_page_tiles(width, height, grid=2, overlap=0.06)
# crop each Tile, run the existing DeepSeek direct-image call, collect JSON by label
merged = merge_extractions(tile_results, full_page=full_page_result)
errors = validate_extraction(merged)
cross_check_warnings = numeric_cross_check(merged, ocr_text)
```

The POC script is not modified. Results must remain proposed/unverified until an engineer checks the page; tile conflict warnings and numeric cross-check warnings must never be silently dropped.

## Tests

Command:

```bash
cd backend
../.venv/bin/python -m pytest tests/engineering_ai -q
```

Result this pass: **63 passed** (1 third-party Starlette/httpx deprecation warning).

A separate manual smoke (not part of the automated suite because it needs the system binary/traineddata) generated a scanned image-only PDF, ran the real Tesseract engine through the API, and produced `extraction_method=ocr`, `ocr_confidence≈0.92`, drawing number `BV-09`, and a searchable page citation. Automated tests inject a mock OCR engine so they remain deterministic.

Coverage:
- private upload and vision routes reject oversized payloads with `413` before unbounded buffering/model invocation; invalid smaller PDFs still return `422`.
- real multi-page PDF text extraction; per-page text, drawing number/revision; original stream.
- SHA-256 duplicate idempotency, version increment, `is_current` switch, first-effective/new-not-effective, effective confirmation, versions and compare.
- sqlite-vec persistent vectors and KNN; vectors survive engine reopen; extension-unavailable fallback with no vec table.
- exact ingest status order and retry idempotency.
- native table extraction and section-boundary chunking.
- scan render + mock OCR fallback, OCR confidence and render endpoint.
- no-OCR path: empty text, `needs_review`, warnings, no invented search result.
- invalid PDF rejection.
- retry idempotency for pages/chunks/FTS.
- project scoping for documents, pages, originals, search, conversations.
- citation quote is a verbatim substring of the cited page; URL resolves.
- exact no-source refusal; conversation persistence, create/search/rename/delete/reopen and project isolation.
- search/chat default `effective` scope and `history` scope; new revision is not automatically effective.
- opt-in chat Vision calls the mock provider once for a rendered top-1 page and does not call it by default.
- cross-reference flags a numeric difference with two verbatim citations; identical values produce no finding without a consistency claim; same page/cross-project pages rejected; low-OCR warning and confidence cap.
- daily-report draft preserves recorded `0` vs `null` and exact quantities, reports missing fields without filling them, accepts linked reviewed/draft reports and rejects cross-project links.
- inspection checklist suggestions carry a page citation; every suggestion is `unconfirmed`/`auto_approved=false`; no-source returns the fixed refusal; linked work items are project-scoped.
- configurable multilingual embedding endpoint: OpenAI and TEI/HuggingFace `inputs` request styles, model, dimension, dedicated key and asymmetric query/document prefixes; local fallback when key is absent; vector model scoping.
- provider answer with `[n]`; uncited provider answer replaced by extractive citations; invented `75 mm` versus cited `50 mm` rejected with extractive fallback and grounding warning; valid cited `50 mm` retained.
- low-OCR fixed warning and confidence cap.
- photo suggestion is proposal-only; non-image rejection.
- offline extractive default without env/key; deterministic normalized local embeddings.
- OpenCode DeepSeek answer provider: exact model/session body, grounded/no-tool prompt, success text, timeout/provider error, extractive fallback, aliases and allow-list; all subprocess calls mocked.
- page extraction enrichment: save/upsert, rendered-page SHA-256, project/document/page scope, verify/reject with note, and proof that invented extraction text does not enter retrieval.
- POC tile helpers: page coverage/overlap/title block, full-page metadata priority, dedupe/warnings/confidence, tile crop-noise filtering while keeping full-page warnings, schema validation, numeric/unit cross-check (`87140` vs `87440`, `mm` vs `cm`) with exact dedupe and 20-warning cap.
- per-project/user rate limit returns 429 with `Retry-After`.

Frontend verification:

```bash
cd frontend
./node_modules/.bin/tsc --noEmit --jsx react-jsx --module esnext \
  --moduleResolution bundler --target es2022 --strict --skipLibCheck \
  --lib ES2022,DOM,DOM.Iterable src/features/engineering-ai/index.ts
```

Result this pass: Engineering AI feature type-checks cleanly (`exit 0`). Full `npm run build` also passed after the site changes (vite build, no errors).

Full-suite note: the coordinator gate now passes `171 passed` with a temporary DB/storage (`scripts/verify_all.sh`); this includes acceptance, site, engineering AI and the addendum DoD test.

## Dependencies

- Backend: FastAPI, SQLAlchemy 2, PyMuPDF (`pymupdf`/`fitz`), python-multipart, httpx (optional external providers), sqlite-vec, pytest.
- System: optional Tesseract OCR binary; `vie` traineddata for Vietnamese scans. Tested with Tesseract 5.5.4 and `TESSDATA_PREFIX=/home/thangpham/.local/share/tessdata`. Optional `opencode` CLI only when `ENGINEERING_AI_PROVIDER=opencode_deepseek`; no model key is stored by this module.
- `sqlite-vec` is used for persistent KNN when available; JSON vectors and the lexical ranker remain fallback. FTS5 is used when available; retrieval falls back to Python lexical/vector ranking otherwise.
- Frontend: React/TypeScript/Vite/Tailwind (shared scaffold), browser `fetch`/`FormData`/object URLs.

## Unresolved issues

- Page-extraction verify/reject currently checks project access/membership, not a dedicated reviewer role; coordinator should map it to shared role policy. Re-saving the same unique extraction resets it to `proposed` and clears prior verification.
- Verified extraction is intentionally not merged into retrieval/citation text yet; only the original page/chunk text is cited. A future coordinator decision must define how verified enrichment is exposed without replacing source text.
- **Chat (2026-11-23) no longer uses raw OCR/chunk retrieval at all.** Generic chat now answers from `PageExtraction` structured data (verified preferred, proposed labelled) and from the component DB; `/ai/search` and inspection checklists still use page/chunk retrieval. `record_id` is kept in conversation message JSON but not in the `AICitation` table (no migration was taken by this agent).
- The OpenCode DeepSeek path has no real-model integration test by design; tests mock `_opencode_call`. Coordinator must run one live smoke with `ENGINEERING_AI_PROVIDER=opencode_deepseek` and the OpenCode service authenticated.
- Real-scan ingest is not executed yet. Required before it: raise `ENGINEERING_AI_MAX_PDF_BYTES` above 66,405,004 B (recommended 70 MiB), raise reverse-proxy/body limits, and reserve ~1 GB storage for OCR renders/originals.
- Real scans are available but not ingested; only four pages and a temporary 2-page cut were measured. No verified project knowledge exists yet.
- OCR confidence is Tesseract word-average; it is not a calibrated probability. Drawing samples measured 0.67–0.69, so engineers must visually verify dimensions and notes; low-confidence pages always require direct drawing review.
- Answer confidence is heuristic, not an engineering validation.
- The default embedder is local feature hashing, not a trained multilingual model.
- In-process rate limiting does not coordinate across workers.
- Retrieval currently loads the project's current chunks and embeddings in memory for hybrid scoring; an ANN/segment index will be needed for very large document sets.
- Version allocation uses a unique `(project_id, document_key, version)` constraint plus bounded retry; the Codex migration must preserve that constraint, and a concurrent race after retries returns 409 for client retry.
- Module tables and addendum columns are present in Alembic head `c7d41f2b9a10`. FTS5 (`engineering_ai_chunks_fts`) and sqlite-vec `vec0` tables are created lazily during ingest and are not in the migration; the first real ingest will add virtual tables inside `data/app.db`. Pre-create them in migration/script if schema changes must be Alembic-only.
- `effective` confirmation currently checks project access/membership, not a specific document-manager role; coordinator should map it to the shared role policy if required. Uniqueness is enforced by the confirmation service, not a DB constraint; concurrent confirmations for the same document family should be serialized by the coordinator.
- Version compare reports text-character/page/chunk/table statistics and detects page-text equality changes; it is not a semantic design diff and does not identify which revision is correct.
- Vision requires an existing rendered page for the top-1 chunk; native-text pages without a render skip Vision with a warning. It is opt-in and never receives the full PDF.
- The grounding gate compares provider values against the displayed citation quote, not the entire page. This is deliberately conservative: a real value outside the quote is rejected rather than accepted without visible evidence. Unit equivalence is formatting-only; no mm↔cm conversion is performed.
- Cross-reference suggestions are deterministic and only compare explicit numeric/unit/grade differences in lexically overlapping sentences. They cannot detect prose contradictions, missing requirements, cross-language differences or drawing/specification relationships that do not share tokens. There is no automatic full-document pair discovery; the user selects the two pages. Every result remains `needs_engineer_review` and must not be treated as a design conclusion.
- Daily-report draft linked mode reads Site Report ORM tables directly and assumes the shared DB/Base; the inline `report` mode avoids that coupling. Missing-field rules are heuristic and never auto-fill values; the draft is not saved.
- Inspection checklist suggestions are lexical review prompts, not a semantic checklist generator. They do not persist checklist rows, do not set acceptance states, and cannot guarantee that every relevant requirement is found. Engineers must add/verify items and perform the inspection.
- Citation `url` is an API path; the frontend fetches render/original with the bearer token as a blob because private files are not static mounts.
- Provider prompt hardening reduces but cannot mathematically guarantee external-model grounding; the service therefore requires `[n]` citations and falls back to extractive text otherwise.

## Run instructions

1. Backend deps: `../.venv/bin/pip install -r backend/requirements.txt` (including `sqlite-vec`); verify `select vec_version()`.
2. Run module tests: `cd backend && ../.venv/bin/python -m pytest tests/engineering_ai -q`.
3. Integration: Codex mounts the router; no standalone main edit is made by this agent.
4. Set `ENGINEERING_AI_STORAGE` to a protected absolute path in deployment.
5. Optional OCR: install Tesseract + Vietnamese data, verify `tesseract --list-langs` includes `vie`. Without it OCR retries `eng` and marks pages for manual review.
6. Optional model provider: set all `ENGINEERING_AI_*` provider variables server-side; leave them unset for the offline extractive mode.
7. Frontend: `cd frontend && npm run dev` after wiring `EngineeringAIPage` into the app shell.
