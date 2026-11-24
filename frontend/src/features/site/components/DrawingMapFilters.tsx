/** Marker filters for the drawing map panel. */

import { BUTTON, FIELD, FOCUS_RING } from "../lib/drawingMapPanel";
import type { DrawingFilters } from "../lib/drawingMap";

type Props = {
  filters: DrawingFilters;
  updateFilter: (patch: Partial<DrawingFilters>) => void;
  visibleMarkerCount: number;
  hasFilters: boolean;
  clearFilters: () => void;
};

export default function DrawingMapFilters({
  filters,
  updateFilter,
  visibleMarkerCount,
  hasFilters,
  clearFilters,
}: Props) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        <label className="min-w-0 text-xs font-medium text-slate-700 sm:col-span-2">
          Tìm mã cấu kiện hoặc bản vẽ
          <input
            type="search"
            inputMode="search"
            className={FIELD}
            value={filters.query}
            placeholder="Ví dụ F-24-25 hoặc TK-32"
            onChange={(event) =>
              updateFilter({ query: event.target.value })
            }
          />
        </label>
        <label className="min-w-0 text-xs font-medium text-slate-700">
          Loại cấu kiện
          <select
            className={FIELD}
            value={filters.type}
            onChange={(event) =>
              updateFilter({ type: event.target.value })
            }
          >
            <option value="">Tất cả loại</option>
            <option value="pile">Cọc</option>
            <option value="beam">Dầm</option>
          </select>
        </label>
        <label className="min-w-0 text-xs font-medium text-slate-700">
          Trạng thái thi công
          <select
            className={FIELD}
            value={filters.status}
            onChange={(event) =>
              updateFilter({ status: event.target.value })
            }
          >
            <option value="">Tất cả trạng thái</option>
            <option value="NOT_STARTED">Chưa bắt đầu</option>
            <option value="IN_PROGRESS">Đang thi công</option>
            <option value="COMPLETED">Hoàn thành</option>
            <option value="BLOCKED">Tạm dừng</option>
          </select>
        </label>
        <label className="min-w-0 text-xs font-medium text-slate-700">
          Phạm vi sửa chữa
          <select
            className={FIELD}
            value={filters.origin}
            onChange={(event) =>
              updateFilter({ origin: event.target.value })
            }
          >
            <option value="">Tất cả phạm vi</option>
            <option value="DESIGN_SCOPE">Thiết kế</option>
            <option value="ADDITIONAL_SCOPE">Phát sinh</option>
          </select>
        </label>
        <div className="flex flex-wrap items-end justify-between gap-2 sm:col-span-2">
          <p aria-live="polite" className="text-xs text-slate-600">
            {visibleMarkerCount} vị trí khớp bộ lọc
          </p>
          {hasFilters ? (
            <button
              type="button"
              className={`${BUTTON} ${FOCUS_RING}`}
              onClick={clearFilters}
            >
              Xóa lọc
            </button>
          ) : null}
        </div>
      </div>
    </div>
  );
}
