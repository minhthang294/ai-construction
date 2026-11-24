import type { DailyProgressFilters } from "../lib/dailyProgress";
import {
  FIELD,
  FOCUS_RING,
  SECONDARY_BUTTON,
  type DailyProgressBusy,
} from "../lib/dailyProgressPanel";

type Props = {
  eventDate: string;
  maxDate: string;
  dateDisabled: boolean;
  filters: DailyProgressFilters;
  zones: string[];
  segmentOptions: Array<{ id: string; number: number }>;
  filtersLocked: boolean;
  busy: DailyProgressBusy;
  showEmpty: boolean;
  onDateChange: (eventDate: string) => void;
  onFilterChange: (patch: Partial<DailyProgressFilters>) => void;
  onOpenPaste?: () => void;
};

export default function DailyProgressHeader({
  eventDate,
  maxDate,
  dateDisabled,
  filters,
  zones,
  segmentOptions,
  filtersLocked,
  busy,
  showEmpty,
  onDateChange,
  onFilterChange,
  onOpenPaste,
}: Props) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
      <h4 className="text-base font-semibold text-slate-900 sm:text-lg">
        Tiến độ trong ngày
      </h4>
      <p className="mt-1 text-xs text-slate-600">
        Chọn đúng bước thi công và cấu kiện có thật; xem lại rồi mới lưu.
      </p>
      {onOpenPaste ? (
        <button
          type="button"
          className={`${SECONDARY_BUTTON} mt-2 w-full ${FOCUS_RING}`}
          onClick={onOpenPaste}
        >
          Dán tin nhắn Zalo để ghi tiến độ
        </button>
      ) : null}
      <label className="mt-3 block text-xs font-medium text-slate-700">
        Ngày ghi nhận
        <input
          type="date"
          className={FIELD}
          value={eventDate}
          max={maxDate}
          disabled={dateDisabled}
          onChange={(event) => onDateChange(event.target.value)}
        />
      </label>
      <div className="mt-2 grid grid-cols-2 gap-2">
        <label className="min-w-0 text-xs font-medium text-slate-700">
          Khu vực
          <select
            className={FIELD}
            value={filters.zone}
            disabled={filtersLocked || busy === "load"}
            onChange={(event) => onFilterChange({ zone: event.target.value })}
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
            value={filters.segment_id}
            disabled={filtersLocked || busy === "load"}
            onChange={(event) =>
              onFilterChange({ segment_id: event.target.value })
            }
          >
            <option value="">Tất cả phân đoạn</option>
            {segmentOptions.map((segment) => (
              <option key={segment.id} value={segment.id}>
                PĐ {segment.number}
              </option>
            ))}
          </select>
        </label>
      </div>
      {busy === "load" ? (
        <p role="status" className="mt-2 text-xs text-slate-600">Đang tải dữ liệu…</p>
      ) : null}
      {showEmpty ? (
        <p className="mt-2 text-sm text-slate-600">
          Chưa có cấu kiện trong công trình.
        </p>
      ) : null}
    </div>
  );
}
