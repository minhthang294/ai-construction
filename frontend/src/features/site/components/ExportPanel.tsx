import { useCallback, useEffect, useState } from "react";
import {
  canShareText,
  copyText,
  createExport,
  downloadExport,
  listExports,
  shareText,
} from "../lib/api";
import { DailyReport, ExportFormat, ExportResult } from "../types";

type Props = {
  projectId: string;
  date: string;
  report: DailyReport | null;
  onMessage: (message: string) => void;
};

const FORMATS: { value: ExportFormat; label: string }[] = [
  { value: "zalo", label: "Nội dung Zalo" },
  { value: "pdf", label: "PDF" },
  { value: "docx", label: "DOCX" },
  { value: "zip", label: "ZIP (ảnh + file)" },
];

function formatTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("vi-VN", {
    timeZone: "Asia/Ho_Chi_Minh",
    dateStyle: "short",
    timeStyle: "short",
  }).format(date);
}

export default function ExportPanel({ projectId, date, report, onMessage }: Props) {
  const [history, setHistory] = useState<ExportResult[]>([]);
  const [preview, setPreview] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const loadHistory = useCallback(async () => {
    try {
      setHistory(await listExports(projectId, date));
    } catch {
      // History is secondary; the save/export actions still work.
      setHistory([]);
    }
  }, [projectId, date]);

  useEffect(() => {
    void loadHistory();
  }, [loadHistory, report?.updated_at]);

  const canExport = report?.status === "reviewed";

  async function handleExport(format: ExportFormat) {
    if (!report) {
      onMessage("Cần lưu báo cáo trước khi xuất.");
      return;
    }
    if (!canExport) {
      onMessage("Báo cáo phải ở trạng thái “Đã duyệt” trước khi xuất file.");
      return;
    }
    setBusy(format);
    try {
      const result = await createExport(projectId, date, format);
      if (format === "zalo") {
        setPreview(result.preview_text ?? "");
        onMessage("Đã tạo nội dung Zalo. Không tự động gửi.");
      } else {
        await downloadExport(result);
        onMessage(`Đã tạo và tải file ${format.toUpperCase()}.`);
      }
      await loadHistory();
    } catch (error) {
      onMessage(
        error instanceof Error ? error.message : "Xuất báo cáo thất bại.",
      );
    } finally {
      setBusy(null);
    }
  }

  async function handleCopy() {
    if (!preview) return;
    try {
      await copyText(preview);
      onMessage("Đã sao chép nội dung Zalo. Người dùng tự dán vào Zalo.");
    } catch {
      onMessage("Không sao chép được; hãy chọn và sao chép thủ công.");
    }
  }

  async function handleShare() {
    if (!preview) return;
    const outcome = await shareText(`Báo cáo ngày ${date}`, preview);
    if (outcome === "shared") {
      onMessage("Đã mở hộp thoại chia sẻ của thiết bị. Người dùng tự chọn nơi gửi.");
    } else if (outcome === "copied") {
      onMessage("Thiết bị không hỗ trợ chia sẻ; đã sao chép nội dung để tự dán.");
    } else if (outcome === "unavailable") {
      onMessage("Không chia sẻ/sao chép được; hãy tải file Zalo trong lịch sử xuất.");
    } else {
      onMessage("Đã huỷ chia sẻ. Không có nội dung nào được gửi.");
    }
  }

  async function handleDownload(result: ExportResult) {
    try {
      await downloadExport(result);
    } catch {
      onMessage("Không tải được file xuất.");
    }
  }

  return (
    <section className="space-y-3">
      <div>
        <h3 className="text-lg font-semibold">Xuất báo cáo</h3>
        {!canExport && (
          <p className="text-xs text-amber-700">
            Chuyển trạng thái sang “Đã duyệt” và lưu trước khi xuất.
          </p>
        )}
      </div>

      <div className="grid grid-cols-2 gap-2">
        {FORMATS.map((format) => (
          <button
            key={format.value}
            type="button"
            disabled={busy !== null || !canExport}
            className="min-h-11 rounded-lg bg-gray-800 px-3 text-sm font-medium text-white disabled:opacity-40"
            onClick={() => void handleExport(format.value)}
          >
            {busy === format.value ? "Đang tạo…" : format.label}
          </button>
        ))}
      </div>

      {preview !== null && (
        <div className="space-y-2 rounded-xl border border-gray-200 bg-white p-3">
          <div className="flex items-center justify-between gap-2">
            <h4 className="text-sm font-semibold">Nội dung Zalo</h4>
            <div className="flex gap-2">
              {canShareText() && (
                <button
                  type="button"
                  className="min-h-9 rounded-lg border border-blue-600 px-3 text-xs font-medium text-blue-700"
                  onClick={() => void handleShare()}
                >
                  Chia sẻ…
                </button>
              )}
              <button
                type="button"
                className="min-h-9 rounded-lg bg-blue-600 px-3 text-xs font-medium text-white"
                onClick={() => void handleCopy()}
              >
                Sao chép
              </button>
            </div>
          </div>
          <pre className="max-h-80 overflow-auto whitespace-pre-wrap rounded-lg bg-gray-50 p-2 text-xs">
            {preview || "Chưa có nội dung."}
          </pre>
          <p className="text-xs text-gray-500">
            Ứng dụng không tự động gửi Zalo. Người dùng tự bấm “Chia sẻ…” hoặc dán nội
            dung đã sao chép.
          </p>
        </div>
      )}

      <div className="space-y-2">
        <h4 className="text-sm font-semibold text-gray-700">Lịch sử xuất</h4>
        {history.length === 0 && (
          <p className="text-xs text-gray-500">Chưa có lần xuất nào.</p>
        )}
        {history.map((item) => (
          <div
            key={item.id}
            className="flex items-center justify-between gap-2 rounded-lg border border-gray-200 bg-white p-2 text-xs"
          >
            <div className="min-w-0">
              <p className="font-medium uppercase">{item.format}</p>
              <p className="truncate text-gray-500">{formatTime(item.generated_at)}</p>
            </div>
            <button
              type="button"
              className="min-h-9 shrink-0 rounded-lg border border-gray-300 px-3"
              onClick={() => void handleDownload(item)}
            >
              Tải
            </button>
          </div>
        ))}
      </div>
    </section>
  );
}
