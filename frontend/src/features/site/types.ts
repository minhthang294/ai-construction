export type ManpowerEntry = {
  id?: string;
  group_name: string;
  person_name?: string | null;
  /** `0` is an explicit zero; `null` means the number is unknown. */
  count: number | null;
  organization_id?: string | null;
};

export type ManpowerPreset = ManpowerEntry & {
  id: string;
  project_id: string;
  created_at: string;
  updated_at: string;
};

export type Organization = {
  id: string;
  project_id: string;
  name: string;
  kind?: string | null;
};

export type SiteNotes = {
  weather?: string | null;
  materials?: string | null;
  equipment?: string | null;
  incidents?: string | null;
  difficulties?: string | null;
  safety?: string | null;
  recommendations?: string | null;
  other?: string | null;
};

export const SITE_NOTE_FIELDS = [
  { key: "weather", label: "Thời tiết", placeholder: "Nắng, mưa, nhiệt độ…" },
  { key: "materials", label: "Vật tư", placeholder: "Vật tư nhận/thiếu…" },
  { key: "equipment", label: "Thiết bị", placeholder: "Thiết bị/hư hỏng…" },
  { key: "incidents", label: "Sự cố", placeholder: "Sự cố trong ngày…" },
  { key: "difficulties", label: "Khó khăn", placeholder: "Vướng mắc…" },
  { key: "safety", label: "An toàn", placeholder: "An toàn lao động…" },
  { key: "recommendations", label: "Kiến nghị", placeholder: "Đề xuất xử lý…" },
  { key: "other", label: "Khác", placeholder: "Nội dung khác…" },
] as const;

export type SiteNoteField = (typeof SITE_NOTE_FIELDS)[number]["key"];

export type DailyWorkLog = {
  id?: string;
  work_item_id?: string | null;
  location?: string | null;
  component?: string | null;
  quantity?: number | null;
  unit?: string | null;
  start_time?: string | null;
  end_time?: string | null;
  status?: string | null;
  notes?: string | null;
};

export type NextDayPlan = {
  id?: string;
  plan_date: string;
  work_item_id?: string | null;
  description?: string | null;
  location?: string | null;
  manpower?: string | null;
  equipment?: string | null;
  dependency?: string | null;
};

export type WorkItem = {
  id: string;
  project_id: string;
  code: string;
  name: string;
  location?: string | null;
  component?: string | null;
  status: string;
};

export type ReportStatus = "draft" | "reviewed";

export type DailyReportInput = {
  status: ReportStatus;
  notes: string | null;
  site_notes: SiteNotes;
  manpower: ManpowerEntry[];
  work_logs: DailyWorkLog[];
  next_day_plans: NextDayPlan[];
};

export type DailyReport = DailyReportInput & {
  id: string;
  project_id: string;
  report_date: string;
  created_at: string;
  updated_at: string;
};

export type SitePhoto = {
  id: string;
  project_id: string;
  report_id?: string | null;
  sha256: string;
  capture_time?: string | null;
  upload_time: string;
  gps_lat?: number | null;
  gps_lon?: number | null;
  /** GPS copied from EXIF; never auto-confirmed. */
  gps_source?: string | null;
  gps_confirmed: boolean;
  device?: string | null;
  category?: string | null;
  location?: string | null;
  component?: string | null;
  stage?: string | null;
  suggested_caption?: string | null;
  confirmed_caption?: string | null;
  mime_type?: string | null;
  size_bytes?: number | null;
  filename?: string | null;
  client_upload_id?: string | null;
  sync_status?: "synced" | string;
  work_item_ids: string[];
};

export type ExportFormat = "zalo" | "pdf" | "docx" | "zip";

export type ExportResult = {
  id: string;
  project_id: string;
  report_id?: string | null;
  report_date?: string | null;
  format: ExportFormat | string;
  sha256: string;
  snapshot_sha256?: string | null;
  download_url?: string | null;
  preview_text?: string | null;
  /** Always false: Zalo is copied/downloaded manually, never sent. */
  auto_send: boolean;
  generated_at: string;
};

export type AcceptanceRecordSummary = {
  id: string;
  number?: string | null;
  status: string;
  result?: string | null;
  revision?: number | null;
  stale?: boolean;
  warnings?: string[];
  confirmed_at?: string | null;
};

export type AcceptanceRequestSummary = {
  id: string;
  number: string;
  status: string;
  work_item_id?: string | null;
  revision?: number | null;
  stale?: boolean;
  warnings?: string[];
  requested_at?: string | null;
  records: AcceptanceRecordSummary[];
};

export type WorkItemAcceptanceHistory = {
  work_item_id: string;
  requests: AcceptanceRequestSummary[];
};

export const PHOTO_CATEGORIES = [
  { value: "progress", label: "Tiến độ" },
  { value: "issue", label: "Vướng mắc" },
  { value: "material", label: "Vật tư" },
  { value: "safety", label: "An toàn" },
  { value: "handover", label: "Bàn giao" },
  { value: "other", label: "Khác" },
] as const;

export type PhotoCategory = (typeof PHOTO_CATEGORIES)[number]["value"];

export const PHOTO_STAGES = [
  { value: "before", label: "Trước thi công" },
  { value: "during", label: "Đang thi công" },
  { value: "after", label: "Hoàn thành" },
  { value: "handover", label: "Bàn giao" },
  { value: "issue", label: "Sự cố" },
  { value: "other", label: "Khác" },
] as const;

export type PhotoStage = (typeof PHOTO_STAGES)[number]["value"];

export type PhotoFilters = {
  date: string;
  location: string;
  component: string;
  stage: string;
  work_item_id: string;
};

export const EMPTY_PHOTO_FILTERS: PhotoFilters = {
  date: "",
  location: "",
  component: "",
  stage: "",
  work_item_id: "",
};

export function photoStageLabel(value?: string | null): string {
  if (!value) return "Chưa phân giai đoạn";
  return PHOTO_STAGES.find((item) => item.value === value)?.label ?? value;
}

export function photoCategoryLabel(value?: string | null): string {
  if (!value) return "Chưa phân loại";
  return PHOTO_CATEGORIES.find((item) => item.value === value)?.label ?? value;
}
