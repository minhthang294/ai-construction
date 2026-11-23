export type ConstructionProgressSummary = {
  components: { verified: number };
  construction: {
    not_started: number;
    in_progress: number;
    completed: number;
    blocked: number;
    completion_ratio: number;
  };
  acceptance?: { confirmed: number; completion_ratio: number };
};

const statusStyles = [
  ["completed", "Hoàn thành", "bg-emerald-700"],
  ["in_progress", "Đang thi công", "bg-sky-700"],
  ["blocked", "Tạm dừng", "bg-amber-700"],
  ["not_started", "Chưa bắt đầu", "bg-slate-500"],
] as const;

const percentage = new Intl.NumberFormat("vi-VN", {
  style: "percent",
  maximumFractionDigits: 1,
});

export default function ConstructionProgressChart({ summary }: { summary: ConstructionProgressSummary }) {
  const { verified } = summary.components;
  const progress = summary.construction;

  if (!verified) {
    return <p className="mt-3 text-sm text-slate-600">Chưa có cấu kiện đã xác minh.</p>;
  }

  return (
    <figure className="mt-3 space-y-4">
      <figcaption className="text-sm leading-5 text-slate-600">
        Trạng thái ghi nhận gần nhất của các cấu kiện đã xác minh.
      </figcaption>
      <div className="grid items-center gap-5 min-[540px]:grid-cols-[minmax(8rem,.75fr)_minmax(0,1.25fr)] lg:grid-cols-1 xl:grid-cols-[minmax(8rem,.75fr)_minmax(0,1.25fr)]">
        <div className="text-center">
          <div
            className="mx-auto grid size-28 place-items-center rounded-full"
            style={{
              background: `conic-gradient(#047857 ${progress.completion_ratio * 100}%, #e2e8f0 0)`,
            }}
          >
            <span className="grid size-[5.5rem] place-items-center rounded-full bg-white text-xl font-bold tabular-nums text-slate-950">
              {percentage.format(progress.completion_ratio)}
            </span>
          </div>
          <p className="mt-2 text-sm font-semibold text-slate-900">Ghi nhận hoàn thành</p>
          <p className="text-sm tabular-nums text-slate-600">{progress.completed}/{verified} cấu kiện</p>
        </div>
        <ul className="min-w-0 space-y-3" aria-label="Số cấu kiện theo trạng thái thi công">
          {statusStyles.map(([key, label, color]) => {
            const count = progress[key];
            return (
              <li key={key}>
                <div className="mb-1 flex flex-wrap items-baseline justify-between gap-x-2 text-sm">
                  <span className="text-slate-800">{label}</span>
                  <span className="font-semibold tabular-nums text-slate-700">
                    {count} · {percentage.format(count / verified)}
                  </span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-slate-100" aria-hidden="true">
                  <div className={`h-full rounded-full ${color}`} style={{ width: `${(count / verified) * 100}%` }} />
                </div>
              </li>
            );
          })}
        </ul>
      </div>
    </figure>
  );
}
