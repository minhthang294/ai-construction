import { useCallback, useState, type FormEvent } from "react";
import {
  correctProgressEvent,
  listProgressEvents,
  undoProgressBatch,
} from "../lib/api";
import type { ProgressEventRecord } from "../lib/batches";

const SECONDARY =
  "min-h-11 rounded-lg border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-800 active:bg-slate-100 disabled:bg-slate-100 disabled:text-slate-400";
const PRIMARY =
  "min-h-11 rounded-lg bg-slate-800 px-4 text-sm font-semibold text-white active:bg-slate-900 disabled:bg-slate-300";
const FIELD =
  "mt-1 min-h-11 w-full min-w-0 rounded-lg border border-slate-300 bg-white px-3 text-base text-slate-900 sm:text-sm";

const STATUS_LABELS: Record<string, string> = {
  NOT_STARTED: "Chưa bắt đầu",
  IN_PROGRESS: "Đang thi công",
  COMPLETED: "Hoàn thành",
  BLOCKED: "Tạm dừng",
};

type Action =
  | { kind: "correct"; eventId: string; status: "IN_PROGRESS" | "COMPLETED" | "BLOCKED" }
  | { kind: "undo"; batchId: string }
  | null;

export default function ProgressHistoryPanel({
  projectId,
  componentId,
  onChanged,
}: {
  projectId: string;
  componentId: string;
  onChanged?: () => void;
}) {
  const [events, setEvents] = useState<ProgressEventRecord[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [action, setAction] = useState<Action>(null);
  const [reason, setReason] = useState("");

  const load = useCallback(async () => {
    setBusy(true);
    try {
      setEvents(await listProgressEvents(projectId, componentId));
      setError(null);
    } catch (cause) {
      setEvents([]);
      setError(cause instanceof Error ? cause.message : "Không tải được lịch sử.");
    } finally {
      setBusy(false);
    }
  }, [componentId, projectId]);

  function startCorrect(event: ProgressEventRecord) {
    setAction({
      kind: "correct",
      eventId: event.id,
      status: event.status === "COMPLETED" ? "IN_PROGRESS" : "COMPLETED",
    });
    setReason("");
    setMessage(null);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!action || busy || !reason.trim()) return;
    setBusy(true);
    setError(null);
    try {
      if (action.kind === "correct") {
        await correctProgressEvent(projectId, action.eventId, action.status, reason.trim());
        setMessage("Đã sửa trạng thái: sự kiện cũ được vô hiệu, sự kiện mới đã ghi.");
      } else {
        const result = await undoProgressBatch(projectId, action.batchId, reason.trim());
        setMessage(`Đã hoàn tác ${result.voided} sự kiện của đợt.`);
      }
      setAction(null);
      setReason("");
      await load();
      onChanged?.();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thực hiện được.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <details
      className="mt-2 rounded-lg border border-slate-200"
      onToggle={(event) => {
        if (event.currentTarget.open && events === null) void load();
      }}
    >
      <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between gap-2 px-2 text-sm font-medium text-slate-700 [&::-webkit-details-marker]:hidden">
        Lịch sử tiến độ
        <span className="text-xs font-normal text-slate-500">
          {busy ? "Đang tải…" : events ? `${events.length} sự kiện` : "Mở để xem"}
        </span>
      </summary>
      <div className="space-y-2 border-t border-slate-200 p-2">
        {error ? <p role="alert" className="text-sm text-red-700">{error}</p> : null}
        {message ? <p role="status" className="text-sm text-emerald-800">{message}</p> : null}
        {events && events.length === 0 ? (
          <p className="text-sm text-slate-600">Chưa có sự kiện tiến độ còn hiệu lực.</p>
        ) : null}
        {events?.map((event) => (
          <div key={event.id} className="rounded-lg border border-slate-200 p-2 text-xs">
            <div className="flex flex-wrap items-baseline justify-between gap-1">
              <span className="font-semibold text-slate-900">{STATUS_LABELS[event.status] ?? event.status}</span>
              <span className="tabular-nums text-slate-600">{event.event_date}</span>
            </div>
            {event.stage_name ? (
              <p className="mt-1 break-words text-slate-700">{event.stage_name}</p>
            ) : null}
            {event.note ? <p className="mt-1 break-words text-slate-700">{event.note}</p> : null}
            <div className="mt-2 flex flex-wrap gap-2">
              <button type="button" className={SECONDARY} onClick={() => startCorrect(event)}>
                Sửa
              </button>
              {event.batch_id ? (
                <button
                  type="button"
                  className={SECONDARY}
                  onClick={() => {
                    setAction({ kind: "undo", batchId: event.batch_id! });
                    setReason("");
                    setMessage(null);
                  }}
                >
                  Hoàn tác đợt
                </button>
              ) : null}
            </div>
          </div>
        ))}

        {action ? (
          <form onSubmit={submit} className="rounded-lg border border-amber-200 bg-amber-50 p-2">
            <p className="text-sm font-semibold text-amber-900">
              {action.kind === "correct" ? "Sửa trạng thái sự kiện" : "Hoàn tác cả đợt ghi"}
            </p>
            {action.kind === "correct" ? (
              <label className="mt-2 block text-xs font-medium text-slate-700">
                Trạng thái mới
                <select
                  className={FIELD}
                  value={action.status}
                  onChange={(event) =>
                    setAction({ ...action, status: event.target.value as typeof action.status })
                  }
                >
                  <option value="IN_PROGRESS">Đang thi công</option>
                  <option value="COMPLETED">Hoàn thành</option>
                  <option value="BLOCKED">Tạm dừng</option>
                </select>
              </label>
            ) : null}
            <label className="mt-2 block text-xs font-medium text-slate-700">
              Lý do (bắt buộc)
              <input
                className={FIELD}
                value={reason}
                maxLength={1000}
                required
                onChange={(event) => setReason(event.target.value)}
              />
            </label>
            <div className="mt-2 flex flex-wrap gap-2">
              <button type="submit" className={PRIMARY} disabled={busy || !reason.trim()}>
                {busy ? "Đang lưu…" : "Xác nhận"}
              </button>
              <button
                type="button"
                className={SECONDARY}
                disabled={busy}
                onClick={() => {
                  setAction(null);
                  setReason("");
                }}
              >
                Hủy
              </button>
            </div>
          </form>
        ) : null}
      </div>
    </details>
  );
}
