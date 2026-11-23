import { useMemo, useState } from "react";
import { analyzeQuickCodes, type QuickCodeRow } from "../lib/quickCodeEntry";

const FIELD =
  "mt-1 min-h-11 w-full min-w-0 rounded-lg border border-slate-300 bg-white px-3 text-base text-slate-900 focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-300 sm:text-sm";

const CONFIRM_BUTTON =
  "min-h-11 rounded-lg border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-800 active:bg-slate-100 disabled:bg-slate-100 disabled:text-slate-400";

export default function QuickCodeEntry({
  rows,
  selectedIds,
  onConfirm,
  disabled = false,
}: {
  rows: QuickCodeRow[];
  selectedIds: string[];
  onConfirm: (ids: string[]) => void;
  disabled?: boolean;
}) {
  const [text, setText] = useState("");
  const [message, setMessage] = useState("");
  const analysis = useMemo(
    () => (text.trim() ? analyzeQuickCodes(text, rows, selectedIds) : null),
    [rows, selectedIds, text],
  );
  const canConfirm = Boolean(
    analysis && analysis.matched.length > 0 && analysis.unknown.length === 0 && !disabled,
  );

  function confirm() {
    if (!analysis || !canConfirm) return;
    onConfirm(analysis.matchedIds);
    setMessage(`Đã thêm ${analysis.matched.length} cấu kiện vào lựa chọn.`);
    setText("");
  }

  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-2">
      <label className="block text-xs font-medium text-slate-700">
        Nhập nhanh mã cấu kiện
        <input
          className={FIELD}
          value={text}
          placeholder="Ví dụ: F67,64,55 G65 H62"
          autoComplete="off"
          disabled={disabled}
          onChange={(event) => {
            setText(event.target.value);
            setMessage("");
          }}
        />
      </label>
      <p className="mt-1 text-xs leading-5 text-slate-500">
        Số trần dùng tiền tố gần nhất; mã dầm có dấu gạch giữ nguyên.
      </p>

      {analysis ? (
        <div className="mt-2 space-y-2" aria-live="polite">
          <p className="break-words text-xs text-slate-700">
            Khớp {analysis.matched.length}:{" "}
            <span className="font-mono font-semibold text-slate-900">
              {analysis.matched.map((item) => item.row.canonical_code).join(", ") || "—"}
            </span>
          </p>
          {analysis.unknown.length ? (
            <p className="break-words text-xs font-medium text-red-700">
              Không tìm thấy trong khu/phân đoạn đã chọn: {analysis.unknown.join(", ")}
            </p>
          ) : null}
          {analysis.duplicates.length ? (
            <p className="break-words text-xs text-amber-800">
              Đã bỏ qua trùng/đã chọn: {analysis.duplicates.join(", ")}
            </p>
          ) : null}
          {analysis.unknown.length ? (
            <p className="text-xs text-red-800">
              Sửa hoặc bỏ các mã chưa khớp trước khi xác nhận.
            </p>
          ) : null}
          <button
            type="button"
            className={CONFIRM_BUTTON}
            disabled={!canConfirm}
            onClick={confirm}
          >
            Chọn {analysis.matched.length} cấu kiện đã xem trước
          </button>
        </div>
      ) : null}

      {message ? (
        <p role="status" className="mt-2 text-xs font-medium text-emerald-800">
          {message}
        </p>
      ) : null}
    </div>
  );
}
