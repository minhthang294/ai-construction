import { shortDate } from "./acceptancePageModel";
import type { PendingAcceptanceResponse } from "../types";

type Props = {
  pending: PendingAcceptanceResponse;
  pendingFilterActive: boolean;
  pendingTotalAll: number | null;
  pendingSelected: Set<string>;
  pendingBusy: boolean;
  onClearFilter: () => void;
  onToggle: (componentId: string) => void;
  onCreate: () => void;
};

export default function PendingAcceptancePanel({
  pending,
  pendingFilterActive,
  pendingTotalAll,
  pendingSelected,
  pendingBusy,
  onClearFilter,
  onToggle,
  onCreate,
}: Props) {
  return (
    <section
      aria-label="Chờ nghiệm thu"
      className="rounded-xl border border-amber-200 bg-amber-50/60 p-3 shadow-sm sm:p-4"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-base font-semibold text-amber-950">
          Chờ nghiệm thu (
          {pendingFilterActive && pendingTotalAll !== null
            ? `${pending.total_components} / ${pendingTotalAll}`
            : pending.total_components}
          )
        </h2>
        <span className="text-sm text-amber-900">
          Hoàn thành thi công, chưa có BBNT xác nhận
        </span>
      </div>
      {pendingFilterActive && (
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <span className="rounded-full border border-amber-300 bg-white px-3 py-1 text-sm text-amber-950">
            Đang lọc:{" "}
            <strong className="[overflow-wrap:anywhere]">
              {pending.stage_name ?? "đợt thi công đã chọn"}
            </strong>
          </span>
          <button
            type="button"
            onClick={onClearFilter}
            className="min-h-11 text-sm font-medium text-teal-800 underline"
          >
            Xem tất cả
          </button>
        </div>
      )}
      <p className="mt-1 text-sm leading-6 text-amber-900">
        Tiến độ thi công không phải nghiệm thu. Chọn cấu kiện để lập phiếu
        yêu cầu; BBNT chỉ được xác nhận bởi người có quyền.
      </p>
      <div className="mt-3 space-y-3">
        {pending.groups.map((group) => (
          <div
            key={`${group.stage_name}-${group.zone}-${group.segment}`}
            className="rounded-lg border border-amber-200 bg-white p-3"
          >
            <h3 className="text-sm font-semibold text-slate-900 [overflow-wrap:anywhere]">
              {group.stage_name}
            </h3>
            <p className="mt-0.5 text-sm text-slate-600">
              {group.zone} · Phân đoạn {group.segment} ·{" "}
              {group.event_dates.map(shortDate).join(", ")}
            </p>
            <div className="mt-2 flex flex-wrap gap-2">
              {group.components.map((component) => {
                const selected = pendingSelected.has(component.component_id);
                return (
                  <label
                    key={component.component_id}
                    className={`flex min-h-11 cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 text-sm ${
                      selected
                        ? "border-teal-700 bg-teal-50 text-teal-900"
                        : "border-slate-300 bg-white text-slate-800"
                    }`}
                  >
                    <input
                      type="checkbox"
                      className="h-5 w-5 accent-teal-700"
                      checked={selected}
                      onChange={() => onToggle(component.component_id)}
                    />
                    <span className="font-medium">{component.code}</span>
                  </label>
                );
              })}
            </div>
          </div>
        ))}
      </div>
      <button
        type="button"
        onClick={onCreate}
        disabled={pendingSelected.size === 0 || pendingBusy}
        className="mt-3 min-h-11 w-full rounded bg-teal-700 px-4 py-3 text-sm font-semibold text-white disabled:opacity-50 sm:w-auto"
      >
        {pendingBusy
          ? "Đang tạo PYC nháp..."
          : `Tạo PYC nháp cho ${pendingSelected.size} cấu kiện`}
      </button>
    </section>
  );
}
