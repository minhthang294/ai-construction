import type { ConstructionBatch } from "../lib/batches";

export default function ConstructionBatchSelector({
  batches,
  value,
  onChange,
  loading = false,
  error = null,
  onManage,
}: {
  batches: ConstructionBatch[];
  value: string;
  onChange: (batchId: string) => void;
  loading?: boolean;
  error?: string | null;
  onManage?: () => void;
}) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm" aria-label="Đợt thi công">
      <div className="flex flex-wrap items-end gap-2">
        <label className="min-w-0 flex-1 text-xs font-medium text-slate-700">
          Đợt thi công
          <select
            className="mt-1 min-h-11 w-full min-w-0 rounded-lg border border-slate-300 bg-white px-3 text-base text-slate-900 sm:text-sm"
            value={value}
            disabled={loading}
            onChange={(event) => onChange(event.target.value)}
          >
            <option value="">Tất cả đợt</option>
            {batches.map((batch) => (
              <option key={batch.id} value={batch.id}>
                {batch.name} ({batch.component_count})
              </option>
            ))}
          </select>
        </label>
        {onManage ? (
          <button
            type="button"
            className="min-h-11 rounded-lg border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-800 hover:bg-slate-50"
            onClick={onManage}
          >
            Quản lý đợt
          </button>
        ) : null}
      </div>
      {loading ? (
        <p role="status" className="mt-2 text-xs text-slate-600">Đang tải đợt thi công…</p>
      ) : null}
      {error ? (
        <p role="alert" className="mt-2 text-xs text-red-700">{error}</p>
      ) : null}
      {!loading && !error && batches.length === 0 ? (
        <p className="mt-2 text-xs text-slate-600">
          Chưa có đợt thi công. Tạo đợt để gom cấu kiện ở nhiều khu.
        </p>
      ) : null}
    </section>
  );
}
