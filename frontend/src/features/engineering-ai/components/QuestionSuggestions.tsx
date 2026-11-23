import { cx, META_TEXT } from "../lib/ui";
import type { QuestionSuggestion } from "../types";
import { AlertIcon } from "./icons";

type Props = {
  suggestions: QuestionSuggestion[];
  loading: boolean;
  busy: boolean;
  onPick: (suggestion: QuestionSuggestion) => void;
};

const BADGE_STYLES: Record<string, string> = {
  verified: "border-emerald-300 bg-emerald-50 text-emerald-900",
  proposed: "border-amber-300 bg-amber-50 text-amber-900",
  navigation: "border-[#405e9b]/30 bg-white text-[#35507f]",
  caution: "border-red-300 bg-red-50 text-red-800",
};

const BADGE_LABELS: Record<string, string> = {
  verified: "Đã xác minh",
  proposed: "Chưa xác minh",
  navigation: "Mở trang",
  caution: "Cần đối chiếu",
};

export default function QuestionSuggestions({
  suggestions,
  loading,
  busy,
  onPick,
}: Props) {
  if (loading) {
    return (
      <div role="status" className={cx(META_TEXT, "flex items-center gap-2")}>
        Đang gợi ý câu hỏi từ dữ liệu công trình...
      </div>
    );
  }

  if (suggestions.length === 0) {
    return (
      <p className={cx(META_TEXT, "flex items-start gap-2")}>
        <AlertIcon className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" />
        Chưa có dữ liệu cấu kiện/tiến độ để gợi ý câu hỏi. Bạn vẫn có thể hỏi tự do.
      </p>
    );
  }

  return (
    <section aria-label="Gợi ý câu hỏi từ dữ liệu công trình">
      <h3 className="text-sm font-semibold text-[#35507f]">
        Hỏi nhanh từ dữ liệu công trình
      </h3>
      <div className="mt-2 flex gap-2 overflow-x-auto pb-1 lg:flex-wrap lg:overflow-visible">
        {suggestions.slice(0, 6).map((suggestion) => (
          <button
            key={suggestion.id}
            type="button"
            onClick={() => onPick(suggestion)}
            disabled={busy}
            title={
              suggestion.mode === "fill"
                ? "Điền câu hỏi vào ô nhập để bạn đổi mã cấu kiện"
                : "Gửi câu hỏi này ngay"
            }
            className="flex min-h-11 max-w-[85%] shrink-0 items-center gap-2 rounded-xl border border-slate-300 bg-white px-3 py-2 text-left text-sm leading-5 text-slate-800 transition-colors hover:border-[#405e9b]/50 hover:bg-[#405e9b]/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#405e9b] disabled:cursor-not-allowed disabled:opacity-60 lg:max-w-full"
          >
            <span className="min-w-0 [overflow-wrap:anywhere]">{suggestion.label}</span>
            {suggestion.badge && (
              <span
                className={cx(
                  "shrink-0 rounded-full border px-2 py-0.5 text-sm font-medium",
                  BADGE_STYLES[suggestion.badge] ??
                    "border-slate-200 bg-slate-50 text-slate-700",
                )}
              >
                {BADGE_LABELS[suggestion.badge] ?? ""}
              </span>
            )}
          </button>
        ))}
      </div>
    </section>
  );
}
