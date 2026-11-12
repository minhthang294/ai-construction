import type { Citation } from "../types";

type Props = {
  citation: Citation;
  onOpen?: (citation: Citation) => void;
};

export default function CitationCard({ citation, onOpen }: Props) {
  const lowOcr = citation.ocr_confidence != null && citation.ocr_confidence < 0.6;
  return (
    <article className="rounded border border-blue-100 bg-blue-50/60 p-2 text-xs space-y-1">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <span className="font-semibold text-blue-900">{citation.document_name}</span>
        <span className="rounded bg-white px-1.5 py-0.5">v{citation.version}</span>
        <span>trang {citation.page_number}</span>
        {citation.drawing_number && <span>bản vẽ {citation.drawing_number}</span>}
        {citation.revision && <span>rev {citation.revision}</span>}
        {citation.section && <span>mục {citation.section}</span>}
        {citation.ocr_confidence != null && (
          <span className={lowOcr ? "font-medium text-red-700" : "text-gray-600"}>
            OCR {(citation.ocr_confidence * 100).toFixed(1)}%
          </span>
        )}
      </div>
      <blockquote className="whitespace-pre-wrap border-l-2 border-blue-300 pl-2 text-gray-800">
        {citation.quote}
      </blockquote>
      {lowOcr && (
        <p className="font-medium text-red-700">
          Thông tin chưa đủ độ tin cậy, cần kiểm tra trực tiếp bản vẽ gốc.
        </p>
      )}
      {onOpen && (
        <button
          type="button"
          className="min-h-11 rounded border border-blue-300 bg-white px-3 py-2 text-xs text-blue-800"
          onClick={() => onOpen(citation)}
        >
          Xem trang nguồn
        </button>
      )}
    </article>
  );
}
