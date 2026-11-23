import type { SourceDocument } from "../types";
import {
  BADGE,
  BUTTON_SECONDARY,
  CARD,
  CARD_PAD,
  cx,
  HELP_TEXT,
  META_TEXT,
  SECTION_TEXT,
  SECTION_TITLE,
} from "../lib/ui";
import { AlertIcon, DocumentIcon, ExternalIcon, RefreshIcon } from "./icons";

type Props = {
  documents: SourceDocument[];
  selectedId?: string | null;
  onSelect: (document: SourceDocument) => void;
  onRefresh: () => void;
  onOpenOriginal: (document: SourceDocument) => void;
  loading?: boolean;
};

const STATUS_LABELS: Record<string, string> = {
  pending: "Chờ xử lý",
  running: "Đang trích xuất",
  ocr_completed: "Đã OCR",
  indexing: "Đang index",
  ready: "Sẵn sàng",
  failed: "Lỗi",
};

const STATUS_STYLES: Record<string, string> = {
  pending: "border-amber-200 bg-amber-100 text-amber-900",
  running: "border-[#405e9b]/20 bg-[#405e9b]/10 text-[#35507f]",
  ocr_completed: "border-sky-200 bg-sky-100 text-sky-900",
  indexing: "border-indigo-200 bg-indigo-100 text-indigo-900",
  ready: "border-emerald-200 bg-emerald-100 text-emerald-900",
  failed: "border-red-200 bg-red-100 text-red-800",
};

const DOCUMENT_TYPE_LABELS: Record<string, string> = {
  drawing: "Bản vẽ",
  specification: "Thuyết minh",
  technical_guideline: "Chỉ dẫn kỹ thuật",
  construction_method: "Biện pháp thi công",
  standard: "Tiêu chuẩn",
  material_record: "Hồ sơ vật liệu",
  test_record: "Hồ sơ thí nghiệm",
  acceptance_record: "Hồ sơ nghiệm thu",
  instruction: "Chỉ dẫn khác",
  report: "Báo cáo",
  other: "Khác",
};

function shortHash(value: string): string {
  return value ? `${value.slice(0, 10)}…` : "";
}

export default function DocumentList({
  documents,
  selectedId,
  onSelect,
  onRefresh,
  onOpenOriginal,
  loading,
}: Props) {
  return (
    <section className={cx(CARD, "min-w-0 overflow-hidden")} aria-busy={loading}>
      <div className={cx(CARD_PAD, "flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between")}>
        <div className="min-w-0">
          <h2 className={SECTION_TITLE}>Hồ sơ nguồn</h2>
          <p className={cx(SECTION_TEXT, "mt-1")}>
            Chỉ hồ sơ <span className="font-medium text-slate-800">ready</span> và phiên
            bản có hiệu lực được dùng để trả lời.
          </p>
        </div>
        <button
          type="button"
          className={cx(BUTTON_SECONDARY, "w-full shrink-0 sm:w-auto")}
          onClick={onRefresh}
          disabled={loading}
          aria-busy={loading}
        >
          <RefreshIcon className={cx("h-4 w-4", loading && "animate-spin motion-reduce:animate-none")} />
          {loading ? "Đang tải..." : "Làm mới"}
        </button>
      </div>

      {documents.length === 0 ? (
        <div className="border-t border-slate-200 p-4">
          <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 p-4 text-center">
            <DocumentIcon className="mx-auto h-9 w-9 text-slate-300" />
            <p className={cx(META_TEXT, "mx-auto mt-2 max-w-sm")}>
              Chưa có hồ sơ PDF trong công trình này. Khi chưa có nguồn, AI trả lời bằng
              câu từ chối chuẩn thay vì suy đoán.
            </p>
          </div>
        </div>
      ) : (
        <ul className="divide-y divide-slate-200 border-t border-slate-200">
          {documents.map((document) => {
            const selected = selectedId === document.id;
            return (
              <li
                key={document.id}
                className={cx(
                  "transition-colors",
                  selected ? "bg-[#405e9b]/5" : "hover:bg-slate-50",
                )}
              >
                <button
                  type="button"
                  onClick={() => onSelect(document)}
                  aria-pressed={selected}
                  className="w-full p-3 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[#405e9b]"
                >
                  <span className="block text-sm font-semibold text-slate-900 [overflow-wrap:anywhere]">
                    {document.original_name}
                  </span>
                  <span className="mt-1.5 flex flex-wrap items-center gap-1.5">
                    <span className={cx(BADGE, "border border-slate-200 bg-slate-100 text-slate-700")}>
                      v{document.version}
                    </span>
                    {!document.is_current && (
                      <span className={cx(BADGE, "border border-slate-200 bg-slate-200 text-slate-700")}>
                        Bản cũ
                      </span>
                    )}
                    <span
                      className={cx(
                        BADGE,
                        document.is_effective
                          ? "border border-emerald-200 bg-emerald-100 text-emerald-900"
                          : "border border-slate-200 bg-slate-100 text-slate-600",
                      )}
                    >
                      {document.is_effective ? "Có hiệu lực" : "Chưa hiệu lực"}
                    </span>
                    <span
                      className={cx(
                        BADGE,
                        STATUS_STYLES[document.status] ??
                          "border border-slate-200 bg-slate-100 text-slate-700",
                      )}
                    >
                      <span className="h-1.5 w-1.5 rounded-full bg-current" aria-hidden="true" />
                      {STATUS_LABELS[document.status] ?? document.status}
                    </span>
                  </span>

                  <span className="mt-2 grid gap-x-4 gap-y-1 text-xs leading-5 text-slate-600 sm:grid-cols-2">
                    <span>
                      <span className="text-slate-500">Loại: </span>
                      {DOCUMENT_TYPE_LABELS[document.type] ?? document.type}
                    </span>
                    <span>{document.page_count} trang</span>
                    <span className="font-mono tabular-nums" title={document.sha256}>
                      <span className="font-sans text-slate-500">SHA-256: </span>
                      {shortHash(document.sha256)}
                    </span>
                    {document.drawing_number && <span>Bản vẽ: {document.drawing_number}</span>}
                    {document.revision && <span>Revision: {document.revision}</span>}
                    <span>{(document.size_bytes / 1024 / 1024).toFixed(2)} MB</span>
                    {document.effective_at && (
                      <span>
                        Hiệu lực: {new Date(document.effective_at).toLocaleString("vi-VN")}
                      </span>
                    )}
                  </span>

                  {document.change_note && (
                    <span className={cx(HELP_TEXT, "block")}>
                      Ghi chú hiệu lực: {document.change_note}
                    </span>
                  )}
                  {document.error_message && (
                    <span className="mt-1 flex items-start gap-1.5 text-xs leading-5 text-red-700">
                      <AlertIcon className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                      <span className="[overflow-wrap:anywhere]">{document.error_message}</span>
                    </span>
                  )}
                  {document.warnings.length > 0 && (
                    <span className="mt-1 flex items-start gap-1.5 text-xs leading-5 text-amber-800">
                      <AlertIcon className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                      {document.warnings.length} cảnh báo hồ sơ nguồn
                    </span>
                  )}
                </button>

                <div className="flex flex-col-reverse gap-2 border-t border-slate-100 px-3 py-2.5 sm:flex-row sm:flex-wrap sm:justify-end">
                  <button
                    type="button"
                    className={cx(BUTTON_SECONDARY, "w-full sm:w-auto")}
                    onClick={() => onOpenOriginal(document)}
                    disabled={!document.original_url}
                  >
                    <ExternalIcon className="h-4 w-4" />
                    Mở PDF gốc
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
