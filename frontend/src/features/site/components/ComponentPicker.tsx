import { useMemo, useState } from "react";
import type { PhotoComponentOption } from "../lib/photoComponents";

export default function ComponentPicker({
  options,
  selectedIds,
  onChange,
  disabled = false,
  label = "Cấu kiện",
}: {
  options: PhotoComponentOption[];
  selectedIds: string[];
  onChange: (ids: string[]) => void;
  disabled?: boolean;
  label?: string;
}) {
  const [query, setQuery] = useState("");
  const byId = useMemo(
    () => new Map(options.map((option) => [option.id, option])),
    [options],
  );
  const selected = selectedIds
    .map((id) => byId.get(id))
    .filter((item): item is PhotoComponentOption => Boolean(item));
  const needle = query.trim().toLocaleLowerCase("vi");
  const results = useMemo(
    () =>
      options
        .filter((option) => {
          if (!needle) return true;
          return [option.code, option.zone, String(option.segment)]
            .join(" ")
            .toLocaleLowerCase("vi")
            .includes(needle);
        })
        .slice(0, 20),
    [needle, options],
  );

  function toggle(id: string) {
    onChange(
      selectedIds.includes(id)
        ? selectedIds.filter((item) => item !== id)
        : [...selectedIds, id],
    );
  }

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-2">
      <p className="text-xs font-semibold text-slate-700">{label}</p>
      <div className="mt-1 flex flex-wrap gap-1">
        {selected.length === 0 ? (
          <span className="text-xs text-slate-600">Chưa chọn cấu kiện</span>
        ) : (
          selected.map((item) => (
            <button
              key={item.id}
              type="button"
              className="inline-flex min-h-11 items-center gap-1 rounded-full border border-[#405e9b]/30 bg-[#eff4fc] px-3 text-xs font-semibold text-[#304b80]"
              disabled={disabled}
              onClick={() => toggle(item.id)}
              aria-label={`Bỏ ${item.code}`}
            >
              {item.code} <span aria-hidden="true">×</span>
            </button>
          ))
        )}
      </div>
      <input
        type="search"
        className="mt-2 min-h-11 w-full rounded-lg border border-slate-300 px-3 text-base sm:text-sm"
        placeholder="Tìm mã cọc/dầm (ví dụ F67)"
        aria-label="Tìm cấu kiện để gắn ảnh"
        value={query}
        disabled={disabled}
        onChange={(event) => setQuery(event.target.value)}
      />
      {options.length === 0 ? (
        <p className="mt-1 text-xs text-slate-600">
          Chưa có cấu kiện trong đợt đang chọn.
        </p>
      ) : (
        <div className="mt-1 max-h-48 overflow-auto">
          {results.map((option) => {
            const checked = selectedIds.includes(option.id);
            return (
              <label
                key={option.id}
                className={`flex min-h-11 cursor-pointer items-center gap-2 rounded-lg px-2 text-sm ${
                  checked ? "bg-[#eff4fc]" : "hover:bg-slate-50"
                }`}
              >
                <input
                  type="checkbox"
                  className="h-5 w-5 shrink-0 accent-[#405e9b]"
                  checked={checked}
                  disabled={disabled}
                  onChange={() => toggle(option.id)}
                />
                <span className="min-w-0 break-words">
                  <span className="font-mono font-semibold">{option.code}</span>
                  <span className="ml-1 text-xs text-slate-600">
                    {option.zone} · PĐ{option.segment}
                  </span>
                </span>
              </label>
            );
          })}
          {results.length === 0 ? (
            <p className="px-2 py-1 text-xs text-slate-600">Không có mã phù hợp.</p>
          ) : null}
        </div>
      )}
    </div>
  );
}
