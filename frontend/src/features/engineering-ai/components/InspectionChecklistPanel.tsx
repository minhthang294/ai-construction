import { useEffect, useState } from "react";
import { listWorkItems, suggestInspectionChecklist } from "../lib/api";
import type {
  Citation,
  InspectionChecklistResponse,
  WorkItemSummary,
} from "../types";
import CitationCard from "./CitationCard";

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
    <section className="space-y-3 rounded border border-gray-200 bg-white p-3 shadow-sm">
      <div>
        <h2 className="text-sm font-semibold">Gợi ý mục kiểm tra từ hồ sơ</h2>
        <p className="text-xs text-gray-600">
          Mỗi gợi ý phải kèm citation trang nguồn; trạng thái luôn là chưa xác nhận.
          Không tự đặt yes/đạt, không tự nghiệm thu.
        </p>
      </div>

      {workItems.length > 0 ? (
        <label className="block text-xs font-medium text-gray-700">
          Công việc
          <select
            className="mt-1 w-full rounded border border-gray-300 p-2 text-sm"
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
        <div className="grid gap-2 sm:grid-cols-2">
          <label className="block text-xs font-medium text-gray-700">
            Mã công việc
            <input
              className="mt-1 w-full rounded border border-gray-300 p-2 text-sm"
              value={inlineCode}
              onChange={(event) => setInlineCode(event.target.value)}
            />
          </label>
          <label className="block text-xs font-medium text-gray-700">
            Tên công việc
            <input
              className="mt-1 w-full rounded border border-gray-300 p-2 text-sm"
              value={inlineName}
              onChange={(event) => setInlineName(event.target.value)}
            />
          </label>
        </div>
      )}

      <label className="block text-xs font-medium text-gray-700">
        Trọng tâm kiểm tra (không bắt buộc)
        <input
          className="mt-1 w-full rounded border border-gray-300 p-2 text-sm"
          value={focus}
          onChange={(event) => setFocus(event.target.value)}
          placeholder="Ví dụ: lớp bảo vệ, mối nối, cao độ..."
        />
      </label>

      <button
        type="button"
        className="rounded bg-blue-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
        onClick={() => void suggest()}
        disabled={busy}
      >
        {busy ? "Đang tìm hồ sơ..." : "Gợi ý mục kiểm tra"}
      </button>

      {error && <div className="rounded bg-red-50 p-2 text-xs text-red-800">{error}</div>}

      {result && (
        <div className="space-y-3">
          {result.no_source && (
            <div className="rounded bg-amber-50 p-2 text-xs text-amber-950">
              <p className="font-semibold">{result.message}</p>
              <p className="mt-1">Không có mục kiểm tra nào được tạo khi thiếu trang nguồn.</p>
            </div>
          )}

          {result.suggestions.length > 0 && (
            <div className="space-y-3">
              <h3 className="text-xs font-semibold text-gray-700">
                {result.suggestions.length} gợi ý · trạng thái chưa xác nhận
              </h3>
              {result.suggestions.map((suggestion, index) => (
                <article
                  key={`${index}-${suggestion.citation.document_id}-${suggestion.citation.page_number}`}
                  className="space-y-2 rounded border border-gray-200 p-2"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <h4 className="text-xs font-semibold text-gray-800">
                      Mục {index + 1}: chưa xác nhận
                    </h4>
                    <span className="rounded bg-gray-100 px-2 py-0.5 text-[11px]">
                      độ khớp nguồn {Math.round(suggestion.relevance_score * 100) / 100}
                    </span>
                  </div>
                  <p className="text-sm">{suggestion.item}</p>
                  <p className="whitespace-pre-wrap rounded bg-gray-50 p-2 text-xs text-gray-700">
                    Tiêu chí trích từ hồ sơ: {suggestion.criterion}
                  </p>
                  <CitationCard citation={suggestion.citation} onOpen={onOpenCitation} />
                  {suggestion.warnings.map((warning, warningIndex) => (
                    <p key={`${warningIndex}-${warning}`} className="text-[11px] text-amber-800">
                      {warning}
                    </p>
                  ))}
                </article>
              ))}
            </div>
          )}

          <div className="rounded bg-amber-50 p-2 text-xs text-amber-950">
            <p>{result.disclaimer}</p>
            {result.warnings.map((warning, index) => (
              <p key={`${index}-${warning}`} className="mt-1">{warning}</p>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
