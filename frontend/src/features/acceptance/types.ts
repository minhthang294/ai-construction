/** Shared types for the PYC/BBNT acceptance feature. */

export type ProjectContext = {
  id: string;
  name: string;
  client?: string | null;
  location?: string | null;
  report_title?: string | null;
};

export type TriState = "yes" | "no" | "unconfirmed";
export type RequestStatus = "draft" | "submitted";
export type RecordStatus = "draft" | "confirmed";
export type ResultState = "approved" | "conditional" | "rejected";
export type ParticipantRole =
  | "investor"
  | "supervisor"
  | "contractor"
  | "requester"
  | "other";
export type ResetPolicy = "never" | "yearly" | "monthly";
export type FieldKind = "construction" | "electric" | "mechanical";
export type Urgency = "normal" | "urgent" | "very_urgent";
export type YesNo = "yes" | "no";

export type AcceptanceNavigationPayload = {
  batch_id?: string | null;
  event_date?: string | null;
  component_ids?: string[];
  stage_definition_id?: string | null;
};

export type PendingAcceptanceComponent = {
  component_id: string;
  code: string;
  type: string;
  event_id: string;
  event_date: string;
  stage_id: string;
  stage_definition_id: string;
  scope_id?: string | null;
  stage_name: string;
};

export type PendingAcceptanceGroup = {
  stage_name: string;
  zone: string;
  segment: number;
  event_dates: string[];
  components: PendingAcceptanceComponent[];
};

export type PendingAcceptanceResponse = {
  project_id: string;
  batch_id?: string | null;
  stage_definition_id?: string | null;
  stage_name?: string | null;
  groups: PendingAcceptanceGroup[];
  total_components: number;
};

export type AcceptanceParticipant = {
  id: string;
  role: ParticipantRole;
  person_name: string;
  organization?: string | null;
  position?: string | null;
  sort_order: number;
};

export type AcceptanceChecklistItem = {
  id: string;
  item: string;
  state: TriState;
  evidence_refs: string[];
  note?: string | null;
  sort_order: number;
};

export type AcceptanceRequest = {
  id: string;
  project_id: string;
  work_item_id?: string | null;
  daily_report_id?: string | null;
  number: string;
  status: RequestStatus;
  requested_at: string;
  revision: number;
  requested_by_profile_id?: string | null;
  supervisor_profile_id?: string | null;
  investor_profile_id?: string | null;
  project_name?: string | null;
  client?: string | null;
  project_location?: string | null;
  location?: string | null;
  request_date?: string | null;
  inspection_time?: string | null;
  content?: string | null;
  subject?: string | null;
  field?: FieldKind | null;
  urgency?: Urgency | null;
  requested_by_name?: string | null;
  supervisor_name?: string | null;
  investor_name?: string | null;
  contractor_org?: string | null;
  supervisor_org?: string | null;
  investor_org?: string | null;
  notes?: string | null;
  excel_sync_warning?: string | null;
  created_at: string;
  updated_at: string;
};

export type AcceptanceRecord = {
  id: string;
  project_id: string;
  request_id: string;
  number?: string | null;
  status: RecordStatus;
  result?: ResultState | null;
  revision: number;
  supersedes_id?: string | null;
  request_updated_at?: string | null;
  stale: boolean;
  stale_warning?: string | null;
  reused: Record<string, unknown>;
  confirmer_id?: string | null;
  confirmed_at?: string | null;
  record_date?: string | null;
  start_time?: string | null;
  end_time?: string | null;
  design_compliance?: YesNo | null;
  technical_compliance?: YesNo | null;
  other_notes?: string | null;
  conclusion_note?: string | null;
  participants: AcceptanceParticipant[];
  checklist: AcceptanceChecklistItem[];
  created_at: string;
  updated_at: string;
};

export type AcceptanceExport = {
  id: string;
  project_id: string;
  kind: "pyc" | "bbnt";
  source_id: string;
  format: string;
  sha256: string;
  template_sha256?: string | null;
  download_url?: string | null;
  generated_at: string;
};

export type LinkedDailyReport = {
  id: string;
  project_id: string;
  report_date: string;
  status: string;
  notes?: string | null;
};

export type ParticipantProfile = {
  id: string;
  project_id: string;
  full_name: string;
  organization?: string | null;
  position?: string | null;
  role: ParticipantRole;
  active: boolean;
  created_at: string;
  updated_at: string;
};

