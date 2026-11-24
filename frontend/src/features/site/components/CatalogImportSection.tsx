import type { RefObject } from "react";
import type {
  ComponentCandidate,
  ComponentFilters,
  ComponentImportResult,
  ComponentPreview,
} from "../lib/componentImport";
import {
  DETAILS_SUMMARY,
  FIELD_CLASS,
  FOCUS_RING,
  SECONDARY_BUTTON,
  type ComponentImportBusy,
} from "../lib/componentCatalogImport";
import CatalogImportPreview from "./CatalogImportPreview";

type Props = {
  file: File | null;
  preview: ComponentPreview | null;
  busy: ComponentImportBusy;
  error: string | null;
  message: string | null;
  result: ComponentImportResult | null;
  inputRef: RefObject<HTMLInputElement | null>;
  filters: ComponentFilters;
  visible: ComponentCandidate[];
  filteredCount: number;
  canCommit: boolean;
  confirmed: boolean;
  workLinkLimit: number;
  onFileChange: (next: File | null) => void;
  onPreview: () => void;
  onFilterChange: (patch: Partial<ComponentFilters>) => void;
  onConfirmedChange: (checked: boolean) => void;
  onLoadMoreVisible: () => void;
  onWorkLinkLimitChange: (limit: number) => void;
  onCommit: () => void;
};

export default function CatalogImportSection({
  file,
  preview,
  busy,
  error,
  message,
  result,
  inputRef,
  filters,
  visible,
  filteredCount,
  canCommit,
  confirmed,
  workLinkLimit,
  onFileChange,
  onPreview,
  onFilterChange,
  onConfirmedChange,
  onLoadMoreVisible,
  onWorkLinkLimitChange,
  onCommit,
}: Props) {
  return (
    <details className="rounded-xl border border-gray-200 bg-white shadow-sm">
      <summary className={DETAILS_SUMMARY}>
        <span className="text-base font-semibold text-slate-900">
          Nhập danh mục từ workbook
        </span>
        <span className="text-xs font-normal text-slate-600">
          XLSX · tối đa 10 MB
        </span>
      </summary>
      <div className="border-t border-gray-100 p-3">
        <p className="text-xs text-slate-600">
          Máy chủ đọc file và luôn tạo preview trước khi nhập. UI không tự
          sửa dữ liệu.
        </p>
        <input
          ref={inputRef}
          type="file"
          accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
          disabled={busy !== null}
          aria-label="Chọn workbook danh mục cấu kiện"
          className={`${FIELD_CLASS} mt-3 file:mr-3 file:min-h-11 file:rounded-md file:border-0 file:bg-slate-800 file:px-3 file:py-2 file:text-sm file:font-semibold file:text-white`}
          onChange={(event) =>
            onFileChange(event.target.files?.[0] ?? null)
          }
        />
        <div className="mt-3 flex flex-col gap-2 sm:flex-row">
          <button
            type="button"
            className={`min-h-11 flex-1 rounded-lg bg-blue-700 px-4 text-sm font-semibold text-white active:bg-blue-800 disabled:cursor-not-allowed disabled:bg-gray-300 ${FOCUS_RING}`}
            disabled={!file || busy !== null}
            onClick={onPreview}
          >
            {busy === "preview"
              ? "Đang đọc workbook…"
              : "Tạo bản xem trước"}
          </button>
          {preview ? (
            <button
              type="button"
              className={`${SECONDARY_BUTTON} sm:w-auto`}
              disabled={busy !== null}
              onClick={() => onFileChange(null)}
            >
              Hủy preview
            </button>
          ) : null}
        </div>

        {error ? (
          <p
            role="alert"
            className="mt-3 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800"
          >
            {error}
          </p>
        ) : null}
        {message ? (
          <p
            role="status"
            className="mt-3 rounded-lg border border-green-200 bg-green-50 p-3 text-sm text-green-800"
          >
            {message}
          </p>
        ) : null}
        {result ? (
          <dl className="mt-3 grid grid-cols-3 gap-2 rounded-lg border border-green-200 bg-white p-3 text-center text-sm">
            <div>
              <dt className="text-xs text-slate-600">Cấu kiện</dt>
              <dd className="text-lg font-semibold text-slate-900">
                {result.components}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-slate-600">Phân đoạn</dt>
              <dd className="text-lg font-semibold text-slate-900">
                {result.segments}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-slate-600">Liên kết</dt>
              <dd className="text-lg font-semibold text-slate-900">
                {result.work_links}
              </dd>
            </div>
          </dl>
        ) : null}

        {preview ? (
          <CatalogImportPreview
            preview={preview}
            filters={filters}
            visible={visible}
            filteredCount={filteredCount}
            canCommit={canCommit}
            confirmed={confirmed}
            busy={busy}
            workLinkLimit={workLinkLimit}
            onFilterChange={onFilterChange}
            onConfirmedChange={onConfirmedChange}
            onLoadMoreVisible={onLoadMoreVisible}
            onWorkLinkLimitChange={onWorkLinkLimitChange}
            onCommit={onCommit}
          />
        ) : null}
      </div>
    </details>
  );
}
