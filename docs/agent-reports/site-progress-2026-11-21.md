# Site progress entry — 2026-11-21, Cầu chính / Đoạn 2

Data-entry record only. No application code, migration, Excel source or other agent module was edited.

## Project and work

- Project: `DAP - PD1 da duyet (du lieu thuc te)` (`be9701c9-dbe2-4bcd-9f37-082a82f03c14`)
- Zone: `Cầu chính` (`name_key = cầu chính`)
- Segment: 2 (`c2f676d1-c961-4ec2-8c29-6cd2b66d3d8b`)
- Work: stage definitions whose name starts with `Đục bê tông om vỡ`
- Status: `COMPLETED`
- Piles: F67, F64, F57, F55, F54, G65, G62, G50, H65, H62, H53, H50, B153, B155 (14)
- No quantity, unit, note, evidence/photo or acceptance data was entered.

## Preconditions

- Alembic `current` on `data/storage/demo-live/app.db`: `639cdb146bf2 (head)`
- Alembic `heads`: `639cdb146bf2 (head)` → equal, proceeded.
- Backup: `data/storage/demo-live/backups/app-before-progress-2026-11-21.db`
  - created with the sqlite3 backup API, 22,458,368 bytes
  - reopened successfully: `PRAGMA integrity_check = ok`, 45 tables
- Actor: user `demo` (`5989bfac-5bee-4b3d-9cd4-4c17f65499b2`), role `admin`, project role `project_manager` on this project.
- Code path: `app.site.progress.preview_daily` then `app.site.progress.commit_daily`
  (`reviewed=True`, `idempotency_key = daily-2026-11-21-pd2-duc-om-vo`), with
  `DATABASE_URL` pointing at the target DB. No raw SQL INSERT was used.
- Helper scripts were kept outside the repository in the session temp folder.

## Stage mapping

Each pile has exactly one matching `Đục bê tông om vỡ` stage; no pile had 0 or >1
matching stages. The definition follows the pile's own repair design group.

| Repair group | Stage definition | Code | Position | Piles |
| --- | --- | --- | --- | --- |
| Nhóm II | `1d07eccd-9716-4c69-a598-3a69b9ce1523` | `DAP-745dd3fcace69f1243ff` | 2001 | F54, F55, F64, G50, G62, G65, H53, H62, H65 |
| Nhóm III | `a2d5bdb9-7a2a-46b6-b599-59006972b931` | `DAP-f9a34bf871a858dabd58` | 2002 | F67, F57, H50, B153, B155 |

The `Đục bê tông om vỡ (phát sinh)` definition (`DAP-PS-DUC-BE-TONG`) is not
attached to any of these piles and was not used.

## Preview

Two lines, one per stage definition. Result: `can_commit = true`, 14 components,
9 + 5 ready, no warnings, no missing/ambiguous/invalid stage selections.

| Pile | Group | Component stage id |
| --- | --- | --- |
| F54 | Nhóm II | `7b58ac88-7038-47da-bf19-cabd05172065` |
| F55 | Nhóm II | `c3c0a2b5-b657-4b41-b9d9-9695a8a19e7f` |
| F64 | Nhóm II | `b8709a0a-3a02-4978-9c35-1aec093a0cf6` |
| G50 | Nhóm II | `fd3573b8-c298-4500-958b-f4e9c3a6f78d` |
| G62 | Nhóm II | `65365202-3d61-45bb-87d7-9262515417a0` |
| G65 | Nhóm II | `b6083691-0618-4fb9-96ed-8aa2adcaae31` |
| H53 | Nhóm II | `19ffc14a-90e5-4afe-a94a-acee89ef68dc` |
| H62 | Nhóm II | `760a34f6-ac3d-4178-be3f-67878d371451` |
| H65 | Nhóm II | `259a9c2b-44f0-42cb-a238-b536e4eb817e` |
| F67 | Nhóm III | `b65d4d50-91b4-429e-8839-180ddc557f0f` |
| F57 | Nhóm III | `cccb7a11-3112-47d3-a33d-48cebc0ffb97` |
| H50 | Nhóm III | `5a48860c-0608-4f23-9be3-e4ff24910d43` |
| B153 | Nhóm III | `2ab6ba7a-e27b-4c02-af70-5d647fa38e45` |
| B155 | Nhóm III | `2288cfc4-f051-4eef-ad04-15263a9be07d` |

## Commit

- Batch: `19c68eb9-4b67-452b-b9af-e103887ec3f5`
- Idempotency key: `daily-2026-11-21-pd2-duc-om-vo`
- Payload hash: `6c7e8ae06572e40306eb488d316a408f7f78a28ae5986e40d2c7889ceb03c617`
- Created: 14 events (9 + 5)
- Audit: `component_progress_daily_recorded` on `SiteProgressBulkBatch`, actor `demo`

| Pile | Event id |
| --- | --- |
| F54 | `7cb8af35-e329-4e3b-afb9-2fd882bb4043` |
| F55 | `6ab5b206-d5be-459e-8a8a-3033e88ce5bf` |
| F64 | `514bc02f-1945-4522-b8ed-f9d4f72b6ae9` |
| G50 | `4d094b9c-0d40-498f-8cbd-c77f937e468f` |
| G62 | `eb750aab-a758-4ad8-9a01-f72db9c401cf` |
| G65 | `170dc4aa-69a8-4372-ad38-b4631e04eacb` |
| H53 | `f1a0f2f3-a89d-46aa-a11a-616788ed0b9a` |
| H62 | `8525214b-18bb-405e-93b1-003fd63cab8f` |
| H65 | `b722b2e8-f92d-4ca7-b24a-526f046dd28a` |
| F67 | `3425fa67-47b7-4d08-a0d8-605f34eab015` |
| F57 | `6933745f-84ee-479c-9e45-d9a94a23d390` |
| H50 | `90a29e27-523b-408b-a298-11b682ad6271` |
| B153 | `08f387c3-2311-4665-9a7c-5a6bbcb9a936` |
| B155 | `ea4d5e22-b2f9-4bc9-a43c-b48ab43063e1` |

## Verification (read-only queries)

- 14 events dated `2026-11-21` in Cầu chính / segment 2, exactly the 14 requested
  piles, all `COMPLETED`, all quantity/unit/note null and evidence empty.
- 14 events dated `2026-11-21` created by actor `demo` (no other events that day).
- Acceptance tables compared against the pre-commit backup: all unchanged
  (`acceptance_requests`, `acceptance_records`, `acceptance_participants`,
  `acceptance_checklists`, `acceptance_number_sequences`,
  `acceptance_participant_profiles`, `component_acceptance_links`; 0 rows each
  before and after).
- Re-running `commit_daily` with the same idempotency key returned the stored
  result and created no new events (count stayed 14) and no new batch row.
