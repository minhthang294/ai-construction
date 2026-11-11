import { useEffect, useState } from "react";
import {
  loadAcceptanceHistory,
  type AcceptanceHistoryResult,
} from "../lib/acceptanceHistory";
import type {
  AcceptanceRecordSummary,
  AcceptanceRequestSummary,
} from "../types";

type WorkItemOption = { id: string; code: string; name: string };

type Props = {
  projectId: string;
  workItems: WorkItemOption[];
  /** Optional app-shell navigation; site never mutates acceptance data. */
  onOpenAcceptance?: () => void;
};

function requestStatusLabel(status: string): string {
  if (status === "draft") return "Nháp";
  if (status === "submitted") return "Đã gửi";
  return status;
}

function recordStatusLabel(status: string): string {
  if (status === "draft") return "Nháp";
  if (status === "confirmed") return "Đã xác nhận";
  return status;
}

function resultLabel(result?: string | null): string {
  if (result === "approved") return "Đạt";
  if (result === "conditional") return "Đạt có điều kiện";
  if (result === "rejected") return "Không đạt";
  return "Chưa có kết luận";
}

function Warnings({ values }: { values?: string[] }) {
  if (!values || values.length === 0) return null;
  return (
    <ul className="mt-1 list-disc space-y-0.5 pl-4 text-xs text-amber-800">
      {values.map((value, index) => (
        <li key={`${value}-${index}`}>{value}</li>
      ))}
    </ul>
  );
}

function RecordRow({ record }: { record: AcceptanceRecordSummary }) {
  return (
    <div className="rounded-lg border border-gray-200 bg-gray-50 p-2 text-xs">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium text-gray-800">
          BBNT {record.number ?? record.id}
        </span>
        <span className="rounded bg-white px-2 py-0.5">{recordStatusLabel(record.status)}</span>
        {record.revision != null && (
          <span className="text-gray-500">Rev. {record.revision}</span>
        )}
        {record.stale && (
          <span className="rounded bg-amber-100 px-2 py-0.5 text-amber-800">
            Cần cập nhật
          </span>
        )}
        <span className="text-gray-500">{resultLabel(record.result)}</span>
      </div>
      <Warnings values={record.warnings} />
    </div>
  );
}

function RequestRow({ request }: { request: AcceptanceRequestSummary }) {
  return (
    <div className="space-y-2 rounded-lg border border-gray-200 bg-white p-2">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="font-medium">PYC {request.number}</span>
        <span className="rounded bg-blue-50 px-2 py-0.5 text-xs text-blue-800">
          {requestStatusLabel(request.status)}
        </span>
        {request.revision != null && (
          <span className="text-xs text-gray-500">Rev. {request.revision}</span>
        )}
        {request.stale && (
          <span className="rounded bg-amber-100 px-2 py-0.5 text-xs text-amber-800">
            PYC đã thay đổi
          </span>
        )}
      </div>
      <Warnings values={request.warnings} />
      {request.records.length > 0 ? (
        <div className="space-y-1">
          {request.records.map((record) => (
            <RecordRow key={record.id} record={record} />
          ))}
        </div>
      ) : (
        <p className="text-xs text-gray-500">Chưa có BBNT cho PYC này.</p>
      )}
    </div>
  );
}

const EMPTY_RESULT: AcceptanceHistoryResult = {
  items: [],
  source: "history",
  warning: null,
};

export default function AcceptanceHistoryPanel({
  projectId,
  workItems,
  onOpenAcceptance,
}: Props) {
  const [result, setResult] = useState<AcceptanceHistoryResult>(EMPTY_RESULT);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const workItemKey = workItems.map((item) => item.id).join(",");

  useEffect(() => {
    let cancelled = false;
    if (workItems.length === 0) {
      setResult(EMPTY_RESULT);
      setError(null);
      return;
    }
    setLoading(true);
    setError(null);
    loadAcceptanceHistory(
      projectId,
      workItems.map((item) => item.id),
    )
      .then((data) => {
        if (!cancelled) setResult(data);
      })
      .catch((reason) => {
        if (!cancelled) {
          setResult(EMPTY_RESULT);
          setError(
            reason instanceof Error
              ? reason.message
              : "Không tải được lịch sử nghiệm thu.",
          );
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // `workItemKey` is the stable identity of the selected work items.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, workItemKey]);

  const byWorkItem = new Map(
    result.items.map((item) => [item.work_item_id, item.requests]),
  );

  return (
    <section className="space-y-3 rounded-xl bg-white p-3 shadow-sm">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h3 className="text-lg font-semibold">Lịch sử nghiệm thu theo công việc</h3>
          <p className="text-xs text-gray-500">
            Chỉ đọc PYC/BBNT. Việc tạo, sửa, xác nhận hoặc xuất thực hiện ở trang
            Nghiệm thu.
          </p>
        </div>
        {onOpenAcceptance && (
          <button
            type="button"
            className="min-h-9 shrink-0 rounded-lg border border-blue-300 bg-blue-50 px-3 text-xs font-medium text-blue-800"
            onClick={onOpenAcceptance}
          >
            Mở Nghiệm thu
          </button>
        )}
      </div>

      {loading && <p className="text-sm text-gray-500">Đang tải lịch sử…</p>}
      {error && <p className="text-sm text-red-700">{error}</p>}
      {result.warning && <p className="text-xs text-amber-800">{result.warning}</p>}
      {result.source === "fallback" && !loading && (
        <p className="text-xs text-gray-500">
          Đang dùng danh sách PYC/BBNT dự phòng; lịch sử theo work item sẽ đầy đủ hơn
          khi endpoint chuyên dụng sẵn sàng.
        </p>
      )}

      {workItems.length === 0 && (
        <p className="text-sm text-gray-500">
          Chưa có work item trong work log/kế hoạch ngày này.
        </p>
      )}

      {workItems.map((item) => {
        const requests = byWorkItem.get(item.id) ?? [];
        return (
          <div key={item.id} className="space-y-2 rounded-xl border border-gray-200 p-2">
            <p className="text-sm font-semibold text-gray-800">
              {item.code} — {item.name}
            </p>
            {requests.length === 0 ? (
              <p className="text-xs text-gray-500">Chưa có PYC/BBNT.</p>
            ) : (
              <div className="space-y-2">
                {requests.map((request) => (
                  <RequestRow key={request.id} request={request} />
                ))}
              </div>
            )}
          </div>
        );
      })}
    </section>
  );
}
