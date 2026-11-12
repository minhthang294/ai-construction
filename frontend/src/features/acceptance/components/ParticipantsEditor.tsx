import type { ParticipantInput, ParticipantRole } from "../types";

type Props = {
  items: ParticipantInput[];
  onChange: (items: ParticipantInput[]) => void;
  disabled?: boolean;
};

const ROLE_OPTIONS: ReadonlyArray<{ value: ParticipantRole; label: string }> = [
  { value: "investor", label: "Chủ đầu tư" },
  { value: "supervisor", label: "Tư vấn giám sát" },
  { value: "contractor", label: "Nhà thầu thi công" },
  { value: "other", label: "Khác" },
];

const MAX_PARTICIPANTS = 6;

export default function ParticipantsEditor({ items, onChange, disabled = false }: Props) {
  function update(index: number, patch: Partial<ParticipantInput>) {
    onChange(items.map((item, i) => (i === index ? { ...item, ...patch } : item)));
  }

  function add() {
    if (items.length >= MAX_PARTICIPANTS) return;
    onChange([
      ...items,
      {
        role: "other",
        person_name: "",
        position: "",
        organization: "",
        sort_order: items.length,
      },
    ]);
  }

  function remove(index: number) {
    onChange(
      items
        .filter((_, i) => i !== index)
        .map((item, i) => ({ ...item, sort_order: i })),
    );
  }

  return (
    <section className="space-y-2" aria-label="Thành phần tham gia nghiệm thu">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold">Thành phần tham gia</h3>
        <button
          type="button"
          onClick={add}
          disabled={disabled || items.length >= MAX_PARTICIPANTS}
          className="min-h-11 rounded border border-teal-700 px-3 py-2 text-sm text-teal-800 disabled:opacity-50"
        >
          + Thêm người
        </button>
      </div>

      {items.length === 0 && (
        <p className="text-sm text-slate-500">
          Chưa có thành phần. Thêm đúng người tham gia của lần nghiệm thu này; hệ
          thống không dùng lại tên từ mẫu cũ.
        </p>
      )}

      <ul className="space-y-3">
        {items.map((item, index) => (
          <li key={index} className="border rounded p-3 bg-white space-y-2">
            <div className="grid gap-2 sm:grid-cols-2">
              <label className="block text-sm">
                Vai trò
                <select
                  className="mt-1 min-h-11 w-full rounded border p-3"
                  value={item.role}
                  disabled={disabled}
                  onChange={(event) =>
                    update(index, { role: event.target.value as ParticipantRole })
                  }
                >
                  {ROLE_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block text-sm">
                Họ tên <span className="text-rose-600">*</span>
                <input
                  className="mt-1 min-h-11 w-full rounded border p-3"
                  value={item.person_name}
                  disabled={disabled}
                  placeholder="Nhập họ tên người tham gia"
                  onChange={(event) => update(index, { person_name: event.target.value })}
                />
              </label>
              <label className="block text-sm">
                Chức vụ
                <input
                  className="mt-1 min-h-11 w-full rounded border p-3"
                  value={item.position ?? ""}
                  disabled={disabled}
                  onChange={(event) => update(index, { position: event.target.value })}
                />
              </label>
              <label className="block text-sm">
                Đơn vị
                <input
                  className="mt-1 min-h-11 w-full rounded border p-3"
                  value={item.organization ?? ""}
                  disabled={disabled}
                  onChange={(event) => update(index, { organization: event.target.value })}
                />
              </label>
            </div>
            <button
              type="button"
              onClick={() => remove(index)}
              disabled={disabled}
              className="inline-flex min-h-11 items-center text-sm text-rose-700 underline disabled:opacity-50"
            >
              Xóa người này
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
