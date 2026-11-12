import type { DailyWorkLog, WorkItem } from "../types";
import { formatISODate } from "../lib/datetime";
import {
  buildWorkItemGroups,
  normalizeWorkItemName,
  workItemNameById,
  workItemNameKey,
} from "../lib/workItems";

type Props = {
  entries: DailyWorkLog[];
  onChange: (entries: DailyWorkLog[]) => void;
  workItems?: WorkItem[];
  /** Date of the whole report; work logs no longer have their own time range. */
  reportDate?: string | null;
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

export default function WorkLogForm({
  entries,
  onChange,
  workItems = [],
  reportDate,
}: Props) {
  const nameById = workItemNameById(workItems);
  const groups = buildWorkItemGroups(
    workItems,
    entries.map((entry) => entry.work_name),
  );
  // Select values must match an option exactly; prefer the catalog casing.
  const canonicalByName = new Map(
    groups.flatMap((group) =>
      group.names.map((name) => [workItemNameKey(name), name] as const),
    ),
  );

  function update(index: number, patch: Partial<DailyWorkLog>) {
    onChange(entries.map((entry, idx) => (idx === index ? { ...entry, ...patch } : entry)));
  }

  /** Display name for an entry; legacy ids resolve through the catalog. */
  function entryWorkName(entry: DailyWorkLog): string {
    const raw = entry.work_name
      ? normalizeWorkItemName(entry.work_name)
      : entry.work_item_id
        ? nameById.get(entry.work_item_id) ?? ""
        : "";
    if (!raw) return "";
    return canonicalByName.get(workItemNameKey(raw)) ?? raw;
  }

  function selectWorkName(index: number, value: string) {
    const entry = entries[index];
    const currentName = entryWorkName(entry);
    const nextName = normalizeWorkItemName(value);
    if (!nextName) {
      update(index, { work_item_id: null, work_name: null });
      return;
    }
    // Do not touch legacy ids or the user's location/component when the
    // selected name is unchanged.
    if (nextName === currentName) return;
    update(index, { work_name: nextName, work_item_id: null });
  }

  function add() {
    onChange([
      ...entries,
      {
        work_item_id: null,
        work_name: null,
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
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold">Công việc thực hiện hôm nay</h3>
          <p className="text-xs text-gray-500">
            {reportDate
              ? `Ngày báo cáo: ${formatISODate(reportDate)}`
              : "Dùng ngày báo cáo ở đầu trang."}
          </p>
        </div>
        <button
          type="button"
          className="min-h-11 shrink-0 rounded-lg bg-blue-600 px-4 text-sm font-medium text-white active:bg-blue-700"
          onClick={add}
        >
          + Thêm công việc
        </button>
      </div>

      {entries.map((entry, index) => {
        const selectedName = entryWorkName(entry);
        return (
          <div
            key={entry.id ?? index}
            className="space-y-2 rounded-xl border border-gray-200 bg-white p-3 shadow-sm"
          >
            <label className="block text-xs font-medium text-gray-600">
              Công việc
              <select
                className="mt-1 min-h-11 w-full rounded-lg border border-gray-300 bg-white px-3 text-base"
                value={selectedName}
                aria-label={`Công việc dòng ${index + 1}`}
                onChange={(event) => selectWorkName(index, event.target.value)}
              >
                <option value="">— Chọn công việc (tuỳ chọn) —</option>
                {groups.map((group) => (
                  <optgroup key={group.key} label={group.label}>
                    {group.names.map((name) => (
                      <option key={`${group.key}:${name}`} value={name}>
                        {name}
                      </option>
                    ))}
                  </optgroup>
                ))}
              </select>
            </label>

            <label className="block text-xs font-medium text-gray-600">
              Vị trí
              <input
                className="mt-1 min-h-11 w-full rounded-lg border border-gray-300 px-3 text-base"
                placeholder="Vị trí (vd: Cọc A2, A8...)"
                aria-label={`Vị trí dòng ${index + 1}`}
                value={entry.location ?? ""}
                onChange={(event) => update(index, { location: event.target.value })}
              />
            </label>

            <details className="rounded-lg border border-gray-200 p-2">
              <summary className="min-h-9 cursor-pointer py-1 text-sm font-medium text-gray-700">
                Chi tiết
              </summary>
              <div className="mt-2 space-y-2">
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
                <label className="block text-xs font-medium text-gray-600">
                  Trạng thái
                  <select
                    className="mt-1 min-h-11 w-full rounded-lg border border-gray-300 bg-white px-3 text-base"
                    value={entry.status ?? "done"}
                    onChange={(event) => update(index, { status: event.target.value })}
                  >
                    {STATUS_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>
                <textarea
                  className="min-h-16 w-full rounded-lg border border-gray-300 px-3 py-2 text-base"
                  placeholder="Ghi chú"
                  value={entry.notes ?? ""}
                  onChange={(event) => update(index, { notes: event.target.value })}
                />
              </div>
            </details>

            <button
              type="button"
              className="min-h-9 px-1 text-sm text-red-600"
              onClick={() => remove(index)}
            >
              Xoá dòng
            </button>
          </div>
        );
      })}

      {entries.length === 0 && (
        <p className="rounded-lg bg-gray-50 p-3 text-sm text-gray-500">
          Chưa có công việc thực hiện hôm nay. Bấm “+ Thêm công việc” để ghi nhận.
        </p>
      )}
    </section>
  );
}
