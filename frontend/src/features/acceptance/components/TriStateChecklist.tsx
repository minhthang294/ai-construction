import type { ChecklistInput, TriState } from "../types";

type Props = {
  items: ChecklistInput[];
  onChange: (items: ChecklistInput[]) => void;
  disabled?: boolean;
};

const STATE_OPTIONS: ReadonlyArray<{ value: TriState; label: string }> = [
  { value: "yes", label: "Có" },
  { value: "no", label: "Không" },
  { value: "unconfirmed", label: "Chưa xác nhận" },
];

const STATE_STYLES: Record<TriState, string> = {
  yes: "bg-emerald-600 text-white border-emerald-600",
  no: "bg-rose-600 text-white border-rose-600",
  unconfirmed: "bg-amber-100 text-amber-900 border-amber-400",
};

export default function TriStateChecklist({ items, onChange, disabled = false }: Props) {
  function setState(index: number, state: TriState) {
    onChange(items.map((item, i) => (i === index ? { ...item, state } : item)));
  }

  const unresolved = items.filter(
    (item) => item.state !== "yes" && item.state !== "no",
  ).length;

  return (
    <section className="space-y-2" aria-label="Checklist hồ sơ nghiệm thu">
      <div className="flex items-center justify-between gap-2">
        <h3 className="font-semibold">Checklist hồ sơ</h3>
        <span
          className={`text-sm rounded px-2 py-1 ${
            unresolved ? "bg-amber-100 text-amber-900" : "bg-emerald-100 text-emerald-900"
          }`}
          role="status"
        >
          {unresolved ? `${unresolved} mục chưa xác nhận` : "Đã xác nhận đủ"}
        </span>
      </div>

      <ol className="space-y-2">
        {items.map((item, index) => (
          <li key={`${item.sort_order}-${item.item}`} className="border rounded p-2 bg-white">
            <p className="text-sm font-medium mb-2">
              <span className="text-slate-500 mr-1">{index + 1}.</span>
              {item.item}
            </p>
            <div className="flex flex-wrap gap-2" role="group" aria-label={item.item}>
              {STATE_OPTIONS.map((option) => {
                const selected = item.state === option.value;
                return (
                  <button
                    key={option.value}
                    type="button"
                    disabled={disabled}
                    aria-pressed={selected}
                    onClick={() => setState(index, option.value)}
                    className={`min-h-11 min-w-11 rounded border px-3 text-sm disabled:opacity-50 ${
                      selected
                        ? STATE_STYLES[option.value]
                        : "bg-white text-slate-700 border-slate-300"
                    }`}
                  >
                    {option.label}
                  </button>
                );
              })}
            </div>
            {item.evidence_refs.length > 0 && (
              <p className="mt-2 text-sm text-slate-500">
                Bằng chứng: {item.evidence_refs.join(", ")}
              </p>
            )}
          </li>
        ))}
      </ol>
    </section>
  );
}

