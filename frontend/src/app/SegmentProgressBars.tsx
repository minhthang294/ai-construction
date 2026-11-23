import { useState } from "react";
import {
  formatOverviewPercent,
  formatSegmentLabel,
  type SegmentProgress,
} from "./overviewFormat";

function hasActivity(segment: SegmentProgress) {
  const construction = segment.construction;
  return (
    construction.completed + construction.in_progress + construction.blocked > 0 ||
    segment.acceptance.confirmed > 0
  );
}

export default function SegmentProgressBars({ segments }: { segments: SegmentProgress[] }) {
  const [showAll, setShowAll] = useState(false);
  const withVerified = segments.filter((segment) => segment.verified_components > 0);
  const active = withVerified.filter(hasActivity);
  const visible = (showAll ? withVerified : active)
    .slice()
    .sort((a, b) => a.zone.localeCompare(b.zone, "vi") || a.segment - b.segment);
  const hiddenCount = withVerified.length - active.length;

  if (withVerified.length === 0) {
    return (
      <p className="mt-3 rounded-xl border border-dashed border-slate-300 bg-slate-50 p-4 text-sm text-slate-600">
        Chưa có cấu kiện đã xác minh theo đoạn.
      </p>
    );
  }

  return (
    <div className="mt-3">
      <p className="app-text-secondary">
        Hai tỷ lệ độc lập: tiến độ thi công và nghiệm thu trên cùng số cấu kiện đã xác minh.
      </p>
      {visible.length === 0 ? (
        <p className="mt-3 rounded-xl border border-dashed border-slate-300 bg-slate-50 p-4 text-sm text-slate-600">
          Chưa có đoạn nào phát sinh thi công hoặc nghiệm thu.
        </p>
      ) : (
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
                  <span className="app-text-secondary tabular-nums">{total} cấu kiện đã xác minh</span>
                </div>
                <div className="mt-2 space-y-2">
                  <div>
                    <div className="mb-1 flex flex-wrap items-baseline justify-between gap-x-2 text-xs">
                      <span className="font-medium text-slate-700">Thi công</span>
                      <span className="tabular-nums text-slate-700">
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
                      <div
                        className="app-status-bar--completed h-full rounded-full"
                        style={{ width: `${construction.completion_ratio * 100}%` }}
                      />
                    </div>
                  </div>
                  <div>
                    <div className="mb-1 flex flex-wrap items-baseline justify-between gap-x-2 text-xs">
                      <span className="font-medium text-slate-700">Nghiệm thu</span>
                      <span className="app-text-secondary tabular-nums">
                        {acceptance.confirmed}/{total} đã xác nhận · {formatOverviewPercent(acceptance.completion_ratio)}
                      </span>
                    </div>
                    <div
                      className="app-acceptance-track h-2 overflow-hidden rounded-full"
                      role="progressbar"
                      aria-label={`Tiến độ nghiệm thu ${label}`}
                      aria-valuenow={Math.round(acceptance.completion_ratio * 100)}
                      aria-valuemin={0}
                      aria-valuemax={100}
                    >
                      <div
                        className="app-acceptance-fill h-full rounded-full"
                        style={{ width: `${acceptance.completion_ratio * 100}%` }}
                      />
                    </div>
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      )}
      {hiddenCount > 0 || showAll ? (
        <button
          type="button"
          className="app-button app-button-secondary mt-3 w-full sm:w-auto"
          onClick={() => setShowAll((current) => !current)}
        >
          {showAll ? "Ẩn đoạn chưa hoạt động" : `Xem tất cả (${hiddenCount} đoạn chưa hoạt động)`}
        </button>
      ) : null}
    </div>
  );
}
