import { useEffect, useState } from "react";
import { listWorkItems, workItemAcceptanceHistory } from "../lib/api";
import {
  recordStatusLabel,
  requestStatusLabel,
  resultLabel,
  revisionLabel,
} from "../lib/statusLabels";
import type {
  AcceptanceHistoryItem,
  WorkItemAcceptanceHistory,
  WorkItemSummary,
} from "../types";

type Props = {
  projectId: string;
  onOpenRequest?: (requestId: string) => void;
  onOpenRecord?: (recordId: string) => void;
};

function formatTime(value: string): string {
  try {
    return new Intl.DateTimeFormat("vi-VN", {
      dateStyle: "short",
      timeStyle: "short",
    }).format(new Date(value));
  } catch {
    return value;
  }
}

export default function AcceptanceHistoryPanel({
  projectId,
  onOpenRequest,
  onOpenRecord,
}: Props) {
  const [workItems, setWorkItems] = useState<WorkItemSummary[]>([]);
  const [workItemId, setWorkItemId] = useState("");
  const [history, setHistory] = useState<WorkItemAcceptanceHistory | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    listWorkItems(projectId)
      .then((rows) => {
        setWorkItems(rows);
        if (rows.length === 1) setWorkItemId(rows[0].id);
        else setWorkItemId("");
        setHistory(null);
      })
      .catch((cause) =>
        setError(cause instanceof Error ? cause.message : "Không tải được công việc."),
      );
  }, [projectId]);

  async function loadHistory(value: string) {
    setWorkItemId(value);
    setHistory(null);
    setError(null);
    if (!value) return;
    setBusy(true);
    try {
      setHistory(await workItemAcceptanceHistory(projectId, value));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không tải được lịch sử nghiệm thu.");
    } finally {
      setBusy(false);
    }
  }

  function openItem(item: AcceptanceHistoryItem) {
    if (item.kind === "pyc" && onOpenRequest) onOpenRequest(item.id);
    if (item.kind === "bbnt" && onOpenRecord) onOpenRecord(item.id);
  }

  return (
    <section className="rounded-xl bg-white p-4 shadow-sm" aria-label="Lịch sử nghiệm thu theo công việc">
      <h2 className="font-semibold">Lịch sử nghiệm thu theo công việc</h2>
      <p className="mb-2 text-sm text-slate-500">
        Chỉ đọc PYC/BBNT theo work item; không tự xác nhận hay thay đổi biên bản.
      </p>

      <label className="block text-sm">
        Công việc
        <select
          className="mt-1 w-full rounded border p-2"
          value={workItemId}
          onChange={(event) => void loadHistory(event.target.value)}
        >
          <option value="">Chọn công việc</option>
          {workItems.map((item) => (
            <option key={item.id} value={item.id}>
              {item.code} — {item.name}
            </option>
          ))}
        </select>
      </label>

      {busy && <p className="mt-2 text-sm text-slate-500">Đang tải...</p>}
      {error && (
        <p role="alert" className="mt-2 rounded bg-rose-50 p-2 text-sm text-rose-800">
          {error}
        </p>
      )}

      {history && (
        <ul className="mt-3 space-y-2">
          {history.items.length === 0 && (
            <li className="text-sm text-slate-500">Chưa có PYC/BBNT cho công việc này.</li>
          )}
          {history.items.map((item) => (
            <li key={`${item.kind}-${item.id}`} className="rounded border p-2 text-sm">
              <div className="flex flex-wrap items-center gap-2">
                <span
                  className={`rounded px-2 py-0.5 text-sm font-semibold ${
                    item.kind === "pyc"
                      ? "bg-sky-100 text-sky-900"
                      : "bg-emerald-100 text-emerald-900"
                  }`}
                >
                  {item.kind.toUpperCase()}
                </span>
                <span className="font-medium">Số {item.number}</span>
                <span className="text-slate-600">
                  {item.kind === "pyc"
                    ? requestStatusLabel(item.status)
                    : recordStatusLabel(item.status)}
                </span>
                <span className="text-slate-600">{revisionLabel(item.revision)}</span>
                {item.result && (
                  <span className="text-slate-600">{resultLabel(item.result)}</span>
                )}
              </div>
              <div className="mt-1 flex flex-wrap items-center justify-between gap-2 text-sm text-slate-600">
                <span>{formatTime(item.updated_at)}</span>
                <button
                  type="button"
                  onClick={() => openItem(item)}
                  className="min-h-11 rounded border border-teal-700 px-3 py-2 text-sm text-teal-800"
                >
                  Mở {item.kind.toUpperCase()}
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

