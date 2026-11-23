import {
  formatOverviewPercent,
  formatSegmentLabel,
  type SegmentProgress,
} from "./overviewFormat";

export default function SegmentProgressBars({ segments }: { segments: SegmentProgress[] }) {
  const visible = [...segments]
    .filter((segment) => segment.verified_components > 0)
    .sort((a, b) => a.zone.localeCompare(b.zone, "vi") || a.segment - b.segment);

  if (visible.length === 0) {
    return (
      <p className="mt-3 rounded-xl border border-dashed border-slate-300 bg-slate-50 p-4 text-sm text-slate-600">
        Chưa có cấu kiện đã xác minh theo đoạn.
      </p>
    );
  }

  return (
    <div className="mt-3">
      <p className="text-xs leading-5 text-slate-500">
        Hai tỷ lệ độc lập: tiến độ thi công và nghiệm thu trên cùng số cấu kiện đã xác minh.
      </p>
      <ul className="mt-3 space-y-4">
        {visible.map((segment) => {
          const label = formatSegmentLabel(segment.zone, segment.segment);
          const total = segment.verified_components;
          const construction = segment.construction;
          const acceptance = segment.acceptance;
          return (
            <li key={segment.segment_id}>
              <div className="flex flex-wrap items-baseline justify-between gap-x-2">
                <span className="text-sm font-semibold text-slate-800">{label}</span>
                <span className="text-xs tabular-nums text-slate-500">{total} cấu kiện đã xác minh</span>
              </div>
              <div className="mt-2 space-y-2">
                <div>
                  <div className="mb-1 flex flex-wrap items-baseline justify-between gap-x-2 text-xs">
                    <span className="text-slate-700">Thi công</span>
                    <span className="tabular-nums text-slate-600">
                      {construction.completed}/{total} hoàn thành · {formatOverviewPercent(construction.completion_ratio)}
                    </span>
                  </div>
                  <div
                    className="h-2 overflow-hidden rounded-full bg-slate-100"
                    role="progressbar"
                    aria-label={`Tiến độ thi công ${label}`}
                    aria-valuenow={Math.round(construction.completion_ratio * 100)}
                    aria-valuemin={0}
                    aria-valuemax={100}
                  >
                    <div className="h-full rounded-full bg-sky-700" style={{ width: `${construction.completion_ratio * 100}%` }} />
                  </div>
                </div>
                <div>
                  <div className="mb-1 flex flex-wrap items-baseline justify-between gap-x-2 text-xs">
                    <span className="text-slate-700">Nghiệm thu</span>
                    <span className="tabular-nums text-slate-600">
                      {acceptance.confirmed}/{total} đã xác nhận · {formatOverviewPercent(acceptance.completion_ratio)}
                    </span>
                  </div>
                  <div
                    className="h-2 overflow-hidden rounded-full bg-slate-100"
                    role="progressbar"
                    aria-label={`Tiến độ nghiệm thu ${label}`}
                    aria-valuenow={Math.round(acceptance.completion_ratio * 100)}
                    aria-valuemin={0}
                    aria-valuemax={100}
                  >
                    <div className="h-full rounded-full bg-emerald-700" style={{ width: `${acceptance.completion_ratio * 100}%` }} />
                  </div>
                </div>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
