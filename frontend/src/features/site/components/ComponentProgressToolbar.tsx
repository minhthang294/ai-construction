import type { RefObject } from "react";
import type { ProgressFilters } from "../lib/componentProgress";
import type { MainWork } from "../lib/mainWorks";
import {
  FIELD,
  FOCUS_RING,
  SECONDARY_BUTTON,
  type ProgressBusy,
} from "../lib/componentProgressPanel";

type Props = {
  filters: ProgressFilters;
  updateFilter: (patch: Partial<ProgressFilters>) => void;
  clearFilters: () => void;
  zones: string[];
  segmentOptions: Array<[string, number]>;
  works: MainWork[];
  activeFilterChips: string[];
  advancedFilterCount: number;
  hasFilters: boolean;
  filteredCount: number;
  busy: ProgressBusy;
  error: string | null;
  definitionsError: boolean;
  selectionMode: boolean;
  onToggleSelectionMode: () => void;
  showAdvanced: boolean;
  onToggleAdvanced: () => void;
  onLoad: () => void;
  headingRef: RefObject<HTMLHeadingElement | null>;
  advancedId: string;
};

export default function ComponentProgressToolbar({
  filters,
  updateFilter,
  clearFilters,
  zones,
  segmentOptions,
  works,
  activeFilterChips,
  advancedFilterCount,
  hasFilters,
  filteredCount,
  busy,
  error,
  definitionsError,
  selectionMode,
  onToggleSelectionMode,
  showAdvanced,
  onToggleAdvanced,
  onLoad,
  headingRef,
  advancedId,
}: Props) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
      <div className="flex items-center justify-between gap-2">
        <div className="min-w-0">
          <h4
            ref={headingRef}
            tabIndex={-1}
            className="text-base font-semibold text-slate-900 focus:outline-none sm:text-lg"
          >
            Tiến độ cấu kiện
          </h4>
          <p className="mt-1 text-xs text-slate-600">
            {busy === "load" ? "Đang tải…" : `${filteredCount} cấu kiện`}
          </p>
        </div>
        <button
          type="button"
          aria-pressed={selectionMode}
          className={`${SECONDARY_BUTTON} shrink-0 ${FOCUS_RING}`}
          onClick={onToggleSelectionMode}
        >
          {selectionMode ? "Xong" : "Chọn nhiều"}
        </button>
      </div>

      <label className="mt-3 block text-xs font-medium text-slate-700">
        Tìm mã cấu kiện
        <input
          type="search"
          inputMode="search"
          className={FIELD}
          value={filters.query}
          placeholder="Ví dụ F-66-67"
          aria-label="Tìm mã cấu kiện, nhóm hoặc bước"
          onChange={(event) => updateFilter({ query: event.target.value })}
        />
      </label>

      <div className="mt-2 grid grid-cols-2 gap-2">
        <label className="min-w-0 text-xs font-medium text-slate-700">
          Khu vực
          <select
            className={FIELD}
            value={filters.zone}
            onChange={(event) => updateFilter({ zone: event.target.value })}
          >
            <option value="">Tất cả khu</option>
            {zones.map((zone) => (
              <option key={zone} value={zone}>
                {zone}
              </option>
            ))}
          </select>
        </label>
        <label className="min-w-0 text-xs font-medium text-slate-700">
          Phân đoạn
          <select
            className={FIELD}
            value={filters.segment}
            onChange={(event) =>
              updateFilter({ segment: event.target.value })
            }
          >
            <option value="">Tất cả phân đoạn</option>
            {segmentOptions.map(([value, number]) => (
              <option key={value} value={value}>
                PĐ {number}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
        <button
          type="button"
          aria-expanded={showAdvanced}
          aria-controls={advancedId}
          className={`${SECONDARY_BUTTON} ${FOCUS_RING}`}
          onClick={onToggleAdvanced}
        >
          Bộ lọc nâng cao
          {advancedFilterCount ? ` (${advancedFilterCount})` : ""}
        </button>
        {hasFilters ? (
          <button
            type="button"
            className={`${SECONDARY_BUTTON} ${FOCUS_RING}`}
            onClick={clearFilters}
          >
            Xóa lọc
          </button>
        ) : null}
      </div>

      {activeFilterChips.length ? (
        <div
          className="mt-2 flex flex-wrap gap-1"
          aria-label="Bộ lọc đang áp dụng"
        >
          {activeFilterChips.map((chip, index) => (
            <span
              key={`${chip}-${index}`}
              className="max-w-full break-words rounded-full border border-slate-300 bg-slate-50 px-2 py-1 text-xs text-slate-700"
            >
              {chip}
            </span>
          ))}
        </div>
      ) : null}

      {showAdvanced ? (
        <div
          id={advancedId}
          className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2"
        >
          <label className="min-w-0 text-xs font-medium text-slate-700">
            Loại
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
            Công tác
            <select
              className={FIELD}
              value={filters.main_work_key}
              onChange={(event) =>
                updateFilter({
                  main_work_key: event.target.value,
                })
              }
            >
              <option value="">Tất cả công tác</option>
              {(["pile", "beam"] as const).map((type) => {
                const items = works.filter(
                  (work) => work.component_type === type,
                );
                if (!items.length) return null;
                return (
                  <optgroup
                    key={type}
                    label={type === "pile" ? "Cọc" : "Dầm"}
                  >
                    {items.map((work) => (
                      <option key={work.key} value={work.key}>
                        {work.label}
                      </option>
                    ))}
                  </optgroup>
                );
              })}
            </select>
          </label>
          <label className="min-w-0 text-xs font-medium text-slate-700">
            Thi công
            <select
              className={FIELD}
              value={filters.construction_status}
              onChange={(event) =>
                updateFilter({
                  construction_status: event.target.value,
                })
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
            Nghiệm thu
            <select
              className={FIELD}
              value={filters.acceptance_status}
              onChange={(event) =>
                updateFilter({
                  acceptance_status: event.target.value,
                })
              }
            >
              <option value="">Tất cả trạng thái</option>
              <option value="NOT_LINKED">Chưa liên kết</option>
              <option value="PENDING">Đang chờ</option>
              <option value="APPROVED">Đã xác nhận</option>
              <option value="CONDITIONAL">Có điều kiện</option>
              <option value="REJECTED">Không đạt</option>
              <option value="CONFIRMED">Đã xác nhận (khác)</option>
            </select>
          </label>
          <button
            type="button"
            className={`${SECONDARY_BUTTON} justify-self-start ${FOCUS_RING}`}
            disabled={busy === "load"}
            onClick={onLoad}
          >
            Tải lại danh sách
          </button>
        </div>
      ) : null}

      {error && !showAdvanced ? (
        <button
          type="button"
          className={`${SECONDARY_BUTTON} mt-2 ${FOCUS_RING}`}
          disabled={busy === "load"}
          onClick={onLoad}
        >
          Tải lại danh sách
        </button>
      ) : null}

      {definitionsError ? (
        <p className="mt-2 text-xs text-amber-800">
          Không tải được danh mục bước thi công.
        </p>
      ) : null}
    </div>
  );
}
