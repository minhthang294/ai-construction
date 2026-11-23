import { useEffect, useState } from "react";
import { listQuestionSuggestions } from "../lib/api";
import { cx, META_TEXT } from "../lib/ui";
import type { QuestionSuggestion } from "../types";
import { AlertIcon } from "./icons";

type Props = {
  projectId: string;
  busy: boolean;
  onPick: (suggestion: QuestionSuggestion) => void;
};

const BADGE_STYLES: Record<string, string> = {
  verified: "border-emerald-200 bg-emerald-50 text-emerald-800",
  proposed: "border-amber-200 bg-amber-50 text-amber-800",
  navigation: "border-[#405e9b]/20 bg-white text-[#35507f]",
  caution: "border-red-200 bg-red-50 text-red-800",
};

const BADGE_LABELS: Record<string, string> = {
  verified: "Đã xác minh",
  proposed: "Chưa xác minh",
  navigation: "Mở trang",
  caution: "Cần đối chiếu",
};

export default function QuestionSuggestions({ projectId, busy, onPick }: Props) {
  const [suggestions, setSuggestions] = useState<QuestionSuggestion[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    listQuestionSuggestions(projectId)
      .then((rows) => {
        if (!cancelled) setSuggestions(rows.slice(0, 6));
      })
      .catch(() => {
        if (!cancelled) setSuggestions([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [projectId]);

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
      <h3 className="text-xs font-semibold uppercase tracking-[0.12em] text-[#35507f]">
        Hỏi nhanh từ dữ liệu công trình
      </h3>
      <div className="mt-2 flex flex-wrap gap-2">
        {suggestions.map((suggestion) => (
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
            className="flex min-h-10 max-w-full items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-left text-xs leading-5 text-slate-700 transition-colors hover:border-[#405e9b]/40 hover:bg-[#405e9b]/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#405e9b] disabled:cursor-not-allowed disabled:opacity-60"
          >
            <span className="min-w-0 [overflow-wrap:anywhere]">{suggestion.label}</span>
            {suggestion.badge && (
              <span
                className={cx(
                  "shrink-0 rounded-full border px-1.5 py-0.5 text-[10px] font-medium",
                  BADGE_STYLES[suggestion.badge] ??
                    "border-slate-200 bg-slate-50 text-slate-600",
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