export type ParticipantProfileInput = {
  full_name: string;
  organization?: string | null;
  position?: string | null;
  role: ParticipantRole;
  active?: boolean;
};

export type NumberingConfig = {
  project_id: string;
  kind: "pyc" | "bbnt";
  prefix: string;
  start_number: number;
  next_number: number;
  width: number;
  reset_policy: ResetPolicy;
  period_key?: string | null;
  date_format: string;
  updated_at?: string | null;
};

export type PreviewPayload = {
  kind: "pyc" | "bbnt";
  source_id: string;
  cells: Record<string, Record<string, unknown>>;
  warnings: string[];
  stale: boolean;
};

export type AcceptanceHistoryItem = {
  kind: "pyc" | "bbnt";
  id: string;
  number: string;
  status: string;
  revision: number;
  request_id?: string | null;
  result?: ResultState | null;
  updated_at: string;
};

export type WorkItemAcceptanceHistory = {
  work_item_id: string;
  items: AcceptanceHistoryItem[];
};

export type WorkItemSummary = {
  id: string;
  project_id: string;
  code: string;
  name: string;
  location?: string | null;
  component?: string | null;
  status: string;
};

export type ParticipantInput = {
  role: ParticipantRole;
  person_name: string;
  organization?: string;
  position?: string;
  sort_order: number;
};

export type ChecklistInput = {
  item: string;
  state: TriState;
  evidence_refs: string[];
  note?: string;
  sort_order: number;
};

export type RequestInput = {
  number?: string | null;
  work_item_id?: string | null;
  daily_report_id?: string | null;
  requested_by_profile_id?: string | null;
  supervisor_profile_id?: string | null;
  investor_profile_id?: string | null;
  status?: RequestStatus;
  project_name?: string | null;
  client?: string | null;
  project_location?: string | null;
  location?: string | null;
  request_date?: string | null;
  inspection_time?: string | null;
  content?: string | null;
  subject?: string | null;
  field?: FieldKind | null;
  urgency?: Urgency | null;
  requested_by_name?: string | null;
  supervisor_name?: string | null;
  investor_name?: string | null;
  contractor_org?: string | null;
  supervisor_org?: string | null;
  investor_org?: string | null;
  notes?: string | null;
};

export type RecordInput = {
  request_id: string;
  number?: string | null;
  record_date?: string | null;
  start_time?: string | null;
  end_time?: string | null;
  design_compliance?: YesNo | null;
  technical_compliance?: YesNo | null;
  other_notes?: string | null;
  conclusion_note?: string | null;
  participants?: ParticipantInput[];
  checklist?: ChecklistInput[];
};

export type ConfirmInput = {
  result: ResultState;
  conclusion_note?: string | null;
};

export const CHECKLIST_TEMPLATE: ReadonlyArray<string> = [
  "Phiếu yêu cầu nghiệm thu của nhà thầu",
  "Hồ sơ thiết kế bản vẽ thi công, chỉ dẫn kỹ thuật được chủ đầu tư phê duyệt",
  "Tiêu chuẩn, quy phạm xây dựng được áp dụng",
  "Kết quả thí nghiệm mẫu kiểm nghiệm của đối tượng nghiệm thu",
  "Nhật ký thi công",
  "Hình ảnh thi công, nghiệm thu",
  "Các tài liệu khác có liên quan",
];

export function emptyChecklist(): ChecklistInput[] {
  return CHECKLIST_TEMPLATE.map((item, index) => ({
    item,
    state: "unconfirmed",
    evidence_refs: [],
    sort_order: index,
  }));
}

export function hasUnresolvedChecklist(record: AcceptanceRecord): boolean {
  return record.checklist.some((item) => item.state !== "yes" && item.state !== "no");
}

export function confirmationBlockers(record: AcceptanceRecord): string[] {
  const blockers: string[] = [];
  const unresolved = record.checklist.filter(
    (item) => item.state !== "yes" && item.state !== "no",
  ).length;
  if (unresolved > 0) blockers.push(`${unresolved} mục checklist chưa xác nhận có/không`);
  if (!record.design_compliance) blockers.push("Chưa đánh giá mức đảm bảo so với thiết kế");
  if (!record.technical_compliance) blockers.push("Chưa đánh giá mức đạt yêu cầu kỹ thuật");
  return blockers;
}
