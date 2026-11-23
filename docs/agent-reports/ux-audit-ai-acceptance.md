# UX audit — Hỏi AI & Nghiệm thu (field engineer, 390 px / 1440 px)

Read-only audit. Scope: `frontend/src/features/engineering-ai`,
`frontend/src/features/acceptance`, `frontend/src/style.css`,
`frontend/src/ui`. Screenshots: `phone-4-*` (Hỏi AI), `phone-3-*`
(Nghiệm thu), `phone-0-top` (Tổng quan entry points), `desktop-3/4-*`.
No code was changed.

Persona assumption: gloves, sun glare, weak signal, one hand, end of day;
already wrote progress in Zalo; still must produce nhật ký and PYC/BBNT.

## Top 10 problems (ranked by field impact)

### 1. Hỏi AI opens on marketing copy; the composer is below the first phone screen
- **Screen:** Hỏi AI, 390 px (`phone-4-top.png`).
- **Evidence:** first 844 px contains brand bar, a large
  “Hỏi đáp AI hồ sơ kỹ thuật” card, a warning, then a second card titled
  “Hỏi đáp có citation”; no input, no suggestion chip.
  `pages/EngineeringAIPage.tsx:102-145`, `components/ChatPanel.tsx:313-323`.
  The composer is only reached after scrolling (`ChatPanel.tsx:451-508`).
- **Impact:** the primary action (ask/paste) is invisible; a one-handed user
  with gloves must scroll before typing. Daily Q&A costs 2 navigations + scroll.
- **Fix:** replace the hero with a single compact title row (project already
  shown in the app bar); put the composer and 3 suggestion chips directly under
  the page title; move explanatory copy behind an “i” disclosure.
- **Effort:** S.

### 2. The approved paste-Zalo → preview → answer → save flow is absent from Hỏi AI
- **Screen:** Hỏi AI (`phone-4-full.png`) vs Tổng quan (`phone-0-top.png`).
- **Evidence:** chat only offers free text and generated Q&A chips
  (`ChatPanel.tsx:468-474`, `components/QuestionSuggestions.tsx:66-100`).
  The paste entry exists only as a quick card on Tổng quan; there is no
  “Dán tin nhắn hôm nay” action, no preview, no review questions and no save
  path inside the chat screen. Acceptance is a separate tab with no hand-off.
- **Impact:** the day-entry goal (< 2 minutes) cannot be completed from the
  chat surface; the engineer still juggles Hỏi AI, Hiện trường, and Nghiệm thu.
- **Fix:** make “Dán tin nhắn Zalo” the first composer action in Hỏi AI, running
  the existing `progress-parse` preview and question chips inline; after save,
  surface the generated Zalo summary + links to journal/PYC.
- **Effort:** M (backend exists; UI/workflow wiring only).

### 3. Nghiệm thu has no “pending acceptance today” queue
- **Screen:** Nghiệm thu (`phone-3-top.png`, `phone-3-full.png`).
- **Evidence:** page opens with tab toggle, “+ Tạo PYC nháp”, an empty PYC card,
  then participant/numbering/history setup (`pages/AcceptancePage.tsx:768-991`,
  `1287-1299`). Nothing is derived from today’s completed progress or from the
  chat/field entry; BBNT is only reachable by choosing a PYC
  (`AcceptancePage.tsx:995-1021`).
- **Impact:** after recording progress, the engineer must remember what needs
  acceptance, re-find the work item and rebuild context. This is a direct cause
  of forgotten PYC/BBNT and late nhật ký.
- **Fix:** add a top section “Chờ nghiệm thu hôm nay” driven by the latest
  progress/acceptance links, with one tap to pre-filled PYC/BBNT; show a count
  badge on the Nghiệm thu nav item.
- **Effort:** M–L (needs a read-only pending queue API).

### 4. PYC/BBNT forms are long and their save action is at the bottom; success
feedback appears at the top
- **Screen:** Nghiệm thu → Tạo PYC / Lập BBNT (`phone-3-full.png`,
  `desktop-3-top.png`).
- **Evidence:** `components/RequestForm.tsx:303-665` has 20+ inputs in one
  scroll with submit at line 661; BBNT has participants, checklist, notes and
  save/confirm/export at `AcceptancePage.tsx:1185-1275`. The success/error banner
  is rendered above the form (`AcceptancePage.tsx:794-799`), while save happens
  at the bottom (`saveRecord`, `:525-552`).
- **Impact:** after a long scroll the engineer cannot see whether the save
  worked; on glare/weak signal this invites double taps and duplicate records.
  Creating PYC becomes a 5+ minute form, not a 30-second task.
