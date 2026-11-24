import { STATUS_LEGEND } from "../lib/statusLabels";
import type { Tab } from "./acceptancePageModel";

type Props = {
  tab: Tab;
  onSwitchTab: (tab: Tab) => void;
};

export default function AcceptanceHeader({ tab, onSwitchTab }: Props) {
  return (
    <>
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.14em] text-[#405e9b]">Điều hành</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight text-slate-950">Nghiệm thu (PYC / BBNT)</h1>
          <p className="mt-1 text-sm text-slate-600">Lập phiếu yêu cầu, biên bản và xuất hồ sơ nghiệm thu.</p>
        </div>
        <div role="group" aria-label="Khu vực nghiệm thu" className="flex gap-2">
          <button
            type="button"
            aria-pressed={tab === "requests"}
            onClick={() => onSwitchTab("requests")}
            className={`min-h-11 rounded-xl px-3 py-2 text-sm font-medium ${tab === "requests" ? "bg-teal-700 text-white" : "border bg-white"}`}
          >
            Phiếu yêu cầu (PYC)
          </button>
          <button
            type="button"
            aria-pressed={tab === "records"}
            onClick={() => onSwitchTab("records")}
            className={`min-h-11 rounded-xl px-3 py-2 text-sm font-medium ${tab === "records" ? "bg-teal-700 text-white" : "border bg-white"}`}
          >
            Biên bản nghiệm thu (BBNT)
          </button>
        </div>
      </header>

      <div className="flex flex-wrap items-center gap-2" aria-label="Chú giải trạng thái">
        <span className="text-sm font-medium text-slate-600">Trạng thái:</span>
        {STATUS_LEGEND.map((item) => (
          <span
            key={item.label}
            className={`rounded-full border px-2 py-1 text-sm ${item.className}`}
          >
            {item.label}
          </span>
        ))}
      </div>
    </>
  );
}
