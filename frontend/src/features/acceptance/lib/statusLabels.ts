import type { RecordStatus, RequestStatus, ResultState } from "../types";

const REQUEST_STATUS_LABELS: Record<RequestStatus, string> = {
  draft: "Nháp",
  submitted: "Đã gửi",
};

const RECORD_STATUS_LABELS: Record<RecordStatus, string> = {
  draft: "Nháp",
  confirmed: "Đã xác nhận",
};

const RESULT_LABELS: Record<ResultState, string> = {
  approved: "Đồng ý",
  conditional: "Đồng ý có điều kiện",
  rejected: "Không đồng ý",
};

export function requestStatusLabel(status: string): string {
  return REQUEST_STATUS_LABELS[status as RequestStatus] ?? status;
}

export function recordStatusLabel(status: string): string {
  return RECORD_STATUS_LABELS[status as RecordStatus] ?? status;
}

export function resultLabel(result: string | null | undefined): string {
  if (!result) return "";
  return RESULT_LABELS[result as ResultState] ?? result;
}

export function revisionLabel(revision: number): string {
  return `Bản sửa ${revision}`;
}

export const STATUS_LEGEND = [
  { label: "Nháp", className: "border-slate-200 bg-slate-100 text-slate-700" },
  { label: "Đã gửi", className: "border-sky-200 bg-sky-100 text-sky-900" },
  {
    label: "Đã xác nhận",
    className: "border-emerald-200 bg-emerald-100 text-emerald-900",
  },
  {
    label: "Đồng ý",
    className: "border-emerald-200 bg-emerald-50 text-emerald-800",
  },
  {
    label: "Có điều kiện",
    className: "border-amber-200 bg-amber-50 text-amber-900",
  },
  {
    label: "Không đồng ý",
    className: "border-rose-200 bg-rose-50 text-rose-800",
  },
] as const;