- **Fix:** three-step wizard (Thông tin → Người ký → Xem lại/Xuất) with a sticky
  bottom bar (Lưu nháp / Tiếp tục / Xuất); show inline toast next to the bar;
  collapse optional/prefilled fields under “Tùy chọn”.
- **Effort:** M.

### 5. “Chưa có hồ sơ nguồn … không trả lời được” contradicts the data that is available
- **Screen:** Hỏi AI (`phone-4-top.png`).
- **Evidence:** warning says every technical question will be refused when the
  project has no PDFs (`EngineeringAIPage.tsx:140-143`), yet the same page shows
  real suggestions such as “PD1: còn 33/45 cọc chưa đục bê tông” and
  “Tiến độ ngày 22/11?” (`phone-4-full.png`) from the component/progress DB.
- **Impact:** the engineer may believe chat is broken and stop using it; or
  distrust a correct answer because the banner says it is impossible.
- **Fix:** derive the banner from `/ai/question-suggestions` / DB availability:
  “Chưa có bản vẽ nguồn; vẫn trả lời được từ database cấu kiện và tiến độ.”
  Only use the refusal copy when both sources are empty.
- **Effort:** S.

### 6. Touch targets and text are too small for gloves/outdoors
- **Screens:** Hỏi AI chips/citations, Nghiệm thu history.
- **Evidence:** suggestion chips `min-h-10` (40 px) and 10 px badges
  (`QuestionSuggestions.tsx:83-95`); citation actions `min-h-9` (36 px)
  (`CitationCard.tsx:62-78`); history “Mở PYC/BBNT” is `px-2 py-1` ≈28 px
  (`AcceptanceHistoryPanel.tsx:124-130`); many metadata/badges use 10–11 px.
- **Impact:** misses and accidental taps, especially one-handed with gloves;
  badges and stage/status labels are unreadable in sun glare.
- **Fix:** enforce 44×44 px minimum on every interactive control; 12 px minimum
  for helper text, 14 px for status labels; increase chip padding and border.
- **Effort:** S.

### 7. Nghiệm thu is cluttered with duplicated and administrative UI
- **Screen:** Nghiệm thu (`phone-3-top.png`, `phone-3-full.png`).
- **Evidence:** two tab buttons look like primary actions
  (`AcceptancePage.tsx:776-791`); the empty “Danh sách PYC” card repeats the
  create action (`:893-895`); the BBNT tab re-lists the same PYC list
  (`:995-1021`); participant library, numbering configuration and history are
  permanently on the main page (`:991`, `:1287-1299`). There is no BBNT list —
  only a work-item selector inside history.
- **Impact:** the daily action is buried in settings; the engineer cannot tell
  where PYC ends and BBNT begins; long page on a phone.
- **Fix:** tabs become a proper segmented control with `aria-pressed`; remove
  empty cards (use a one-line empty hint); move numbering/participant library to
  “Cài đặt nghiệm thu”; add a records list with status chips.
- **Effort:** M.

### 8. Low-contrast secondary/disabled states outdoors; colour semantics are inconsistent
- **Screens:** both.
- **Evidence:** global disabled buttons drop to `opacity: .55`
  (`style.css:78-81`), making “Gửi”, “Đổi tên”, “Xóa” almost invisible
  (`ChatPanel.tsx:326-340`, `:500-508`, screenshot `phone-4-top.png`). Metadata
  uses `text-slate-500` on white; badges are pastel at 10 px. Brand tokens are
  named `teal-*` but map to blue `#405e9b` (`style.css:3-9`), acceptance uses
  `teal-700` while engineering hardcodes `#405e9b`; “emerald” means both
  verified (chat) and confirmed/approved (acceptance), while “sky” means PYC.
- **Impact:** disabled actions look like rendering bugs; statuses are hard to
  distinguish in sunlight; future theme changes will split the two screens.
- **Fix:** hide unavailable actions instead of disabling, or keep text ≥4.5:1;
  define shared semantic tokens (`--status-verified`, `--status-pending`,
  `--status-rejected`, `--status-construction`) and a visible legend; rename
  the blue token, stop hardcoding hex in features.
- **Effort:** S–M.

### 9. Save feedback is out of view and empty states flash during loading
- **Screens:** Nghiệm thu, Hỏi AI.
- **Evidence:** acceptance shows “Chưa có PYC.”/“Chưa có …” while lists are
  still loading (`AcceptancePage.tsx:893-895`, `995-1000`), and success/error
  banners sit at page top (`:794-799`) while the save button is at the bottom.
  Chat history renders “Chưa có hội thoại.” before the fetch completes
  (`ChatPanel.tsx:280-283`); chat errors do offer “Thử lại”
  (`ChatPanel.tsx:452-466`), acceptance does not retry inline.
