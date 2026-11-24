import type {
  ComponentSegment,
  ComponentSummary,
} from "../lib/componentImport";
import {
  FIELD_CLASS,
  PRIMARY_BUTTON,
  SECONDARY_BUTTON,
  catalogEmptyMessage,
  catalogVerificationLabel,
  componentTypeLabel,
  pageRemaining,
  segmentLabel,
} from "../lib/componentCatalogImport";
import BatchZoneBadge from "./BatchZoneBadge";

type Props = {
  catalog: ComponentSummary[];
  segments: ComponentSegment[];
  search: string;
  catalogBusy: boolean;
  catalogError: string | null;
  catalogLimit: number;
  primaryZone: string | null;
  onSearchChange: (value: string) => void;
  onSearch: () => void;
  onLoadMore: () => void;
};

export default function CatalogComponentList({
  catalog,
  segments,
  search,
  catalogBusy,
  catalogError,
  catalogLimit,
  primaryZone,
  onSearchChange,
  onSearch,
  onLoadMore,
}: Props) {
  const visibleCatalog = catalog.slice(0, catalogLimit);
  const segmentById = new Map(segments.map((item) => [item.id, item]));

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-3 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="text-base font-semibold text-slate-900">
            Danh mục hiện có
          </h3>
          <p className="text-xs text-slate-600">
            Tìm theo mã chuẩn hoặc tên khác đã nhập.
          </p>
        </div>
        <span className="text-xs font-medium text-slate-600">
          {catalog.length} dòng
        </span>
      </div>

      <form
        className="mt-3 flex flex-col gap-2 sm:flex-row"
        onSubmit={(event) => {
          event.preventDefault();
          onSearch();
        }}
      >
        <input
          className={`${FIELD_CLASS} min-w-0 flex-1`}
          value={search}
          placeholder="Ví dụ I40-42"
          aria-label="Tìm cấu kiện theo mã hoặc tên khác"
          onChange={(event) => onSearchChange(event.target.value)}
        />
        <button
          type="submit"
          className={`${PRIMARY_BUTTON} sm:w-auto`}
          disabled={catalogBusy}
        >
          {catalogBusy ? "Đang tải…" : "Tìm"}
        </button>
      </form>

      {catalogError ? (
        <p
          role="alert"
          className="mt-2 rounded-lg border border-red-200 bg-red-50 p-2 text-sm text-red-800"
        >
          {catalogError}
        </p>
      ) : null}

      <div className="mt-3 space-y-2">
        {visibleCatalog.map((component) => {
          const segment = segmentById.get(component.segment_id);
          return (
            <div
              key={component.id}
              className="rounded-lg border border-gray-200 p-3 text-sm"
            >
              <p className="break-all font-mono text-base font-semibold text-slate-900">
                {component.canonical_code}
              </p>
              {component.raw_code !== component.canonical_code ? (
                <p className="font-mono text-xs text-amber-700">
                  Mã gốc: {component.raw_code}
                </p>
              ) : null}
              <p className="mt-1 text-xs text-slate-600">
                {segment ? segmentLabel(segment) : component.segment_id} ·{" "}
                <span>{componentTypeLabel(component.type)}</span> ·{" "}
                <span>{catalogVerificationLabel(component.verification)}</span>
              </p>
              <div className="mt-1">
                <BatchZoneBadge
                  zone={component.zone ?? segment?.zone ?? ""}
                  segmentNumber={component.segment_number ?? segment?.number ?? 0}
                  primaryZone={primaryZone}
                />
              </div>
            </div>
          );
        })}
        {!catalogBusy && catalog.length === 0 && !catalogError ? (
          <p className="rounded-lg border border-gray-200 p-3 text-sm text-slate-600">
            {catalogEmptyMessage(search)}
          </p>
        ) : null}
      </div>

      {catalogLimit < catalog.length ? (
        <div className="mt-3 space-y-2">
          <p className="text-xs text-slate-600">
            Hiển thị {visibleCatalog.length}/{catalog.length} dòng.
          </p>
          <button
            type="button"
            className={`${SECONDARY_BUTTON} w-full`}
            onClick={onLoadMore}
          >
            Xem thêm {pageRemaining(catalog.length, catalogLimit)} dòng
          </button>
        </div>
      ) : null}
    </div>
  );
}
