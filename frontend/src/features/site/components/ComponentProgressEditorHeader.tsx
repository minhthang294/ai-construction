import type { RefObject } from "react";
import type { ProgressRow } from "../lib/componentProgress";
import {
  FOCUS_RING,
  type ProgressBusy,
} from "../lib/componentProgressPanel";

type Props = {
  selectedRows: ProgressRow[];
  busy: ProgressBusy;
  onClose: () => void;
  headingRef: RefObject<HTMLHeadingElement | null>;
};

export default function ComponentProgressEditorHeader({
  selectedRows,
  busy,
  onClose,
  headingRef,
}: Props) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
      <div className="flex items-start gap-2">
        <button
          type="button"
          aria-label="Quay lại danh sách"
          className={`min-h-11 min-w-11 shrink-0 rounded-lg border border-slate-300 text-lg font-semibold text-slate-800 active:bg-slate-100 disabled:bg-slate-100 disabled:text-slate-400 ${FOCUS_RING}`}
          disabled={busy !== null}
          onClick={onClose}
        >
          ←
        </button>
        <div className="min-w-0">
          <h4
            ref={headingRef}
            tabIndex={-1}
            className="text-lg font-semibold text-slate-900 focus:outline-none"
          >
            Ghi tiến độ
          </h4>
          <p className="mt-1 text-xs text-slate-600">
            {selectedRows.length} cấu kiện · một bước thi công
          </p>
        </div>
      </div>

      <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50 p-2">
        <p className="text-xs font-medium text-slate-700">
          Cấu kiện đã chọn
        </p>
        <p className="mt-1 max-h-32 overflow-auto break-words font-mono text-sm text-slate-900">
          {selectedRows.map((row) => row.canonical_code).join(", ")}
        </p>
      </div>
    </div>
  );
}
