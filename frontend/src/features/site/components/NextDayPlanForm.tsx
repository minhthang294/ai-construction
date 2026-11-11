import { NextDayPlan, WorkItem } from "../types";

type Props = {
  entries: NextDayPlan[];
  onChange: (entries: NextDayPlan[]) => void;
  defaultDate: string;
  workItems?: WorkItem[];
};

export default function NextDayPlanForm({
  entries,
  onChange,
  defaultDate,
  workItems = [],
}: Props) {
  function update(index: number, patch: Partial<NextDayPlan>) {
    onChange(entries.map((entry, idx) => (idx === index ? { ...entry, ...patch } : entry)));
  }

  function selectWorkItem(index: number, workItemId: string) {
    const item = workItems.find((candidate) => candidate.id === workItemId);
    const current = entries[index];
    update(index, {
      work_item_id: workItemId || null,
      location: current.location || item?.location || "",
      description: current.description || item?.name || "",
    });
  }

  function add() {
    onChange([
      ...entries,
      {
        plan_date: defaultDate,
        work_item_id: null,
        description: "",
        location: "",
        manpower: "",
        equipment: "",
        dependency: "",
      },
    ]);
  }

  function remove(index: number) {
    onChange(entries.filter((_, idx) => idx !== index));
  }

  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-lg font-semibold">Kế hoạch ngày mai</h3>
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
          <label className="block text-xs text-gray-600">
            Ngày kế hoạch
            <input
              type="date"
              className="mt-1 min-h-11 w-full rounded-lg border border-gray-300 px-3 text-base"
              value={entry.plan_date}
              onChange={(event) => update(index, { plan_date: event.target.value })}
            />
          </label>
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
          <textarea
            className="min-h-16 w-full rounded-lg border border-gray-300 px-3 py-2 text-base"
            placeholder="Mô tả công việc"
            value={entry.description ?? ""}
            onChange={(event) => update(index, { description: event.target.value })}
          />
          <input
            className="min-h-11 w-full rounded-lg border border-gray-300 px-3 text-base"
            placeholder="Vị trí"
            value={entry.location ?? ""}
            onChange={(event) => update(index, { location: event.target.value })}
          />
          <div className="grid grid-cols-2 gap-2">
            <input
              className="min-h-11 w-full rounded-lg border border-gray-300 px-3 text-sm"
              placeholder="Nhân lực"
              value={entry.manpower ?? ""}
              onChange={(event) => update(index, { manpower: event.target.value })}
            />
            <input
              className="min-h-11 w-full rounded-lg border border-gray-300 px-3 text-sm"
              placeholder="Thiết bị"
              value={entry.equipment ?? ""}
              onChange={(event) => update(index, { equipment: event.target.value })}
            />
          </div>
          <input
            className="min-h-11 w-full rounded-lg border border-gray-300 px-3 text-base"
            placeholder="Phụ thuộc / điều kiện"
            value={entry.dependency ?? ""}
            onChange={(event) => update(index, { dependency: event.target.value })}
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
          Chưa có kế hoạch ngày mai.
        </p>
      )}
    </section>
  );
}
