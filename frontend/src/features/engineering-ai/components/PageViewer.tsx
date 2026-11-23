import { useEffect, useState } from "react";
import { fetchResourceBlob, getDocumentPage } from "../lib/api";
import type { DocumentPage } from "../types";
import {
  clampPageZoom,
  MAX_PAGE_ZOOM,
  MIN_PAGE_ZOOM,
  stepPageZoom,
} from "../lib/pageViewport";
import {
  BUTTON_SECONDARY,
  CARD,
  cx,
  META_TEXT,
  PANEL_ALERT,
  SECTION_TEXT,
  SECTION_TITLE,
} from "../lib/ui";
import { MinusIcon, PlusIcon, XIcon } from "./icons";
import PageExtractionPanel from "./PageExtractionPanel";

type Props = {
  projectId: string;
  documentId: string;
  pageNumber: number;
  totalPages: number;
  onClose: () => void;
  onPageChange: (pageNumber: number) => void;
  closeLabel?: string;
};

export default function PageViewer({
  projectId,
  documentId,
  pageNumber,
  totalPages,
  onClose,
  onPageChange,
  closeLabel = "Đóng",
}: Props) {
  const [page, setPage] = useState<DocumentPage | null>(null);
  const [renderUrl, setRenderUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [zoom, setZoom] = useState(MIN_PAGE_ZOOM);

  useEffect(() => {
    let cancelled = false;
    let objectUrl: string | null = null;

    (async () => {
      setLoading(true);
      setError(null);
      setPage(null);
      setRenderUrl(null);
      setZoom(MIN_PAGE_ZOOM);
      try {
        const result = await getDocumentPage(projectId, documentId, pageNumber);
        if (cancelled) return;
        setPage(result);
        if (result.render_url) {
          try {
            const blob = await fetchResourceBlob(result.render_url);
            if (cancelled) return;
            objectUrl = URL.createObjectURL(blob);
            setRenderUrl(objectUrl);
          } catch {
            // Text extraction is still useful when a scan render is absent.
          }
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Không tải được trang.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [projectId, documentId, pageNumber]);

  return (
    <section
      aria-busy={loading}
      className={cx(CARD, "min-w-0 overflow-hidden")}
    >
      <div className="border-b border-slate-200 p-4 sm:p-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <h2 className={SECTION_TITLE}>Trang {pageNumber}</h2>
            {page && (
              <p className={cx(META_TEXT, "mt-1 [overflow-wrap:anywhere]")}>
                {page.drawing_number && `Bản vẽ ${page.drawing_number}`}
                {page.revision && ` · Rev ${page.revision}`}
              </p>
            )}
          </div>
          <button
            type="button"
            className={cx(BUTTON_SECONDARY, "w-full shrink-0 sm:w-auto")}
            onClick={onClose}
          >
            <XIcon className="h-4 w-4" />
            {closeLabel}
          </button>
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-2">
          <button
            type="button"
            className={cx(BUTTON_SECONDARY, "flex-1 sm:flex-none")}
            onClick={() => onPageChange(pageNumber - 1)}
            disabled={pageNumber <= 1 || loading}
          >
            Trang trước
          </button>
          <span
            aria-live="polite"
            className="flex min-h-11 min-w-16 items-center justify-center rounded-lg bg-slate-100 px-3 text-sm font-medium text-slate-700 tabular-nums"
          >
            {pageNumber}/{Math.max(1, totalPages)}
          </span>
          <button
            type="button"
            className={cx(BUTTON_SECONDARY, "flex-1 sm:flex-none")}
            onClick={() => onPageChange(pageNumber + 1)}
            disabled={pageNumber >= totalPages || loading}
          >
            Trang sau
          </button>
        </div>
      </div>

      <div className="space-y-4 p-4 sm:p-5">
        {loading && (
          <div role="status" aria-live="polite" className="space-y-3">
            <span className="sr-only">Đang tải trang...</span>
            <div className="h-5 w-40 animate-pulse rounded bg-slate-200 motion-reduce:animate-none" />
            <div className="h-48 animate-pulse rounded-lg bg-slate-100 motion-reduce:animate-none" />
            <div className="h-4 w-2/3 animate-pulse rounded bg-slate-200 motion-reduce:animate-none" />
          </div>
        )}

        {error && (
          <div role="alert" className={PANEL_ALERT}>
            {error}
          </div>
        )}

        {page && (
          <>
            {renderUrl ? (
              <>
                <div
                  role="toolbar"
                  aria-label="Điều khiển xem bản vẽ"
                  className="flex flex-wrap items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 p-2"
                >
                  <button
                    type="button"
                    className={cx(BUTTON_SECONDARY, "min-w-11 px-3")}
                    onClick={() => setZoom((current) => stepPageZoom(current, -1))}
                    disabled={zoom <= MIN_PAGE_ZOOM}
                    aria-label="Thu nhỏ bản vẽ"
                  >
                    <MinusIcon className="h-4 w-4" />
                  </button>
                  <span
                    aria-live="polite"
                    className="flex min-h-11 min-w-16 items-center justify-center rounded-lg bg-white px-2 text-sm font-medium text-slate-700 tabular-nums"
                  >
                    {Math.round(zoom * 100)}%
                  </span>
                  <button
                    type="button"
                    className={cx(BUTTON_SECONDARY, "min-w-11 px-3")}
                    onClick={() => setZoom((current) => stepPageZoom(current, 1))}
                    disabled={zoom >= MAX_PAGE_ZOOM}
                    aria-label="Phóng to bản vẽ"
                  >
                    <PlusIcon className="h-4 w-4" />
                  </button>
                  <button
                    type="button"
                    className={cx(BUTTON_SECONDARY, "px-3")}
                    onClick={() => setZoom(MIN_PAGE_ZOOM)}
                    disabled={zoom === MIN_PAGE_ZOOM}
                  >
                    Về 100%
                  </button>
                </div>
                <div
                  role="region"
                  aria-label={`Trang ${pageNumber}, cuộn để xem toàn bộ bản vẽ`}
                  tabIndex={0}
                  className="max-h-[70vh] overflow-auto overscroll-contain rounded-lg border border-slate-200 bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[#405e9b]"
                >
                  <img
                    src={renderUrl}
                    alt={`Trang ${pageNumber} bản vẽ${page.drawing_number ? ` ${page.drawing_number}` : ""}`}
                    draggable={false}
                    className="block h-auto max-w-none select-none rounded object-contain"
                    style={{ width: `${clampPageZoom(zoom) * 100}%` }}
                  />
                </div>
              </>
            ) : (
              <p className={cx(SECTION_TEXT, "rounded-lg bg-slate-50 p-3")}>
                Chưa có ảnh trang cho bản vẽ này.
              </p>
            )}

            <PageExtractionPanel
              key={`${documentId}:${pageNumber}`}
              projectId={projectId}
              documentId={documentId}
              pageNumber={pageNumber}
            />
          </>
        )}
      </div>
    </section>
  );
}
