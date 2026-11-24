import type { ProgressRow } from "../lib/componentProgress";
import {
  FOCUS_RING,
  PRIMARY_BUTTON,
  SECONDARY_BUTTON,
  type ProgressBusy,
} from "../lib/componentProgressPanel";
import QuickCodeEntry from "./QuickCodeEntry";

type Props = {
  selected: string[];
  quickCodeRows: ProgressRow[];
  busy: ProgressBusy;
  onQuickCodeConfirm: (ids: string[]) => void;
  onClearSelection: () => void;
  onOpenEditor: () => void;
};

export default function ComponentProgressSelection({
  selected,
  quickCodeRows,
  busy,
  onQuickCodeConfirm,
  onClearSelection,
  onOpenEditor,
}: Props) {
  return (
    <>
      <p className="text-sm text-slate-700">
        Chọn từng cấu kiện. Đổi bộ lọc sẽ xóa lựa chọn.
      </p>
      <QuickCodeEntry
        rows={quickCodeRows}
        selectedIds={selected}
        disabled={busy !== null}
        onConfirm={onQuickCodeConfirm}
      />
      <div
        className={`flex flex-wrap items-center justify-between gap-2 rounded-xl border border-slate-300 bg-white p-2 shadow-sm ${selected.length ? "fixed inset-x-3 bottom-[calc(3.75rem+max(0.5rem,env(safe-area-inset-bottom)))] z-20 mx-auto max-w-3xl shadow-md lg:static" : ""}`}
      >
        <p aria-live="polite" className="text-xs font-semibold text-slate-900">
          Đã chọn {selected.length}
        </p>
        <div className="flex min-w-0 flex-wrap gap-2">
          <button
            type="button"
            className={`${SECONDARY_BUTTON} flex-1 sm:flex-none ${FOCUS_RING}`}
            disabled={selected.length === 0}
            onClick={onClearSelection}
          >
            Bỏ chọn
          </button>
          <button
            type="button"
            className={`${PRIMARY_BUTTON} flex-1 sm:flex-none ${FOCUS_RING}`}
            disabled={selected.length === 0 || busy !== null}
            onClick={onOpenEditor}
          >
            Ghi tiến độ
          </button>
        </div>
      </div>
    </>
  );
}
