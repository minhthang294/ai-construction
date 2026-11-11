import { useEffect, useState } from "react";
import { fetchResourceBlob, getDocumentPage } from "../lib/api";
import type { DocumentPage } from "../types";

type Props = {
  projectId: string;
  documentId: string;
  pageNumber: number;
  totalPages: number;
  onClose: () => void;
  onPageChange: (pageNumber: number) => void;
};

export default function PageViewer({
  projectId,
  documentId,
  pageNumber,
  totalPages,
  onClose,
  onPageChange,
}: Props) {
  const [page, setPage] = useState<DocumentPage | null>(null);
  const [renderUrl, setRenderUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let objectUrl: string | null = null;

    (async () => {
      setLoading(true);
      setError(null);
      setPage(null);
      setRenderUrl(null);
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
            className="rounded border border-gray-300 px-2 py-1 text-xs disabled:opacity-40"
            onClick={() => onPageChange(pageNumber - 1)}
            disabled={pageNumber <= 1 || loading}
          >
            Trang trước
          </button>
          <span className="text-xs text-gray-600">
            {pageNumber}/{Math.max(1, totalPages)}
          </span>
          <button
            type="button"
            className="rounded border border-gray-300 px-2 py-1 text-xs disabled:opacity-40"
            onClick={() => onPageChange(pageNumber + 1)}
            disabled={pageNumber >= totalPages || loading}
          >
            Trang sau
          </button>
          <button
            type="button"
            className="rounded border border-gray-300 px-2 py-1 text-xs"
            onClick={onClose}
          >
            Đóng
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
            <img
              src={renderUrl}
              alt={`Trang ${pageNumber} bản vẽ`}
              className="max-h-[70vh] w-full rounded border border-gray-200 object-contain"
            />
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
        </>
      )}
    </section>
  );
}
