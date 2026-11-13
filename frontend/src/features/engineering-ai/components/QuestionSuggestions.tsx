import { useEffect, useMemo, useState } from "react";
import {
  QUESTION_CATEGORIES,
  QUESTION_SUGGESTIONS,
  suggestionBadgeLabel,
  suggestionsForCategory,
  type QuestionCategoryId,
  type QuestionSuggestion,
} from "../lib/questionSuggestions";
import { cx, FIELD_BASE, META_TEXT } from "../lib/ui";
import { SearchIcon } from "./icons";

type Props = {
  busy: boolean;
  compact?: boolean;
  onPick: (suggestion: QuestionSuggestion) => void;
};

const BADGE_STYLES: Record<
  NonNullable<QuestionSuggestion["badge"]>,
  string
> = {
  verified: "border-emerald-200 bg-emerald-50 text-emerald-800",
  proposed: "border-amber-200 bg-amber-50 text-amber-800",
  navigation: "border-[#405e9b]/20 bg-white text-[#35507f]",
  caution: "border-red-200 bg-red-50 text-red-800",
};

function SuggestionButton({
  suggestion,
  busy,
  onPick,
}: {
  suggestion: QuestionSuggestion;
  busy: boolean;
  onPick: (suggestion: QuestionSuggestion) => void;
}) {
  const badge = suggestionBadgeLabel(suggestion.badge);
  return (
    <button
      type="button"
      onClick={() => onPick(suggestion)}
      disabled={busy}
      title={
        suggestion.mode === "fill"
          ? "Điền câu hỏi vào ô nhập để bạn đổi mã cọc/dầm"
          : "Gửi câu hỏi này ngay"
      }
      className="group flex min-h-11 max-w-full items-start gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-left text-xs leading-5 text-slate-700 transition-colors hover:border-[#405e9b]/40 hover:bg-[#405e9b]/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#405e9b] disabled:cursor-not-allowed disabled:opacity-60"
    >
      <span className="min-w-0 [overflow-wrap:anywhere]">{suggestion.label}</span>
      {badge && (
        <span
          className={cx(
            "shrink-0 rounded-full border px-1.5 py-0.5 text-[10px] font-medium",
            BADGE_STYLES[suggestion.badge!],
          )}
        >
          {badge}
        </span>
      )}
      <span
        aria-hidden="true"
        className="ml-auto shrink-0 text-slate-400 group-hover:text-[#405e9b]"
      >
        {suggestion.mode === "fill" ? "Sửa" : "Gửi"}
      </span>
    </button>
  );
}

