import { DailyWorkLog, WorkItem } from "../types";
import { fromLocalInputValue, toLocalInputValue } from "../lib/datetime";

type Props = {
  entries: DailyWorkLog[];
  onChange: (entries: DailyWorkLog[]) => void;
  workItems?: WorkItem[];
};

const STATUS_OPTIONS = [
  { value: "done", label: "Hoàn thành" },
  { value: "in_progress", label: "Đang làm" },
  { value: "planned", label: "Kế hoạch" },
  { value: "blocked", label: "Vướng mắc" },
];

function parseQuantity(raw: string): number | null {
  if (raw.trim() === "") return null;
  const value = Number(raw);
  return Number.isFinite(value) ? value : null;
}

export default function WorkLogForm({ entries, onChange, workItems = [] }: Props) {
  function update(index: number, patch: Partial<DailyWorkLog>) {
    onChange(entries.map((entry, idx) => (idx === index ? { ...entry, ...patch } : entry)));
  }

  function selectWorkItem(index: number, workItemId: string) {
    const item = workItems.find((candidate) => candidate.id === workItemId);
    const current = entries[index];
    update(index, {
      work_item_id: workItemId || null,
      location: current.location || item?.location || "",
      component: current.component || item?.component || "",
    });
  }

  function add() {
    onChange([
      ...entries,
      {
        work_item_id: null,
        location: "",
        component: "",
        quantity: null,
        unit: "",
        status: "done",
        notes: "",
      },
    ]);
  }

  function remove(index: number) {
    onChange(entries.filter((_, idx) => idx !== index));
  }

  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-lg font-semibold">Khối lượng thực hiện</h3>
        <button
          type="button"
          className="min-h-11 rounded-lg bg-blue-600 px-4 text-sm font-medium text-white active:bg-blue-700"
          onClick={add}
        >
          + Thêm
        </button>
      </div>

      {entries.map((entry, index) => (
        <div
          key={entry.id ?? index}
          className="space-y-2 rounded-xl border border-gray-200 bg-white p-3 shadow-sm"
        >
          {workItems.length > 0 && (
            <select
              className="min-h-11 w-full rounded-lg border border-gray-300 bg-white px-3 text-base"
              value={entry.work_item_id ?? ""}
              onChange={(event) => selectWorkItem(index, event.target.value)}
            >
              <option value="">— Chọn công việc (tuỳ chọn) —</option>
              {workItems.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.code} — {item.name}
                </option>
              ))}
            </select>
          )}
          <input
            className="min-h-11 w-full rounded-lg border border-gray-300 px-3 text-base"
            placeholder="Vị trí (vd: Trụ T1, cầu số 2)"
            value={entry.location ?? ""}
            onChange={(event) => update(index, { location: event.target.value })}
          />
          <input
            className="min-h-11 w-full rounded-lg border border-gray-300 px-3 text-base"
            placeholder="Hạng mục / component"
            value={entry.component ?? ""}
            onChange={(event) => update(index, { component: event.target.value })}
          />
          <div className="flex gap-2">
            <input
              type="number"
              inputMode="decimal"
              min={0}
              step="any"
              className="min-h-11 flex-1 rounded-lg border border-gray-300 px-3 text-base"
              placeholder="Số lượng"
              value={entry.quantity ?? ""}
              onChange={(event) =>
                update(index, { quantity: parseQuantity(event.target.value) })
              }
            />
            <input
              className="min-h-11 w-24 rounded-lg border border-gray-300 px-3 text-base"
              placeholder="ĐVT"
              value={entry.unit ?? ""}
              onChange={(event) => update(index, { unit: event.target.value })}
            />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <label className="text-xs text-gray-600">
              Bắt đầu
              <input
                type="datetime-local"
                className="mt-1 min-h-11 w-full rounded-lg border border-gray-300 px-2 text-sm"
                value={toLocalInputValue(entry.start_time)}
                onChange={(event) =>
                  update(index, { start_time: fromLocalInputValue(event.target.value) })
                }
              />
            </label>
            <label className="text-xs text-gray-600">
              Kết thúc
              <input
                type="datetime-local"
                className="mt-1 min-h-11 w-full rounded-lg border border-gray-300 px-2 text-sm"
                value={toLocalInputValue(entry.end_time)}
                onChange={(event) =>
                  update(index, { end_time: fromLocalInputValue(event.target.value) })
                }
              />
            </label>
          </div>
          <select
            className="min-h-11 w-full rounded-lg border border-gray-300 bg-white px-3 text-base"
            value={entry.status ?? "done"}
            onChange={(event) => update(index, { status: event.target.value })}
          >
            {STATUS_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <textarea
            className="min-h-16 w-full rounded-lg border border-gray-300 px-3 py-2 text-base"
            placeholder="Ghi chú"
            value={entry.notes ?? ""}
            onChange={(event) => update(index, { notes: event.target.value })}
          />
          <button
            type="button"
            className="min-h-9 px-1 text-sm text-red-600"
            onClick={() => remove(index)}
          >
            Xoá dòng
          </button>
        </div>
      ))}

      {entries.length === 0 && (
        <p className="rounded-lg bg-gray-50 p-3 text-sm text-gray-500">
          Chưa có khối lượng. Bấm “+ Thêm” để ghi nhận.
        </p>
      )}
    </section>
  );
}
