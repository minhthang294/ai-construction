import { useEffect, useState } from "react";
import { fetchResourceBlob, getDocumentPage } from "../lib/api";
import type { DocumentPage } from "../types";
import {
  clampPageZoom,
  MAX_PAGE_ZOOM,
  MIN_PAGE_ZOOM,
  stepPageZoom,
} from "../lib/pageViewport";
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
    <section className="rounded border border-gray-200 bg-white p-3 shadow-sm space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold">Trang {pageNumber}</h2>
          {page && (
            <p className="text-[11px] text-gray-600">
              Phương thức: {page.extraction_method}
              {page.ocr_confidence != null &&
                ` · OCR ${(page.ocr_confidence * 100).toFixed(1)}%`}
              {page.drawing_number && ` · Bản vẽ ${page.drawing_number}`}
              {page.revision && ` · Rev ${page.revision}`}
              {page.tables.length > 0 && ` · ${page.tables.length} bảng`}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            className="min-h-11 rounded border border-gray-300 px-3 py-2 text-sm disabled:opacity-40"
            onClick={() => onPageChange(pageNumber - 1)}
            disabled={pageNumber <= 1 || loading}
          >
            Trang trước
          </button>
          <span className="flex min-h-11 items-center text-xs text-gray-600">
            {pageNumber}/{Math.max(1, totalPages)}
          </span>
          <button
            type="button"
            className="min-h-11 rounded border border-gray-300 px-3 py-2 text-sm disabled:opacity-40"
            onClick={() => onPageChange(pageNumber + 1)}
            disabled={pageNumber >= totalPages || loading}
          >
            Trang sau
          </button>
          <button
            type="button"
            className="min-h-11 rounded border border-gray-300 px-3 py-2 text-sm"
            onClick={onClose}
          >
            {closeLabel}
          </button>
        </div>
      </div>

      {loading && <div className="text-xs text-gray-600">Đang tải trang...</div>}
      {error && <div className="rounded bg-red-50 p-2 text-xs text-red-800">{error}</div>}

      {page && (
        <>
          {page.needs_review && (
            <div className="rounded bg-amber-50 p-2 text-xs text-amber-900">
              Trang này cần kiểm tra trực tiếp bản vẽ gốc (OCR thiếu hoặc độ tin cậy thấp).
            </div>
          )}
          {page.warnings.length > 0 && (
            <ul className="list-disc rounded bg-amber-50 p-2 pl-5 text-xs text-amber-900">
              {page.warnings.map((warning, index) => (
                <li key={`${index}-${warning}`}>{warning}</li>
              ))}
            </ul>
          )}
          {renderUrl ? (
            <>
              <div className="flex flex-wrap items-center gap-2 rounded border border-gray-200 bg-gray-50 p-2 text-xs">
                <button
                  type="button"
                  className="min-h-11 min-w-11 rounded border border-gray-300 bg-white px-3 py-2 text-base disabled:opacity-40"
                  onClick={() => setZoom((current) => stepPageZoom(current, -1))}
                  disabled={zoom <= MIN_PAGE_ZOOM}
                  aria-label="Thu nhỏ bản vẽ"
                >
                  −
                </button>
                <span className="flex min-h-11 min-w-14 items-center justify-center text-sm">
                  {Math.round(zoom * 100)}%
                </span>
                <button
                  type="button"
                  className="min-h-11 min-w-11 rounded border border-gray-300 bg-white px-3 py-2 text-base disabled:opacity-40"
                  onClick={() => setZoom((current) => stepPageZoom(current, 1))}
                  disabled={zoom >= MAX_PAGE_ZOOM}
                  aria-label="Phóng to bản vẽ"
                >
                  +
                </button>
                <button
                  type="button"
                  className="min-h-11 rounded border border-gray-300 bg-white px-3 py-2 text-sm disabled:opacity-40"
                  onClick={() => setZoom(MIN_PAGE_ZOOM)}
                  disabled={zoom === MIN_PAGE_ZOOM}
                >
                  Về 100%
                </button>
                <button
                  type="button"
                  className="ml-auto min-h-11 rounded border border-gray-300 bg-white px-3 py-2 text-sm"
                  onClick={onClose}
                >
                  {closeLabel}
                </button>
              </div>
              <div className="max-h-[70vh] overflow-auto overscroll-contain rounded border border-gray-200 bg-gray-100">
                <img
                  src={renderUrl}
                  alt={`Trang ${pageNumber} bản vẽ`}
                  draggable={false}
                  className="block h-auto max-w-none select-none rounded object-contain"
                  style={{ width: `${clampPageZoom(zoom) * 100}%` }}
                />
              </div>
            </>
          ) : (
            <p className="text-xs text-gray-500">
              Không có ảnh render cho trang này; chỉ hiển thị text trích xuất.
            </p>
          )}
          <div>
            <h3 className="text-xs font-semibold text-gray-700">
              {page.extraction_method === "ocr" ? "Text OCR" : "Text trích xuất"}
            </h3>
            <pre className="mt-1 max-h-80 overflow-auto whitespace-pre-wrap rounded bg-gray-50 p-2 text-xs">
              {page.text || "(trang không có text trích xuất được)"}
            </pre>
          </div>
          <PageExtractionPanel
            key={`${documentId}:${pageNumber}`}
            projectId={projectId}
            documentId={documentId}
            pageNumber={pageNumber}
          />
        </>
      )}
    </section>
  );
}
