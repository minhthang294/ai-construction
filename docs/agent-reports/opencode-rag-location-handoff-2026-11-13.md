# OpenCode handoff: RAG pile/beam location QA

Continue the RAG location lookup work in this repository. Preserve the current working tree and do not discard existing changes.

## User's reproduced failure

The chat returned “Không tìm thấy thông tin...” for:

`cầu chính, cọc nhóm 2 cần sửa gồm những cọc nào`

Root cause: pile group lookup read only `proposed` page extractions, so it skipped page 8 after page 8 became `verified`. The remaining group 2 table pages often put location in the page summary, not in table rows. The current patch merges verified component facts with exact proposed table rows and uses page summary location only as unverified evidence.

## Current local changes to review

- `backend/app/engineering_ai/component_search.py`: group-only verified fact lookup is allowed.
- `backend/app/engineering_ai/pile_group_lookup.py`: infer page-level location from title/summary; keep row-level segment where present.
- `backend/app/engineering_ai/component_chat.py`: combine verified and proposed pile codes, remove non-pile pseudo-codes and duplicates, show source status separately, cite source pages.

Manual replay on the live project DB now returns 45 verified codes and 46 additional AI-proposed codes from pages 8–9 for Cầu chính, group 2. Seventeen proposed codes still have no known segment. Do not present the proposed set as verified or as an official total. Inspect whether all 46 codes really belong to the queried bridge against the source page images; page-summary location inference is a heuristic and should be replaced with direct visual/source mapping where possible.

## Next steps

1. Review the diff and exact source pages 8–9, especially codes with unknown segment and any repeated code.
2. Improve mapping so each returned code has its correct group, bridge, segment, and page/table row; abstain on conflicting or uncertain rows.
3. Confirm the exact user question returns a useful list with citations, and verify “cọc nhóm 2 cần sửa ở cầu dẫn” stays separate.
4. Check beam location lookups still work; Q-295 is extracted on page 103 as group 1 / PĐ12 / Cầu dẫn, proposed and unverified.
5. Run the relevant tests after fixing; do not alter extraction verification status or the real database to make a test pass.

The backend is currently running on port 8765 with OpenCode DeepSeek configured. Reload it after changes and check `/health`.
