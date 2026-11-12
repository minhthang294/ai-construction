import { useEffect, useState } from "react";
import { listWorkItems, suggestInspectionChecklist } from "../lib/api";
import {
  BADGE,
  BUTTON_PRIMARY,
  CARD,
  CARD_PAD,
  cx,
  FIELD,
  LABEL,
  PANEL_ALERT,
  SECTION_TEXT,
  SECTION_TITLE,
} from "../lib/ui";
import { AlertIcon, ChecklistIcon, SpinnerIcon } from "./icons";
import CitationCard from "./CitationCard";
import type {
  Citation,
  InspectionChecklistResponse,
  WorkItemSummary,
} from "../types";

type Props = {
  projectId: string;
  onOpenCitation: (citation: Citation) => void;
};

export default function InspectionChecklistPanel({
  projectId,
  onOpenCitation,
}: Props) {
  const [workItems, setWorkItems] = useState<WorkItemSummary[]>([]);
  const [workItemId, setWorkItemId] = useState("");
  const [inlineCode, setInlineCode] = useState("");
  const [inlineName, setInlineName] = useState("");
  const [focus, setFocus] = useState("");
  const [result, setResult] = useState<InspectionChecklistResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const items = await listWorkItems(projectId);
        if (cancelled) return;
        setWorkItems(items);
        setWorkItemId((current) => current || items[0]?.id || "");
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Không tải được danh mục công việc.");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  async function suggest() {
    if (busy) return;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const payload = workItems.length > 0
        ? { work_item_id: workItemId, focus: focus.trim() || undefined, top_k: 8 }
        : {
            work_item: {
              code: inlineCode.trim() || undefined,
              name: inlineName.trim() || undefined,
            },
            focus: focus.trim() || undefined,
            top_k: 8,
          };
      if (workItems.length > 0 && !workItemId) {
        throw new Error("Chọn công việc cần kiểm tra.");
      }
      if (workItems.length === 0 && !inlineCode.trim() && !inlineName.trim()) {
        throw new Error("Nhập mã hoặc tên công việc.");
      }
      setResult(await suggestInspectionChecklist(projectId, payload));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không tạo được checklist.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section
      aria-busy={busy}
      className={cx(CARD, CARD_PAD, "space-y-4")}
    >
      <div className="max-w-3xl">
        <h2 className={SECTION_TITLE}>Gợi ý mục kiểm tra từ hồ sơ</h2>
        <p className={cx(SECTION_TEXT, "mt-1")}>
          Mỗi gợi ý phải kèm citation trang nguồn; trạng thái luôn là chưa xác nhận.
          Không tự đặt yes/đạt, không tự nghiệm thu.
        </p>
      </div>

      <div className="max-w-3xl space-y-4">
          {workItems.length > 0 ? (
          <label className={LABEL} htmlFor="eai-inspection-work-item">
            Công việc
            <select
              id="eai-inspection-work-item"
              className={FIELD}
              value={workItemId}
              onChange={(event) => {
                setWorkItemId(event.target.value);
                setResult(null);
              }}
            >
              {workItems.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.code} — {item.name}
                </option>
              ))}
            </select>
          </label>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2">
            <label className={LABEL} htmlFor="eai-inspection-code">
              Mã công việc
              <input
                id="eai-inspection-code"
                className={FIELD}
                value={inlineCode}
                onChange={(event) => setInlineCode(event.target.value)}
              />
            </label>
            <label className={LABEL} htmlFor="eai-inspection-name">
              Tên công việc
              <input
                id="eai-inspection-name"
                className={FIELD}
                value={inlineName}
                onChange={(event) => setInlineName(event.target.value)}
              />
            </label>
          </div>
        )}

        <label className={LABEL} htmlFor="eai-inspection-focus">
          Trọng tâm kiểm tra (không bắt buộc)
          <input
            id="eai-inspection-focus"
            className={FIELD}
            value={focus}
            onChange={(event) => setFocus(event.target.value)}
            placeholder="Ví dụ: lớp bảo vệ, mối nối, cao độ..."
          />
        </label>

        <button
          type="button"
          className={cx(BUTTON_PRIMARY, "w-full sm:w-auto")}
          onClick={() => void suggest()}
          disabled={busy}
        >
          {busy && <SpinnerIcon className="h-4 w-4" />}
          {busy ? "Đang tìm hồ sơ..." : "Gợi ý mục kiểm tra"}
        </button>

        {error && (
          <div role="alert" className={PANEL_ALERT}>
            {error}
          </div>
        )}

        {result && (
          <div className="space-y-4">
            {result.no_source && (
              <div className="flex gap-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm leading-6 text-amber-950">
                <AlertIcon className="mt-0.5 h-5 w-5 shrink-0 text-amber-700" />
                <div>
                  <p className="font-semibold">{result.message}</p>
                  <p className="mt-1">Không có mục kiểm tra nào được tạo khi thiếu trang nguồn.</p>
                </div>
              </div>
            )}

            {result.suggestions.length > 0 && (
              <div className="space-y-3">
                <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-800">
                  <ChecklistIcon className="h-4 w-4 text-[#405e9b]" />
                  {result.suggestions.length} gợi ý · trạng thái chưa xác nhận
                </h3>
                {result.suggestions.map((suggestion, index) => (
                  <article
                    key={`${index}-${suggestion.citation.document_id}-${suggestion.citation.page_number}`}
                    className="space-y-3 rounded-lg border border-slate-200 bg-white p-3"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <h4 className="text-sm font-semibold text-slate-800">
                        Mục {index + 1}: chưa xác nhận
                      </h4>
                      <span className={cx(BADGE, "border border-slate-200 bg-slate-100 text-slate-700")}>
                        độ khớp nguồn {Math.round(suggestion.relevance_score * 100) / 100}
                      </span>
                    </div>
                    <p className="text-sm leading-6 text-slate-900">{suggestion.item}</p>
                    <p className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm leading-6 text-slate-700 whitespace-pre-wrap">
                      Tiêu chí trích từ hồ sơ: {suggestion.criterion}
                    </p>
                    <CitationCard citation={suggestion.citation} onOpen={onOpenCitation} />
                    {suggestion.warnings.map((warning, warningIndex) => (
                      <p key={`${warningIndex}-${warning}`} className="text-xs leading-5 text-amber-800">
                        {warning}
                      </p>
                    ))}
                  </article>
                ))}
              </div>
            )}

            <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm leading-6 text-amber-950">
              <p>{result.disclaimer}</p>
              {result.warnings.map((warning, index) => (
                <p key={`${index}-${warning}`} className="mt-1">
                  {warning}
                </p>
              ))}
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
