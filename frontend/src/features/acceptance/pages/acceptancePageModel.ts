import { AcceptanceApiError } from "../lib/api";
import { projectMetadataDefaults } from "../lib/projectPrefill";
import { recordStatusLabel, resultLabel, revisionLabel } from "../lib/statusLabels";
import type {
  AcceptanceNavigationPayload,
  AcceptanceRecord,
  AcceptanceRequest,
  ChecklistInput,
  LinkedDailyReport,
  ParticipantInput,
  ProjectContext,
  RecordInput,
  ResultState,
  YesNo,
} from "../types";
import { emptyChecklist } from "../types";

export type Tab = "requests" | "records";

export type RecordDraft = {
  id?: string;
  request_id: string;
  request_number?: string;
  project_name: string;
  client: string;
  project_location: string;
  location: string;
  number?: string | null;
  revision: number;
  stale: boolean;
  stale_warning?: string | null;
  status: "draft" | "confirmed";
  record_date: string;
  start_time: string;
  end_time: string;
  design_compliance: YesNo | "";
  technical_compliance: YesNo | "";
  other_notes: string;
  conclusion_note: string;
  result?: ResultState | null;
  participants: ParticipantInput[];
  checklist: ChecklistInput[];
};

export type PendingFilters = {
  batch_id?: string | null;
  stage_definition_id?: string | null;
};

export function shortDate(value: string): string {
  const [year, month, day] = value.split("-");
  return year && month && day ? `${day}/${month}/${year}` : value;
}

export function today(): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Ho_Chi_Minh",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
}

export function draftFor(
  record: AcceptanceRecord,
  request?: AcceptanceRequest,
  project?: ProjectContext | null,
): RecordDraft {
  const metadata = projectMetadataDefaults(project);
  return {
    id: record.id,
    request_id: record.request_id,
    request_number: request?.number,
    project_name: request?.project_name || metadata.project_name,
    client: request?.client || metadata.client,
    project_location: request?.project_location || metadata.project_location,
    location: request?.location ?? "",
    number: record.number,
    revision: record.revision,
    stale: record.stale,
    stale_warning: record.stale_warning,
    status: record.status,
    record_date: record.record_date ?? "",
    start_time: record.start_time ?? "",
    end_time: record.end_time ?? "",
    design_compliance: record.design_compliance ?? "",
    technical_compliance: record.technical_compliance ?? "",
    other_notes: record.other_notes ?? "",
    conclusion_note: record.conclusion_note ?? "",
    result: record.result,
    participants: record.participants.map((participant) => ({
      role: participant.role,
      person_name: participant.person_name,
      organization: participant.organization ?? "",
      position: participant.position ?? "",
      sort_order: participant.sort_order,
    })),
    checklist: record.checklist.map((item) => ({
      item: item.item,
      state: item.state,
      evidence_refs: item.evidence_refs,
      note: item.note ?? undefined,
      sort_order: item.sort_order,
    })),
  };
}

export function newDraft(
  request: AcceptanceRequest,
  project?: ProjectContext | null,
): RecordDraft {
  const metadata = projectMetadataDefaults(project);
  return {
    request_id: request.id,
    request_number: request.number,
    project_name: request.project_name || metadata.project_name,
    client: request.client || metadata.client,
    project_location: request.project_location || metadata.project_location,
    location: request.location ?? "",
    number: null,
    revision: 1,
    stale: false,
    stale_warning: null,
    status: "draft",
    record_date: today(),
    start_time: "",
    end_time: "",
    design_compliance: "",
    technical_compliance: "",
    other_notes: "",
    conclusion_note: "",
    result: null,
    // Deliberately empty: never reuse old personnel from the template.
    participants: [],
    checklist: emptyChecklist(),
  };
}

export function draftPayload(draft: RecordDraft): RecordInput {
  const participants = draft.participants
    .filter((participant) => participant.person_name.trim())
    .map((participant, index) => ({
      ...participant,
      person_name: participant.person_name.trim(),
      sort_order: index,
    }));
  const payload: RecordInput = {
    request_id: draft.request_id,
    number: draft.number ?? null,
    record_date: draft.record_date || null,
    start_time: draft.start_time.trim() || null,
    end_time: draft.end_time.trim() || null,
    design_compliance: draft.design_compliance || null,
    technical_compliance: draft.technical_compliance || null,
    other_notes: draft.other_notes.trim() || null,
    conclusion_note: draft.conclusion_note.trim() || null,
    checklist: draft.checklist,
  };
  // On the first save, omit an empty list so the backend can prefill from PYC.
  if (draft.id || participants.length > 0) payload.participants = participants;
  return payload;
}

export function errorMessage(error: unknown): string {
  if (error instanceof AcceptanceApiError) {
    return error.code ? `${error.message} (${error.code})` : error.message;
  }
  return error instanceof Error ? error.message : "Thao tác thất bại.";
}

export function hasPendingFilter(
  initialState?: AcceptanceNavigationPayload | null,
): boolean {
  return Boolean(initialState?.stage_definition_id || initialState?.batch_id);
}

export function pendingFilters(
  initialState: AcceptanceNavigationPayload | null | undefined,
  useFilter: boolean,
): PendingFilters {
  return useFilter
    ? {
        batch_id: initialState?.batch_id,
        stage_definition_id: initialState?.stage_definition_id,
      }
    : {};
}

export function requestSubtitle(request: AcceptanceRequest): string {
  return (
    request.location ||
    request.subject ||
    request.project_name ||
    "Chưa có nội dung"
  );
}

export function dailyReportLabel(
  report: LinkedDailyReport | null | undefined,
): string {
  return report ? `${report.report_date} (${report.status})` : "đã liên kết";
}

export function dailyReportHref(projectId: string, reportDate: string): string {
  return `/api/v1/projects/${projectId}/daily-reports/${reportDate}`;
}

export function recordActionLabel(record?: AcceptanceRecord): string {
  return record ? "Mở BBNT" : "Tạo BBNT";
}

export function recordPickerLabel(
  request: AcceptanceRequest,
  record?: AcceptanceRecord,
): string {
  return `PYC ${request.number} ${
    record ? `— BBNT ${recordStatusLabel(record.status)}` : "— chưa có BBNT"
  }`;
}

export function recordPickerActionLabel(record?: AcceptanceRecord): string {
  return record ? "Mở" : "Lập BBNT";
}

export function draftTitle(draft: RecordDraft): string {
  const subject = draft.number
    ? `số ${draft.number}`
    : draft.request_number
      ? `cho PYC ${draft.request_number}`
      : "(nháp)";
  return `BBNT ${subject} — ${revisionLabel(draft.revision)}`;
}

export function draftStatusSummary(draft: RecordDraft): string {
  return draft.status === "confirmed"
    ? `Đã xác nhận: ${resultLabel(draft.result) || "—"}`
    : "Nháp — chưa có kết luận";
}

export function deleteRequestWarning(
  request: AcceptanceRequest,
  record?: AcceptanceRecord,
): string {
  return record
    ? `PYC ${request.number} đã có BBNT (${recordStatusLabel(record.status)}). Xoá PYC sẽ xoá luôn BBNT liên quan và lịch sử xuất file. Không thể hoàn tác. Tiếp tục?`
    : request.status === "submitted"
      ? `PYC ${request.number} đã gửi. Xoá phiếu này và lịch sử xuất file? Không thể hoàn tác.`
      : `Xoá PYC ${request.number}? Không thể hoàn tác.`;
}
