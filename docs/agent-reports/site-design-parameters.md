# Design parameters for pile stages (`t_cm`)

**Task:** show the actual per-pile thickness `t` from reviewed design tables in stage names, instead of the truncated generic `... trung bình t`.

**Source (private, reviewed, not committed):**
`data/storage/design-review/DAP-coc-thong-so-TK19-TK25.csv`
· 393 data rows · sha256 `62e28912392c…` (full hash stored in DB provenance)
· `;` separated, decimal comma · TK-19 (group II) and TK-25 (group III).

No source file, source rows or private path were copied into the repository. Only numeric values and provenance fields (drawing/page/row/hash) are stored.

## Schema

One migration on top of `a1b2c3d4e5f6`:

- `b7c8d9e0f1a2_component_design_parameters.py`
- `component_design_parameters`:
  `id`, `project_id`, `component_id`, `name`, `value`, `unit`,
  `source_drawing`, `source_page`, `source_row`, `source_file_hash`,
  `created_by`, `created_at`; unique `(component_id, name)`, indexes on project/component.
- Downgrade drops table and indexes.
- Model `ComponentDesignParameter` in `backend/app/core/component_models.py`.

## Import CLI

`scripts/import_design_parameters.py`

```bash
python scripts/import_design_parameters.py \
  --database sqlite:///path/app.db \
  --project "DAP - PD1 da duyet (du lieu thuc te)" \
  --csv "…/DAP-coc-thong-so-TK19-TK25.csv" \
  [--actor demo] [--commit]
```

- Dry-run by default, prints counts/lists, never writes.
- Matches `code_printed` + `zone_printed` against canonical codes, raw codes and aliases, pile components only, project-scoped.
- Reports unmatched, ambiguous (never auto-picks), invalid numeric, and conflicting duplicate rows. A pile with different values for the same parameter is skipped and listed.
- Names imported: `L1_m`, `L2_m`, `L3_m`, `L4_m`, `t_cm`, `n`, `a_mm`, `b_m`; empty values are skipped so missing `t` stays missing.
- Commit is idempotent: identical existing rows are unchanged; a different stored value is a conflict and is never overwritten. Missing rows are inserted in one transaction with one audit entry (`component_design_parameters_imported`).
- Preview tolerates a database that has not yet run the new migration; commit requires the table.

### Preview against the read-only real-data copy

Command target: `C:/Users/Thang Minh Pham/.claude/jobs/0f99d406/tmp/mig/app.db`
(project `DAP - PD1 da duyet (du lieu thuc te)`, **no --commit**):

- CSV rows: **393**
- Matched: **392 rows / 392 piles**, **390 piles with `t_cm`**
- Parameters planned: **2,525** (unchanged: 0, table not yet migrated in that copy)
- **Unmatched: 1** — `Cầu chính / M263` (TK-25, page 31, source row 6)
- Ambiguous: **0**
- Conflicts: **0**
- Invalid numeric: **0**
- Missing `t` in source (other params still import): `A162`, `A163` (TK-25 page 31 row 39, `THICKNESS_MISSING_IN_SOURCE`)

The CLI reported “table missing; commit requires migration” as expected; no row was written to the copy.

## Display helper

`backend/app/core/design_parameters.py`:

- `display_stage_name("Đục bê tông om vỡ dày trung bình t", [3])`
  → `Đục bê tông om vỡ dày trung bình t = 3 cm`
- Multiple values → `… t = 2–5 cm`
- Missing value → `… t (chưa có số liệu)`
- Names not ending in `t` / not containing `trung bình t` are unchanged.
- `load_t_values`, `load_parameters` are project/component scoped.

Applied in:

- Component detail `stages[].name`, `progress_events[].stage_name`, new `design_parameters[]`
  (`backend/app/core/component_router.py`).
- Component progress history endpoint (`progress-events`) stage names.
- Site progress rows/stages, daily-preview `stage_display_name` per line
  (`backend/app/site/progress.py`).
- Journal preview/export event and work lines (`backend/app/site/progress.py`).
- Overview latest-day: groups by raw work + zone/segment/type/status; if t differs,
  `stage_name` shows range and `codes[]` includes per-code `(t = … cm)`.
  Missing values annotate `(chưa có số liệu)`.
- Drawing-map popup `current_work`.
- Frontend paste-message review shows `stage_display_name`; Zalo summary uses it.
- Progress history UI shows the stage display name.

## Tests run

```bash
cd backend
DATABASE_URL="sqlite:///$TEMP/design-params-test.db" \
SITE_REPORT_STORAGE="$TEMP/design-site" ACCEPTANCE_STORAGE="$TEMP/design-acc" \
  ../.venv/Scripts/python -m pytest \
  tests/test_design_parameter_import.py tests/test_design_parameters_api.py \
  tests/test_component_migration.py -q
# 8 passed
```

Coverage:

- `tests/test_design_parameter_import.py`: preview counts, alias matching, commit,
  idempotent rerun, audit, unmatched, ambiguous, conflicting duplicate rows, and
  existing-value conflict without overwrite.
- `tests/test_design_parameters_api.py`: display helper single/range/missing;
  component detail parameters + stage name; overview range grouping with per-code
  values; daily-preview `stage_display_name`; journal per-pile stage names.
- `tests/test_component_migration.py`: new migration round trip on a temp DB
  (upgrade head → downgrade -1 → upgrade head) preserving existing component data.

Full backend and frontend gates are listed in the site report for this wave.
- Full backend: **361 passed, 6 skipped**.
- Frontend: **210 tests passed**, `npm run build` OK.

## Notes / unresolved

- `M263` is not in the current project catalog; owner should confirm whether it is a
  typo or a missing pile. It was not imported.
- `A162`/`A163` have no thickness in the reviewed source; their other parameters are
  imported and the stage name shows `(chưa có số liệu)`.
- Group I piles (no `t` column) remain outside this CSV and show “chưa có số liệu”
  when they use a `t`-named stage.
- Import matching uses exact zone + code/alias. Any future alias/zone edits require
  a fresh preview; existing values are never silently overwritten.
- The real-data copy is read-only for this task; commit should be run on a migrated
  application DB after owner approval.
