import { SITE_NOTE_FIELDS } from "../types";
import type { SiteNotes } from "../types";

type Props = {
  notes: SiteNotes;
  onChange: (notes: SiteNotes) => void;
};

export default function SiteNotesForm({ notes, onChange }: Props) {
  function update(key: (typeof SITE_NOTE_FIELDS)[number]["key"], value: string) {
    onChange({ ...notes, [key]: value });
  }

  return (
    <details className="rounded-xl bg-white p-3 shadow-sm">
      <summary className="cursor-pointer text-lg font-semibold">
        Ghi chú hiện trường (tuỳ chọn)
      </summary>
      <p className="mt-1 text-xs text-gray-500">
        Chỉ điền nội dung có thật; mục để trống sẽ không xuất hiện trong báo cáo.
      </p>
      <div className="mt-3 space-y-3">
        {SITE_NOTE_FIELDS.map((field) => (
          <label key={field.key} className="block text-sm text-gray-700">
            {field.label}
            <textarea
              className="mt-1 min-h-16 w-full rounded-lg border border-gray-300 px-3 py-2 text-base"
              placeholder={field.placeholder}
              value={notes[field.key] ?? ""}
              onChange={(event) => update(field.key, event.target.value)}
            />
          </label>
        ))}
      </div>
    </details>
  );
}
