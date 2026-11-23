import type { Citation } from "../types";
import { cx, BUTTON_SECONDARY } from "../lib/ui";
import { citationDisplay } from "../lib/citations";
import { ArrowLeftIcon, AlertIcon } from "./icons";

type Props = {
  citation: Citation;
  onOpen?: (citation: Citation) => void;
  onOpenComponent?: (recordId: string, citation: Citation) => void;
};

export default function CitationCard({ citation, onOpen, onOpenComponent }: Props) {
  const display = citationDisplay(citation);
  const lowOcr = citation.ocr_confidence != null && citation.ocr_confidence < 0.6;
  const isComponentRow = display.table === "structural_components";
  return (
    <article className="min-w-0 space-y-1.5 rounded-lg border border-[#405e9b]/20 bg-[#405e9b]/5 p-2.5">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm leading-5">
        <span className="min-w-0 font-semibold text-[#2f487a] [overflow-wrap:anywhere]">
          {display.title}
        </span>
        {display.isDatabase ? (
          <>
            <span className="rounded-full border border-slate-300 bg-white px-2 py-0.5 text-sm font-medium text-slate-700">
              {display.table}
            </span>
            {display.recordId && (
              <span className="text-sm text-slate-600 [overflow-wrap:anywhere]">
                bản ghi {display.recordId}
              </span>
            )}
            {citation.drawing_number && (
              <span className="text-sm text-slate-600">
                bảng {citation.drawing_number}
              </span>
            )}
            {citation.page_number > 0 && (
              <span className="text-sm text-slate-600">trang {citation.page_number}</span>
            )}
            {citation.section && (
              <span className="text-sm text-slate-600">{citation.section}</span>
            )}
          </>
        ) : (
          <>
            {display.pageLabel && (
              <span className="rounded-full border border-[#405e9b]/20 bg-white px-2 py-0.5 text-sm font-medium text-slate-700">
                v{citation.version} · {display.pageLabel}
              </span>
            )}
            {citation.drawing_number && (
              <span className="text-sm text-slate-600">
                bản vẽ {citation.drawing_number}
                {citation.revision ? ` bản sửa ${citation.revision}` : ""}
              </span>
            )}
            {citation.section && (
              <span className="text-sm text-slate-600">mục {citation.section}</span>
            )}
          </>
        )}
      </div>
      <blockquote className="line-clamp-3 border-l-2 border-[#405e9b]/40 pl-2 text-sm leading-5 text-slate-800 [overflow-wrap:anywhere] whitespace-pre-wrap">
        {citation.quote}
      </blockquote>
      {lowOcr && (
        <p className="flex items-start gap-1.5 text-sm leading-5 text-amber-800">
          <AlertIcon className="mt-0.5 h-4 w-4 shrink-0" />
          Trang nguồn có độ tin cậy thấp; cần kiểm tra bản vẽ gốc.
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        {display.isDatabase && isComponentRow && display.recordId && onOpenComponent && (
          <button
            type="button"
            className={cx(BUTTON_SECONDARY, "min-h-11 px-3 py-1 text-sm")}
            onClick={() => onOpenComponent(display.recordId!, citation)}
          >
            Mở cấu kiện
          </button>
        )}
        {!display.isDatabase && onOpen && (
          <button
            type="button"
            className={cx(BUTTON_SECONDARY, "min-h-11 px-3 py-1 text-sm")}
            onClick={() => onOpen(citation)}
          >
            <ArrowLeftIcon className="h-4 w-4 rotate-180" />
            Xem trang
          </button>
        )}
      </div>
    </article>
  );
}
