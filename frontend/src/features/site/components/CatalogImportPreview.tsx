import { useMemo } from "react";
import {
  summarizePreview,
  type ComponentCandidate,
  type ComponentFilters,
  type ComponentPreview,
} from "../lib/componentImport";
import {
  FOCUS_RING,
  FIELD_CLASS,
  PAGE_SIZE,
  SECONDARY_BUTTON,
  pageRemaining,
  type ComponentImportBusy,
} from "../lib/componentCatalogImport";
import CatalogCandidateCard from "./CatalogCandidateCard";

type Props = {
  preview: ComponentPreview;
  filters: ComponentFilters;
  visible: ComponentCandidate[];
  filteredCount: number;
  canCommit: boolean;
  confirmed: boolean;
  busy: ComponentImportBusy;
  workLinkLimit: number;
  onFilterChange: (patch: Partial<ComponentFilters>) => void;
  onConfirmedChange: (checked: boolean) => void;
  onLoadMoreVisible: () => void;
  onWorkLinkLimitChange: (limit: number) => void;
  onCommit: () => void;
};

export default function CatalogImportPreview({
  preview,
  filters,
  visible,
  filteredCount,
  canCommit,
  confirmed,
  busy,
  workLinkLimit,
  onFilterChange,
  onConfirmedChange,
  onLoadMoreVisible,
  onWorkLinkLimitChange,
  onCommit,
}: Props) {
  const summary = summarizePreview(preview);
  const zones = useMemo(
    () => Array.from(new Set(preview.components.map((item) => item.zone))),
    [preview],
  );
  const segmentNumbers = useMemo(
    () =>
      Array.from(
        new Set(preview.segments.map((item) => String(item.number))),
      ).sort((left, right) => Number(left) - Number(right)),
    [preview],
  );

  return (
    <div className="mt-3 space-y-3 rounded-xl border border-gray-200 bg-slate-50 p-3">
      <div>
        <h4 className="text-base font-semibold text-slate-900">
          Preview từ máy chủ
        </h4>
        <p className="break-all font-mono text-xs text-slate-600">
          sha256: {preview.source_sha256}
        </p>
        <p className="mt-1 text-sm text-slate-700">
          {summary.components} cấu kiện · {summary.segments} phân đoạn
          · {summary.workLinks} liên kết công việc
        </p>
      </div>

      {summary.conflicts > 0 ? (
        <div className="rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-900">
          <p className="font-semibold">
            {summary.conflicts} xung đột — không thể nhập
          </p>
          <ul className="mt-2 list-disc space-y-1 pl-5">
            {preview.conflicts.map((conflict, index) => (
              <li key={`${index}-${conflict}`}>{conflict}</li>
            ))}
          </ul>
        </div>
      ) : (
        <p className="rounded-lg border border-green-200 bg-green-50 p-2 text-sm text-green-800">
          Không có xung đột trong preview này.
        </p>
      )}

      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        <label className="text-xs font-semibold text-slate-700">
          Tìm trong preview
          <input
            className={`${FIELD_CLASS} mt-1`}
            value={filters.query}
            placeholder="mã, mã gốc, alias, dòng nguồn…"
            onChange={(event) => onFilterChange({ query: event.target.value })}
          />
        </label>
        <label className="text-xs font-semibold text-slate-700">
          Khu
          <select
            className={`${FIELD_CLASS} mt-1`}
            value={filters.zone}
            onChange={(event) => onFilterChange({ zone: event.target.value })}
          >
            <option value="">Tất cả khu</option>
            {zones.map((zone) => (
              <option key={zone} value={zone}>
                {zone}
              </option>
            ))}
          </select>
        </label>
        <label className="text-xs font-semibold text-slate-700">
          Loại
          <select
            className={`${FIELD_CLASS} mt-1`}
            value={filters.type}
            onChange={(event) => onFilterChange({ type: event.target.value })}
          >
            <option value="">Tất cả loại</option>
            <option value="pile">Cọc</option>
            <option value="beam">Dầm</option>
          </select>
        </label>
        <label className="text-xs font-semibold text-slate-700">
          Phân đoạn
          <select
            className={`${FIELD_CLASS} mt-1`}
            value={filters.segment}
            onChange={(event) => onFilterChange({ segment: event.target.value })}
          >
            <option value="">Tất cả phân đoạn</option>
            {segmentNumbers.map((number) => (
              <option key={number} value={number}>
                PĐ {number}
              </option>
            ))}
          </select>
        </label>
        <label className="text-xs font-semibold text-slate-700">
          Phạm vi
          <select
            className={`${FIELD_CLASS} mt-1`}
            value={filters.scope}
            onChange={(event) => onFilterChange({ scope: event.target.value })}
          >
            <option value="">Tất cả phạm vi</option>
            <option value="DESIGN_SCOPE">Theo thiết kế</option>
            <option value="ADDITIONAL_SCOPE">
              Phát sinh sửa chữa
            </option>
          </select>
        </label>
        <label className="text-xs font-semibold text-slate-700">
          Xác minh danh mục
          <select
            className={`${FIELD_CLASS} mt-1`}
            value={filters.verification}
            onChange={(event) =>
              onFilterChange({ verification: event.target.value })
            }
          >
            <option value="">Tất cả trạng thái</option>
            <option value="NEEDS_REVIEW">Chờ duyệt</option>
          </select>
        </label>
      </div>

      <p className="text-xs text-slate-600">
        Hiển thị {visible.length}/{filteredCount} cấu kiện (tổng{" "}
        {summary.components}).
      </p>
      <div className="space-y-2">
        {visible.map((component) => (
          <CatalogCandidateCard
            key={`${component.source_id}-${component.source_row}`}
            component={component}
          />
        ))}
        {filteredCount === 0 ? (
          <p className="rounded-lg border border-gray-200 p-3 text-sm text-slate-600">
            Không có dòng khớp bộ lọc.
          </p>
        ) : null}
      </div>
      {visible.length < filteredCount ? (
        <button
          type="button"
          className={`${SECONDARY_BUTTON} w-full`}
          onClick={onLoadMoreVisible}
        >
          Hiển thị thêm{" "}
          {pageRemaining(filteredCount, visible.length)} dòng
        </button>
      ) : null}

      <details className="rounded-lg border border-gray-200 bg-white p-2">
        <summary
          className={`flex min-h-11 cursor-pointer items-center justify-between gap-2 text-sm font-semibold text-slate-800 ${FOCUS_RING}`}
        >
          <span>Phân đoạn trong preview ({summary.segments})</span>
        </summary>
        <ul className="mt-2 space-y-1 text-xs text-slate-700">
          {preview.segments.map((segment) => (
            <li key={segment.source_id} className="font-mono">
              {segment.zone} · PĐ {segment.number} ·{" "}
              {segment.source_id}
            </li>
          ))}
        </ul>
      </details>

      <details className="rounded-lg border border-gray-200 bg-white p-2">
        <summary
          className={`flex min-h-11 cursor-pointer items-center justify-between gap-2 text-sm font-semibold text-slate-800 ${FOCUS_RING}`}
        >
          <span>Liên kết công việc ({summary.workLinks})</span>
        </summary>
        <div className="mt-2 max-h-80 space-y-1 overflow-auto text-xs">
          {preview.work_links.slice(0, workLinkLimit).map((link) => (
            <div
              key={`${link.source_id}-${link.dm_row}`}
              className="rounded border border-gray-100 p-2"
            >
              <p className="break-all font-mono">
                {link.code} · DM dòng {link.dm_row} · seed dòng{" "}
                {link.seed_row} · {link.source_id}
              </p>
              <p className="text-slate-700">{link.work}</p>
              <p className="break-all text-slate-600">
                {link.raw_location}
              </p>
            </div>
          ))}
        </div>
        <div className="mt-2 space-y-2">
          <p className="text-xs text-slate-600">
            Đang xem {Math.min(workLinkLimit, preview.work_links.length)}
            /{preview.work_links.length} liên kết.
          </p>
          {workLinkLimit < preview.work_links.length ? (
            <div className="flex flex-col gap-2 sm:flex-row">
              <button
                type="button"
                className={`${SECONDARY_BUTTON} flex-1`}
                onClick={() =>
                  onWorkLinkLimitChange(workLinkLimit + PAGE_SIZE)
                }
              >
                Hiển thị thêm{" "}
                {pageRemaining(
                  preview.work_links.length,
                  workLinkLimit,
                )}{" "}
                liên kết
              </button>
              <button
                type="button"
                className={`${SECONDARY_BUTTON} flex-1`}
                onClick={() =>
                  onWorkLinkLimitChange(preview.work_links.length)
                }
              >
                Hiển thị tất cả
              </button>
            </div>
          ) : null}
        </div>
      </details>

      <div className="rounded-lg border border-amber-300 bg-amber-50 p-3">
        <p className="text-sm font-semibold text-amber-950">
          Preview được gửi nguyên bản
        </p>
        <p className="mt-1 text-xs text-amber-950">
          Muốn sửa, hãy sửa workbook rồi tạo lại preview. Nếu còn
          xung đột, nút nhập bị khóa.
        </p>
        <label className="mt-3 flex min-h-11 items-start gap-2 text-sm text-amber-950">
          <input
            type="checkbox"
            className={`mt-1 h-5 w-5 rounded border-gray-400 ${FOCUS_RING}`}
            checked={confirmed}
            disabled={!canCommit || busy !== null}
            onChange={(event) => onConfirmedChange(event.target.checked)}
          />
          <span>
            Tôi đã kiểm tra workbook và preview khớp nhau, và xác nhận
            nhập {summary.components} cấu kiện / {summary.segments}{" "}
            phân đoạn.
          </span>
        </label>
        <button
          type="button"
          className={`mt-3 min-h-11 w-full rounded-lg bg-green-700 px-4 text-sm font-semibold text-white active:bg-green-800 disabled:cursor-not-allowed disabled:bg-gray-300 ${FOCUS_RING}`}
          disabled={!canCommit || !confirmed || busy !== null}
          onClick={onCommit}
        >
          {busy === "commit"
            ? "Đang nhập danh mục…"
            : "Xác nhận nhập danh mục"}
        </button>
      </div>
    </div>
  );
}
