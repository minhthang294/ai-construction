import type { AcceptanceExport, PreviewPayload } from "../types";

type Props = {
  error: string | null;
  showError: boolean;
  lastExport: AcceptanceExport | null;
  downloadFailed: boolean;
  busy: boolean;
  onDownloadExport: (exported: AcceptanceExport) => void;
  preview: PreviewPayload | null;
  previewImageUrl: string | null;
  previewBusy: boolean;
  onClosePreview: () => void;
};

export default function AcceptanceNotices({
  error,
  showError,
  lastExport,
  downloadFailed,
  busy,
  onDownloadExport,
  preview,
  previewImageUrl,
  previewBusy,
  onClosePreview,
}: Props) {
  return (
    <>
      {showError && error && (
        <div role="alert" className="rounded bg-rose-50 p-3 text-sm text-rose-900">
          {error}
        </div>
      )}
      {lastExport && (
        <div className="rounded bg-white p-3 text-sm shadow-sm">
          File đã tạo:{" "}
          <button
            type="button"
            className="inline-flex min-h-11 items-center text-teal-700 underline disabled:opacity-50"
            disabled={busy}
            onClick={() => onDownloadExport(lastExport)}
          >
            {downloadFailed ? "Tải lại" : "Tải xuống lại"}{" "}
            {lastExport.kind.toUpperCase()} (.{lastExport.format})
          </button>{" "}
          <span className="text-slate-500">sha256 {lastExport.sha256.slice(0, 12)}…</span>
        </div>
      )}

      {preview && (
        <section className="rounded-xl bg-white p-3 shadow-sm">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold">Xem trước {preview.kind.toUpperCase()}</h2>
            <button
              type="button"
              className="inline-flex min-h-11 items-center text-sm underline"
              onClick={onClosePreview}
            >
              Đóng
            </button>
          </div>
          {preview.warnings.map((warning) => (
            <p key={warning} className="mt-2 rounded bg-amber-50 p-2 text-sm text-amber-900">
              {warning}
            </p>
          ))}
          {preview.kind === "pyc" ? (
            previewImageUrl ? (
              <div className="mt-2 space-y-2">
                <img
                  src={previewImageUrl}
                  alt="Ảnh xem trước phiếu yêu cầu nghiệm thu"
                  className="w-full rounded border border-slate-200 bg-white shadow-sm"
                />
                <p className="text-sm text-slate-500">
                  Ảnh được tạo từ mẫu Excel đã điền dữ liệu; bản chính thức chỉ
                  được tạo khi bấm xuất file.
                </p>
              </div>
            ) : (
              <p className="mt-2 rounded bg-slate-50 p-3 text-sm text-slate-600">
                {previewBusy
                  ? "Đang tạo ảnh xem trước PYC…"
                  : "Chưa tạo được ảnh xem trước. Xem thông báo lỗi phía trên."}
              </p>
            )
          ) : (
            <pre className="mt-2 max-h-64 overflow-auto rounded bg-slate-50 p-2 text-sm">
              {JSON.stringify(preview.cells, null, 2)}
            </pre>
          )}
        </section>
      )}
    </>
  );
}
