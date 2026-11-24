import type { ProgressRow } from "../lib/componentProgress";
import {
  FOCUS_RING,
  PROGRESS_PAGE_SIZE,
  SECONDARY_BUTTON,
  type ProgressBusy,
} from "../lib/componentProgressPanel";
import ProgressCard from "./ProgressCard";

type Props = {
  rows: ProgressRow[];
  filteredCount: number;
  visibleRows: ProgressRow[];
  busy: ProgressBusy;
  selectionMode: boolean;
  selectedIds: ReadonlySet<string>;
  projectId: string;
  primaryZone?: string | null;
  remaining: number;
  onLoadMore: () => void;
  onChanged: () => void;
  onToggle: (id: string) => void;
  onOpen: (id: string) => void;
};

export default function ComponentProgressList({
  rows,
  filteredCount,
  visibleRows,
  busy,
  selectionMode,
  selectedIds,
  projectId,
  primaryZone,
  remaining,
  onLoadMore,
  onChanged,
  onToggle,
  onOpen,
}: Props) {
  return (
    <div className="space-y-2">
      {busy === "load" && rows.length === 0 ? (
        <p className="rounded-lg border border-slate-200 bg-white p-3 text-sm text-slate-600">
          Đang tải cấu kiện…
        </p>
      ) : null}
      {!busy && filteredCount === 0 ? (
        <p className="rounded-lg border border-slate-200 bg-white p-3 text-sm text-slate-600">
          {rows.length === 0
            ? "Chưa có cấu kiện trong công trình."
            : "Không có cấu kiện khớp bộ lọc."}
        </p>
      ) : null}
      {visibleRows.map((row) => (
        <ProgressCard
          key={row.id}
          row={row}
          projectId={projectId}
          primaryZone={primaryZone}
          onChanged={onChanged}
          selectionMode={selectionMode}
          selected={selectedIds.has(row.id)}
          onToggle={() => onToggle(row.id)}
          onOpen={() => onOpen(row.id)}
        />
      ))}
      {remaining > 0 ? (
        <button
          type="button"
          className={`${SECONDARY_BUTTON} w-full ${FOCUS_RING}`}
          onClick={onLoadMore}
        >
          Xem thêm {Math.min(PROGRESS_PAGE_SIZE, remaining)} cấu kiện
        </button>
      ) : null}
    </div>
  );
}