- **Impact:** users think data disappeared or that save failed, then retry.
- **Fix:** skeletons/spinners for first load; empty state only after a
  successful fetch; sticky inline toast + retry for save/export failures;
  scroll/focus the new record after save.
- **Effort:** S.

### 10. Accessibility and dead-end actions
- **Screens:** both.
- **Evidence:** acceptance tab buttons expose no selected state
  (`aria-pressed`/tab semantics missing, `AcceptancePage.tsx:776-791`); the
  confirm dialog has `aria-modal` but no focus trap, initial focus or Escape
  handling (`ConfirmDialog.tsx:59-65`); `MenuButton` is a popover without
  `aria-haspopup`/menu roles (`ui/MenuButton.tsx:56-76`). Chat’s DB citation
  “Mở cấu kiện” dispatches a window CustomEvent with no guaranteed listener, so
  the button can silently do nothing (`EngineeringAIPage.tsx:72-78`).
- **Impact:** keyboard/screen-reader users cannot tell which tab is active or
  escape a modal; field staff see a button that appears dead.
- **Fix:** implement tablist/tab/tabpanel semantics; trap focus and close on
  Escape; add `aria-haspopup`; hide “Mở cấu kiện” unless the shell registers a
  handler (or provide an in-module component sheet fallback).
- **Effort:** S.

## Quick wins (≤1 day each)

1. Move composer + suggestion chips to the first screen of Hỏi AI; shrink the
   hero to one row and delete the duplicated “Hỏi đáp có citation” intro.
2. Fix the empty-source banner copy to reflect DB/progress availability.
3. Raise chips/citation/history actions to 44 px and 12–14 px text.
4. Hide “Đổi tên/Xóa” until a conversation exists; hide disabled “Gửi” label
   or keep contrast.
5. Sticky save bar for PYC/BBNT + inline toast; keep error next to the action.
6. Move numbering + participant library into a collapsible “Cài đặt”.
7. Remove “Danh sách PYC” empty card, replace with one line under the create
   button.
8. Add `aria-pressed`, focus trap/Escape, and `aria-haspopup` (finding 10).
9. Replace English status strings in lists (`draft`, `submitted`, `confirmed`,
   `revision`) with Vietnamese labels and a legend
   (`AcceptancePage.tsx:904`, `:1007`, `AcceptanceHistoryPanel.tsx:118-120`).
10. Precompute `recordsByRequest` instead of `records.find` inside every row
    (`AcceptancePage.tsx:342-344`, used at `:898`, `:1003`); add list pagination
    or “load more” for large projects.
11. Unify terminology: chat “bước”/“công đoạn”, acceptance “công việc”;
    translate “citation” to “nguồn trích dẫn” in field-facing copy.

## Larger redesign proposals

### A. “Hôm nay” sheet as the primary day workflow
One screen: paste Zalo text → map/list preview with pile chips → answer only
ambiguous points with buttons → save → immediately show the generated Zalo
summary + “Nhật ký đã tạo” + “PYC cần lập”. Hỏi AI becomes an assistant drawer
inside this flow, not a destination tab. This directly serves the <2 minute goal
and removes the Tổng quan/Hiện trường/Hỏi AI/Nghiệm thu hop chain.

### B. Acceptance driven by map/component, not by PYC list
Show a “Chờ nghiệm thu” badge/count on map markers and a bottom sheet per pile:
timeline of progress, “Lập PYC”, “Lập BBNT”, prefilled from the latest progress
event and daily report. The Nghiệm thu tab becomes a queue + search, with the
numbering/participant admin moved to settings.

### C. Chat as context assistant
Open Hỏi AI from a selected pile/page with contextual chips (“Vì sao cọc này
chưa xong?”, “Mở bản vẽ nhóm 2”), keep the conversation in a side panel on
desktop and a bottom sheet on phone; citations open the page in a split view.
Remove the marketing header and the global empty-state warning; show source
types as chips (database / extraction / drawing).

### D. Shared field design system
One set of tokens for construction vs acceptance status colours, 44 px touch
targets, 12/14/16 px type scale, outdoor-contrast helpers, and Vietnamese
status labels. Replace the `teal-*` names that render blue, and remove
feature-local hardcoded brand hex so both screens stay consistent.

## Notes

- No legacy work-item cards or double daily-report cards were present inside
  the two audited screens; the duplication here is PYC/BBNT lists and the
  create button/empty card.
- Big-list risk: acceptance requests/records are fetched without paging and
  `recordFor` is O(n²); the chat conversation list is also unpaginated.
- Map-first is not visible on either audited screen; only Tổng quan links to
  map/field work. Moving the day entry into a map/component context is the
  largest product-level improvement.
