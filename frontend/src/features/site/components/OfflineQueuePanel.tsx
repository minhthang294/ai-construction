import { useState } from "react";
import type { PhotoQueuePayload, QueueItem, ReportQueuePayload } from "../lib/offlineDb";
import { describeQueueItem, isQueueItemFailed } from "../lib/queueRetry";

type Props = {
  projectId: string;
  items: QueueItem[];
  /** Disable while a sync pass is running to avoid racing the worker. */
  disabled?: boolean;
  onDiscard: (id: string) => Promise<boolean>;
  onMessage?: (message: string) => void;
};

function itemLabel(item: QueueItem): string {
  if (item.kind === "report") {
    const payload = item.payload as ReportQueuePayload;
    return `Báo cáo ngày ${payload.date}`;
  }
  const payload = item.payload as PhotoQueuePayload;
  return `Ảnh ${payload.filename}`;
}

function discardConfirmation(item: QueueItem): string {
  const label = itemLabel(item);
  if (item.kind === "photo") {
    return (
      `Bỏ "${label}" khỏi hàng đợi?\n\n` +
      "Chỉ mục chờ này trên thiết bị bị xoá. Ảnh đã tải lên máy chủ không bị xoá; " +
      "bản sao ảnh đang chờ trong hàng đợi sẽ mất."
    );
  }
  return (
    `Bỏ "${label}" khỏi hàng đợi?\n\n` +
    "Chỉ mục chờ này bị xoá. Bản nháp trên thiết bị và báo cáo đã lưu trên máy chủ " +
    "không bị xoá."
  );
}

/**
 * Mobile offline queue list.  Each entry shows its attempt count/backoff state
 * and can be discarded individually after an explicit confirmation.
 */
export default function OfflineQueuePanel({
  projectId,
  items,
  disabled = false,
  onDiscard,
  onMessage,
}: Props) {
  const [busyId, setBusyId] = useState<string | null>(null);

  if (items.length === 0) return null;

  async function handleDiscard(item: QueueItem) {
    if (item.projectId !== projectId) {
      onMessage?.("Mục này thuộc công trình khác, không thể bỏ ở đây.");
      return;
    }
    if (!window.confirm(discardConfirmation(item))) return;
    setBusyId(item.id);
    try {
      const removed = await onDiscard(item.id);
      onMessage?.(
        removed
          ? "Đã bỏ mục khỏi hàng đợi. Bản nháp/ảnh gốc không bị xoá."
          : "Không bỏ được mục khỏi hàng đợi.",
      );
    } finally {
      setBusyId(null);
    }
  }

  const failedCount = items.filter((item) => isQueueItemFailed(item)).length;
  const now = Date.now();

  return (
    <section className="space-y-2 rounded-xl border border-gray-200 bg-white p-3 shadow-sm">
      <div className="flex items-start justify-between gap-2">
        <h3 className="text-base font-semibold">Hàng đợi đồng bộ</h3>
        <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-700">
          {items.length} mục{failedCount > 0 ? ` · ${failedCount} lỗi` : ""}
        </span>
      </div>
      <p className="text-xs text-gray-500">
        Mục lỗi tạm thời sẽ tự thử lại theo thời gian chờ tăng dần. Sau 8 lần vẫn
        lỗi, mục chuyển “thất bại” và chỉ được bỏ khi bạn xác nhận.
      </p>
      <ul className="divide-y divide-gray-100">
        {items.map((item) => {
          const failed = isQueueItemFailed(item);
          return (
            <li key={item.id} className="flex items-start gap-2 py-2">
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-gray-800">
                  {itemLabel(item)}
                </p>
                <p
                  className={`text-xs ${failed ? "text-red-700" : "text-gray-500"}`}
                >
                  {describeQueueItem(item, now)}
                </p>
                {item.lastError && (
                  <p className="mt-0.5 break-words text-xs text-gray-400">
                    {item.lastError}
                  </p>
                )}
              </div>
              <button
                type="button"
                className="min-h-9 shrink-0 rounded-lg border border-red-300 bg-red-50 px-3 text-xs font-medium text-red-700 disabled:opacity-50"
                disabled={disabled || busyId === item.id}
                onClick={() => void handleDiscard(item)}
              >
                {busyId === item.id ? "Đang bỏ…" : "Bỏ mục"}
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
