import type { ManpowerEntry, Organization } from "../types";
import { parseManpowerCount, summarizeManpower } from "../lib/manpower";

type Props = {
  entries: ManpowerEntry[];
  onChange: (entries: ManpowerEntry[]) => void;
  organizations?: Organization[];
};

export default function ManpowerTable({ entries, onChange, organizations = [] }: Props) {
  const summary = summarizeManpower(entries);

  function update(index: number, patch: Partial<ManpowerEntry>) {
    onChange(entries.map((entry, idx) => (idx === index ? { ...entry, ...patch } : entry)));
  }

  function add() {
    onChange([...entries, { group_name: "", count: null }]);
  }

  function remove(index: number) {
    onChange(entries.filter((_, idx) => idx !== index));
  }

  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold">Nhân lực</h3>
          <p className="text-xs text-gray-500">
            Để trống = chưa rõ. Nhập <b>0</b> = đã xác định không có người.
          </p>
        </div>
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
          <input
            className="min-h-11 w-full rounded-lg border border-gray-300 px-3 text-base"
            placeholder="Nhóm / nhà thầu / công việc *"
            value={entry.group_name}
            onChange={(event) => update(index, { group_name: event.target.value })}
          />
          <input
            className="min-h-11 w-full rounded-lg border border-gray-300 px-3 text-base"
            placeholder="Họ tên (tuỳ chọn)"
            value={entry.person_name ?? ""}
            onChange={(event) => update(index, { person_name: event.target.value || null })}
          />
          {organizations.length > 0 && (
            <select
              className="min-h-11 w-full rounded-lg border border-gray-300 bg-white px-2 text-sm"
              value={entry.organization_id ?? ""}
              onChange={(event) =>
                update(index, { organization_id: event.target.value || null })
              }
            >
              <option value="">Không gắn tổ chức</option>
              {organizations.map((organization) => (
                <option key={organization.id} value={organization.id}>
                  {organization.name}
                </option>
              ))}
            </select>
          )}
          <div className="flex items-center gap-3">
            <label className="text-sm text-gray-600" htmlFor={`manpower-count-${index}`}>
              Số lượng
            </label>
            <input
              id={`manpower-count-${index}`}
              type="number"
              inputMode="numeric"
              min={0}
              step={1}
              className="min-h-11 flex-1 rounded-lg border border-gray-300 px-3 text-base"
              value={entry.count === null ? "" : entry.count}
              onChange={(event) =>
                update(index, { count: parseManpowerCount(event.target.value) })
              }
              placeholder="Trống = chưa rõ"
            />
            <span className="text-xs text-gray-500">0 ≠ chưa rõ</span>
          </div>
          <button
            type="button"
            className="min-h-9 px-1 text-sm text-red-600"
            onClick={() => remove(index)}
          >
            Xoá nhóm
          </button>
        </div>
      ))}

      {entries.length === 0 && (
        <p className="rounded-lg bg-gray-50 p-3 text-sm text-gray-500">
          Chưa có nhân lực. Bấm “+ Thêm” để ghi nhận.
        </p>
      )}

      <div className="flex flex-wrap gap-2 text-xs">
        <span className="rounded-full bg-blue-50 px-3 py-1 text-blue-800">
          Tổng đã biết: <b>{summary.knownTotal}</b>
        </span>
        {summary.unknownGroups.length > 0 && (
          <span className="rounded-full bg-amber-50 px-3 py-1 text-amber-800">
            Chưa rõ: {summary.unknownGroups.join(", ")}
          </span>
        )}
        {summary.zeroGroups.length > 0 && (
          <span className="rounded-full bg-gray-100 px-3 py-1 text-gray-700">
            0 người: {summary.zeroGroups.join(", ")}
          </span>
        )}
      </div>
    </section>
  );
}
