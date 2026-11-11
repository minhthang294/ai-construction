import { useEffect, useState } from "react";
import type { AcceptanceRecord, ResultState } from "../types";
import { confirmationBlockers, hasUnresolvedChecklist } from "../types";

type Props = {
  record: AcceptanceRecord;
  open: boolean;
  onCancel: () => void;
  onConfirm: (result: ResultState, note: string) => Promise<void> | void;
  submitting?: boolean;
};

const RESULT_OPTIONS: ReadonlyArray<{ value: ResultState; label: string; hint: string }> = [
  { value: "approved", label: "Đồng ý nghiệm thu", hint: "Chỉ khi tất cả hạng mục đạt" },
  { value: "conditional", label: "Đồng ý có điều kiện", hint: "Bắt buộc ghi rõ điều kiện" },
  { value: "rejected", label: "Không đồng ý", hint: "Bắt buộc ghi rõ lý do" },
];

export default function ConfirmDialog({
  record,
  open,
  onCancel,
  onConfirm,
  submitting = false,
}: Props) {
  const [result, setResult] = useState<ResultState | "">("");
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setResult("");
      setNote("");
      setError(null);
    }
  }, [open, record.id]);

  if (!open) return null;

  const blockers = confirmationBlockers(record);
  const unresolved = hasUnresolvedChecklist(record);
  const noteRequired = result === "conditional" || result === "rejected";
  const canConfirm =
    blockers.length === 0 &&
    result !== "" &&
    !(noteRequired && !note.trim()) &&
    !submitting;

  async function handleConfirm() {
    if (!canConfirm) return;
    setError(null);
    try {
      await onConfirm(result as ResultState, note.trim());
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không xác nhận được BBNT.");
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-3">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="acceptance-confirm-title"
        className="max-h-full w-full max-w-lg overflow-y-auto rounded-xl bg-white p-4 shadow-xl"
      >
        <h2 id="acceptance-confirm-title" className="text-lg font-semibold">
          Xác nhận BBNT
        </h2>
        <p className="mt-1 rounded bg-amber-50 p-2 text-sm text-amber-900">
          Chỉ người có quyền xác nhận (quản lý dự án/quản trị) được thao tác. Đây
          là quyết định của con người; hệ thống không tự kết luận nghiệm thu.
        </p>

        {blockers.length > 0 && (
          <div className="mt-3 rounded bg-rose-50 p-3 text-sm text-rose-900">
            <p className="font-semibold">Chưa thể xác nhận:</p>
            <ul className="mt-1 list-disc pl-5">
              {blockers.map((blocker) => (
                <li key={blocker}>{blocker}</li>
              ))}
            </ul>
          </div>
        )}

        <div className="mt-3 space-y-2">
          <p className="text-sm text-slate-600">
            Checklist:{" "}
            {unresolved
              ? "còn mục chưa xác nhận"
              : `đã xác nhận ${record.checklist.length}/${record.checklist.length}`}
          </p>
          <p className="text-sm text-slate-600">
            So với thiết kế: {record.design_compliance === "yes" ? "Đảm bảo" : record.design_compliance === "no" ? "Không đảm bảo" : "Chưa đánh giá"}
          </p>
          <p className="text-sm text-slate-600">
            Chỉ dẫn kỹ thuật: {record.technical_compliance === "yes" ? "Đạt yêu cầu" : record.technical_compliance === "no" ? "Không đạt yêu cầu" : "Chưa đánh giá"}
          </p>
        </div>

        <fieldset className="mt-4 space-y-2">
          <legend className="font-semibold">Kết luận của người xác nhận</legend>
          {RESULT_OPTIONS.map((option) => (
            <label key={option.value} className="flex items-start gap-2 rounded border p-2 text-sm">
              <input
                type="radio"
                name="acceptance-result"
                value={option.value}
                checked={result === option.value}
                onChange={() => setResult(option.value)}
                className="mt-1"
              />
              <span>
                <span className="font-medium">{option.label}</span>
                <span className="block text-xs text-slate-500">{option.hint}</span>
              </span>
            </label>
          ))}
        </fieldset>

        <label className="mt-3 block text-sm">
          {noteRequired ? "Lý do / điều kiện (bắt buộc)" : "Ghi chú kết luận (nếu có)"}
          <textarea
            className="mt-1 w-full rounded border p-3"
            rows={3}
            value={note}
            onChange={(event) => setNote(event.target.value)}
          />
        </label>

        {error && (
          <p role="alert" className="mt-3 rounded bg-rose-50 p-3 text-sm text-rose-800">
            {error}
          </p>
        )}

        <div className="mt-4 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={handleConfirm}
            disabled={!canConfirm}
            className="rounded bg-teal-700 px-4 py-3 font-semibold text-white disabled:opacity-50"
          >
            {submitting ? "Đang xác nhận..." : "Xác nhận BBNT"}
          </button>
          <button
            type="button"
            onClick={onCancel}
            disabled={submitting}
            className="rounded border px-4 py-3 disabled:opacity-50"
          >
            Hủy
          </button>
        </div>
      </div>
    </div>
  );
}
