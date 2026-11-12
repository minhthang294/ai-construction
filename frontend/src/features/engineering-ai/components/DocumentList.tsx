import type { SourceDocument } from "../types";

type Props = {
  documents: SourceDocument[];
  selectedId?: string | null;
  onSelect: (document: SourceDocument) => void;
  onRefresh: () => void;
  onOpenOriginal: (document: SourceDocument) => void;
  onReingest?: (document: SourceDocument) => void;
  onConfirmEffective?: (document: SourceDocument) => void;
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
  pending: "bg-amber-100 text-amber-800",
  running: "bg-blue-100 text-blue-800",
  ocr_completed: "bg-cyan-100 text-cyan-800",
  indexing: "bg-indigo-100 text-indigo-800",
  ready: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
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
  onReingest,
  onConfirmEffective,
  loading,
}: Props) {
  return (
    <section className="rounded border border-gray-200 bg-white p-3 shadow-sm space-y-2">
      <div className="flex items-center justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold">Hồ sơ nguồn</h2>
          <p className="text-xs text-gray-600">
            Chỉ hồ sơ <span className="font-medium">ready</span> và phiên bản có hiệu lực
            được dùng để trả lời.
          </p>
        </div>
        <button
          type="button"
          className="rounded border border-gray-300 px-3 py-1 text-xs font-medium"
          onClick={onRefresh}
          disabled={loading}
        >
          {loading ? "Đang tải..." : "Làm mới"}
        </button>
      </div>

      {documents.length === 0 ? (
        <div className="rounded bg-gray-50 p-3 text-xs text-gray-600">
          Chưa có hồ sơ PDF trong công trình này. Khi chưa có nguồn, AI trả lời bằng
          câu từ chối chuẩn thay vì suy đoán.
        </div>
      ) : (
        <ul className="divide-y divide-gray-100">
          {documents.map((document) => (
            <li key={document.id}>
              <button
                type="button"
                onClick={() => onSelect(document)}
                className={`w-full p-2 text-left transition ${
                  selectedId === document.id ? "bg-blue-50" : "hover:bg-gray-50"
                }`}
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-medium break-all">{document.original_name}</span>
                  <span className="rounded bg-gray-100 px-2 py-0.5 text-[11px] text-gray-700">
                    v{document.version}
                  </span>
                  {!document.is_current && (
                    <span className="rounded bg-gray-200 px-2 py-0.5 text-[11px]">
                      Bản cũ
                    </span>
                  )}
                  <span
                    className={`rounded px-2 py-0.5 text-[11px] ${
                      document.is_effective
                        ? "bg-emerald-100 text-emerald-800"
                        : "bg-gray-100 text-gray-600"
                    }`}
                  >
                    {document.is_effective ? "Có hiệu lực" : "Chưa hiệu lực"}
                  </span>
                  <span
                    className={`rounded px-2 py-0.5 text-[11px] ${
                      STATUS_STYLES[document.status] ?? "bg-gray-100 text-gray-700"
                    }`}
                  >
                    {STATUS_LABELS[document.status] ?? document.status}
                  </span>
                </div>
                <div className="mt-1 grid gap-x-3 text-[11px] text-gray-600 sm:grid-cols-3">
                  <span>Loại: {document.type}</span>
                  <span>{document.page_count} trang</span>
                  <span title={document.sha256}>SHA-256: {shortHash(document.sha256)}</span>
                  {document.drawing_number && <span>Bản vẽ: {document.drawing_number}</span>}
                  {document.revision && <span>Revision: {document.revision}</span>}
                  <span>{(document.size_bytes / 1024 / 1024).toFixed(2)} MB</span>
                  {document.effective_at && (
                    <span>Hiệu lực: {new Date(document.effective_at).toLocaleString("vi-VN")}</span>
                  )}
                </div>
                {document.change_note && (
                  <p className="mt-1 text-[11px] text-gray-600">
                    Ghi chú hiệu lực: {document.change_note}
                  </p>
                )}
                {document.error_message && (
                  <p className="mt-1 text-[11px] text-red-700">{document.error_message}</p>
                )}
                {document.warnings.length > 0 && (
                  <p className="mt-1 text-[11px] text-amber-700">
                    {document.warnings.length} cảnh báo trích xuất/OCR
                  </p>
                )}
              </button>
              <div className="flex justify-end gap-2 pb-2">
                {!document.is_effective && onConfirmEffective && (
                  <button
                    type="button"
                    className="min-h-11 rounded border border-emerald-400 bg-emerald-50 px-3 py-2 text-xs text-emerald-900"
                    onClick={() => onConfirmEffective(document)}
                  >
                    Xác nhận hiệu lực
                  </button>
                )}
                {document.status === "failed" && onReingest && (
                  <button
                    type="button"
                    className="min-h-11 rounded border border-amber-400 bg-amber-50 px-3 py-2 text-xs text-amber-900"
                    onClick={() => onReingest(document)}
                  >
                    Xử lý lại
                  </button>
                )}
                <button
                  type="button"
                  className="min-h-11 rounded border border-gray-300 px-3 py-2 text-xs"
                  onClick={() => onOpenOriginal(document)}
                >
                  Mở PDF gốc
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
