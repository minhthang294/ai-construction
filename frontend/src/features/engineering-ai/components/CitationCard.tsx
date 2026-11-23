import type { Citation } from "../types";
import { cx, BUTTON_SECONDARY } from "../lib/ui";
import { ArrowLeftIcon, AlertIcon } from "./icons";

type Props = {
  citation: Citation;
  onOpen?: (citation: Citation) => void;
};

export default function CitationCard({ citation, onOpen }: Props) {
  const lowOcr = citation.ocr_confidence != null && citation.ocr_confidence < 0.6;
  const isDatabase = citation.source === "database";
  return (
    <article className="min-w-0 space-y-2 rounded-lg border border-[#405e9b]/20 bg-[#405e9b]/5 p-3">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs leading-5">
        <span className="min-w-0 font-semibold text-[#2f487a] [overflow-wrap:anywhere]">
          {citation.document_name}
        </span>
        {isDatabase ? (
          <span className="rounded-full border border-slate-300 bg-white px-2 py-0.5 font-medium text-slate-700">
            bản ghi {citation.record_id ?? citation.document_id}
          </span>
        ) : (
          <>
            <span className="rounded-full border border-[#405e9b]/20 bg-white px-2 py-0.5 font-medium text-slate-700">
              v{citation.version}
            </span>
            <span className="text-slate-700">trang {citation.page_number}</span>
            {citation.drawing_number && (
              <span className="text-slate-700">bản vẽ {citation.drawing_number}</span>
            )}
            {citation.revision && <span className="text-slate-700">rev {citation.revision}</span>}
            {citation.section && <span className="text-slate-700">mục {citation.section}</span>}
          </>
        )}
        {citation.ocr_confidence != null && (
          <span className={cx(lowOcr ? "font-semibold text-red-700" : "text-slate-600")}>
            OCR {(citation.ocr_confidence * 100).toFixed(1)}%
          </span>
        )}
      </div>
      <blockquote className="border-l-2 border-[#405e9b]/40 pl-3 text-sm leading-6 text-slate-800 [overflow-wrap:anywhere] whitespace-pre-wrap">
        {citation.quote}
      </blockquote>
      {lowOcr && (
        <p className="flex items-start gap-2 rounded-md bg-red-50 p-2 text-xs leading-5 text-red-800">
          <AlertIcon className="mt-0.5 h-4 w-4 shrink-0" />
          Thông tin chưa đủ độ tin cậy, cần kiểm tra trực tiếp bản vẽ gốc.
        </p>
      )}
      {onOpen && !isDatabase && (
        <button
          type="button"
          className={cx(BUTTON_SECONDARY, "w-full sm:w-auto")}
          onClick={() => onOpen(citation)}
        >
          <ArrowLeftIcon className="h-4 w-4 rotate-180" />
          Xem trang nguồn
        </button>
      )}
    </article>
  );
}