export default function QuestionSuggestions({
  busy,
  compact = false,
  onPick,
}: Props) {
  const [activeCategory, setActiveCategory] =
    useState<QuestionCategoryId>("location");
  const [open, setOpen] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [query, setQuery] = useState("");

  const visible = suggestionsForCategory(activeCategory).slice(
    0,
    compact ? 4 : 8,
  );
  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return QUESTION_SUGGESTIONS;
    return QUESTION_SUGGESTIONS.filter(
      (item) =>
        item.label.toLowerCase().includes(needle) ||
        item.prompt.toLowerCase().includes(needle),
    );
  }, [query]);

  useEffect(() => {
    if (!modalOpen) return;
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setModalOpen(false);
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [modalOpen]);

  function pick(suggestion: QuestionSuggestion) {
    onPick(suggestion);
    setModalOpen(false);
  }

  return (
    <>
      <section
        aria-label="Gợi ý câu hỏi"
        className="rounded-xl border border-[#405e9b]/20 bg-[#405e9b]/5 p-3"
      >
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h3 className="text-xs font-semibold uppercase tracking-[0.12em] text-[#35507f]">
              Gợi ý câu hỏi
            </h3>
            <p className={cx(META_TEXT, "mt-0.5")}>
              Chọn mẫu để hỏi nhanh. Câu có mã sẽ điền vào ô nhập để bạn đổi mã.
            </p>
          </div>
          <div className="flex shrink-0 gap-1">
            <button
              type="button"
              className="min-h-9 rounded-md px-2 text-xs font-medium text-[#35507f] hover:bg-white/70"
              onClick={() => setOpen((value) => !value)}
            >
              {open ? "Thu gọn" : "Mở"}
            </button>
            <button
              type="button"
              className="min-h-9 rounded-md px-2 text-xs font-medium text-[#35507f] hover:bg-white/70"
              onClick={() => setModalOpen(true)}
            >
              Xem tất cả
            </button>
          </div>
        </div>

        {open && (
          <>
            <div className="mt-3 flex gap-1 overflow-x-auto pb-1">
              {QUESTION_CATEGORIES.map((category) => {
                const active = category.id === activeCategory;
                return (
                  <button
                    key={category.id}
                    type="button"
                    aria-pressed={active}
                    onClick={() => setActiveCategory(category.id)}
                    className={cx(
                      "min-h-9 shrink-0 rounded-full border px-3 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#405e9b]",
                      active
                        ? "border-[#405e9b] bg-[#405e9b] text-white"
                        : "border-slate-200 bg-white text-slate-600 hover:border-[#405e9b]/40",
                    )}
                  >
                    {category.label}
                  </button>
                );
              })}
            </div>
            <div className="mt-2 flex flex-wrap gap-2">
              {visible.map((suggestion) => (
                <SuggestionButton
                  key={suggestion.id}
                  suggestion={suggestion}
                  busy={busy}
                  onPick={pick}
                />
              ))}
              {visible.length === 0 && (
                <p className={META_TEXT}>Chưa có câu hỏi mẫu trong nhóm này.</p>
              )}
            </div>
          </>
        )}
      </section>

      {modalOpen && (
        <div
          className="fixed inset-0 z-50 flex items-end justify-center bg-slate-950/50 p-3 sm:items-center"
          role="presentation"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) setModalOpen(false);
          }}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="eai-question-library-title"
            className="flex max-h-[88vh] w-full max-w-3xl flex-col overflow-hidden rounded-2xl bg-white shadow-xl"
          >
            <div className="flex items-start justify-between gap-3 border-b border-slate-200 p-4">
              <div>
                <h2
                  id="eai-question-library-title"
                  className="text-base font-semibold text-slate-950"
                >
                  Thư viện câu hỏi mẫu
                </h2>
                <p className={cx(META_TEXT, "mt-1")}>
                  Chọn theo việc thực tế: vị trí, kích thước, quy trình, mở trang,
                  nguồn và thuyết minh.
                </p>
              </div>
              <button
                type="button"
                className="min-h-10 shrink-0 rounded-lg border border-slate-200 px-3 text-sm text-slate-600 hover:bg-slate-50"
                onClick={() => setModalOpen(false)}
              >
                Đóng
              </button>
            </div>

            <div className="border-b border-slate-200 p-4">
              <label htmlFor="eai-question-library-search" className="sr-only">
                Tìm câu hỏi mẫu
              </label>
              <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3">
                <SearchIcon className="h-4 w-4 shrink-0 text-slate-400" />
                <input
                  id="eai-question-library-search"
                  className={cx(FIELD_BASE, "border-0 py-2 shadow-none")}
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Tìm theo mã, nhóm, quy trình, mở trang..."
                />
              </div>
            </div>

            <div className="overflow-y-auto p-4">
              {QUESTION_CATEGORIES.map((category) => {
                const items = filtered.filter(
                  (item) => item.category === category.id,
                );
                if (items.length === 0) return null;
                return (
                  <section key={category.id} className="mb-5 last:mb-0">
                    <div className="mb-2">
                      <h3 className="text-sm font-semibold text-slate-900">
                        {category.label}
                      </h3>
                      <p className={META_TEXT}>{category.description}</p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {items.map((suggestion) => (
                        <SuggestionButton
                          key={suggestion.id}
                          suggestion={suggestion}
                          busy={busy}
                          onPick={pick}
                        />
                      ))}
                    </div>
                  </section>
                );
              })}
              {filtered.length === 0 && (
                <p className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-600">
                  Không tìm thấy câu hỏi mẫu phù hợp.
                </p>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
