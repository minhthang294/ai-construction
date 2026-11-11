# Engineering AI Agent Report

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
- `backend/app/engineering_ai/service.py` (new)
- `backend/app/engineering_ai/router.py` (new)
- `backend/app/engineering_ai/dependencies.py` (extended with `project_access`, OCR/language/page-limit getters)
- `backend/app/engineering_ai/models.py` (addendum fields `change_note/is_effective/effective_at/effective_by`, `tables_json`, `section`; unique project/key/version constraint)
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
| `ENGINEERING_AI_PROVIDER` | `extractive` | `openai_compatible` enables external chat |
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

## Tests

Command:

```bash
cd backend
../.venv/bin/python -m pytest tests/engineering_ai -q
```

Result this pass: **47 passed** (1 third-party Starlette/httpx deprecation warning).

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
- System: optional Tesseract OCR binary; `vie` traineddata for Vietnamese scans. Tested with Tesseract 5.5.4 and `TESSDATA_PREFIX=/home/thangpham/.local/share/tessdata`.
- `sqlite-vec` is used for persistent KNN when available; JSON vectors and the lexical ranker remain fallback. FTS5 is used when available; retrieval falls back to Python lexical/vector ranking otherwise.
- Frontend: React/TypeScript/Vite/Tailwind (shared scaffold), browser `fetch`/`FormData`/object URLs.

## Unresolved issues

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
