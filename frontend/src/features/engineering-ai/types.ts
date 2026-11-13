export type DocumentStatus =
  | "pending"
  | "running"
  | "ocr_completed"
  | "indexing"
  | "ready"
  | "failed";

export type PageSummary = {
  id: string;
  page_number: number;
  extraction_method: string;
  ocr_confidence?: number | null;
  drawing_number?: string | null;
  revision?: string | null;
  needs_review: boolean;
  url?: string | null;
};

export type SourceDocument = {
  id: string;
  project_id: string;
  type: string;
  original_name: string;
  document_key: string;
  version: number;
  is_current: boolean;
  is_effective: boolean;
  change_note?: string | null;
  effective_at?: string | null;
  effective_by?: string | null;
  sha256: string;
  status: DocumentStatus;
  mime_type?: string | null;
  size_bytes: number;
  page_count: number;
  drawing_number?: string | null;
  revision?: string | null;
  ocr_languages?: string | null;
  warnings: string[];
  error_message?: string | null;
  created_by?: string | null;
  ingest_started_at?: string | null;
  ingest_finished_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  original_url?: string | null;
  pages: PageSummary[];
  deduplicated: boolean;
};

export type DocumentPage = {
  id: string;
  project_id: string;
  document_id: string;
  page_number: number;
  extraction_method: string;
  text?: string | null;
  ocr_text?: string | null;
  tables: Array<{
    bbox?: number[];
    row_count?: number;
    col_count?: number;
    rows?: Array<Array<string | null>>;
  }>;
  ocr_confidence?: number | null;
  drawing_number?: string | null;
  revision?: string | null;
  width?: number | null;
  height?: number | null;
  needs_review: boolean;
  warnings: string[];
  render_url?: string | null;
  original_url?: string | null;
};

export type Citation = {
  document_id: string;
  document_name: string;
  version: number;
  page_number: number;
  drawing_number?: string | null;
  revision?: string | null;
  quote: string;
  url: string;
  ocr_confidence?: number | null;
  chunk_id?: string | null;
  page_id?: string | null;
  extraction_method?: string | null;
  score?: number | null;
  section?: string | null;
};

export type SearchResponse = {
  query: string;
  citations: Citation[];
  results: Citation[];
  has_sources: boolean;
  message?: string | null;
};

export type PageAction = {
  document_id: string;
  page_id?: string | null;
  page_number: number;
  label: string;
};

export type ChatResponse = {
  conversation_id: string;
  message_index: number;
  answer: string;
  citations: Citation[];
  confidence: number;
  no_source: boolean;
  warnings: string[];
  vision_used: boolean;
  vision_note?: string | null;
  page_action?: PageAction | null;
};

export type Conversation = {
  id: string;
  project_id: string;
  title?: string | null;
  messages: Array<{
    role: string;
    content: string;
    citations: Citation[];
    warnings: string[];
    created_at?: string | null;
    vision_used?: boolean;
    vision_note?: string | null;
  }>;
  created_at?: string | null;
  updated_at?: string | null;
};

export type PhotoSuggestion = {
  suggested_category?: string | null;
  suggested_caption?: string | null;
  regions: Array<{ left: number; top: number; width: number; height: number }>;
  confidence: number;
  requires_confirmation: boolean;
  disclaimer: string;
  warnings: string[];
};

export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  citations: Citation[];
  warnings: string[];
  confidence?: number;
  no_source?: boolean;
  vision_used?: boolean;
  vision_note?: string | null;
};

export type CrossReferenceSuggestion = {
  topic: string;
  first_citation: Citation;
  second_citation: Citation;
  observation: string;
  confidence: number;
  requires_engineer_review: boolean;
  warnings: string[];
};

export type CrossReferenceResponse = {
  project_id: string;
  status: string;
  citations: Citation[];
  suggestions: CrossReferenceSuggestion[];
  message: string;
  disclaimer: string;
  warnings: string[];
};

export type ReportDraftManpower = {
  entry_id?: string | null;
  group_name: string;
  person_name?: string | null;
  count: number | null;
  organization_id?: string | null;
};

export type ReportDraftWorkLog = {
  entry_id?: string | null;
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

export type ReportDraftPlan = {
  entry_id?: string | null;
  plan_date: string;
  work_item_id?: string | null;
  description?: string | null;
  location?: string | null;
  manpower?: string | null;
  equipment?: string | null;
  dependency?: string | null;
};

export type DailyReportDraftResponse = {
  project_id: string;
  source: "linked" | "provided";
  source_report_id?: string | null;
  source_status: string;
  draft: {
    report_date: string;
    status: string;
    notes?: string | null;
    manpower: ReportDraftManpower[];
    work_logs: ReportDraftWorkLog[];
    next_day_plans: ReportDraftPlan[];
    summary_lines: string[];
  };
  missing_fields: Array<{
    section: string;
    index?: number | null;
    field: string;
    message: string;
  }>;
  warnings: string[];
  disclaimer: string;
  no_invented_quantities: boolean;
};

export type InspectionChecklistSuggestion = {
  item: string;
  criterion: string;
  citation: Citation;
  status: "unconfirmed";
  requires_engineer_review: boolean;
  auto_approved: boolean;
  relevance_score: number;
  warnings: string[];
};

export type InspectionChecklistResponse = {
  project_id: string;
  work_item: {
    id?: string | null;
    code?: string | null;
    name?: string | null;
    location?: string | null;
    component?: string | null;
  };
  suggestions: InspectionChecklistSuggestion[];
  has_sources: boolean;
  no_source: boolean;
  message?: string | null;
  warnings: string[];
  disclaimer: string;
};

export type WorkItemSummary = {
  id: string;
  code: string;
  name: string;
  location?: string | null;
  component?: string | null;
  status?: string | null;
};

export type VersionSummary = {
  id: string;
  version: number;
  is_current: boolean;
  is_effective: boolean;
  status: string;
  original_name: string;
  sha256: string;
  page_count: number;
  chunk_count: number;
  total_chars: number;
  effective_at?: string | null;
  effective_by?: string | null;
};

export type VersionCompareResponse = {
  project_id: string;
  same_document_key: boolean;
  left: VersionSummary;
  right: VersionSummary;
  page_count_delta: number;
  chunk_count_delta: number;
  total_chars_delta: number;
  left_table_count: number;
  right_table_count: number;
  page_changes: Array<{
    page_number: number;
    left_chars: number;
    right_chars: number;
    changed: boolean;
  }>;
  warnings: string[];
  disclaimer: string;
};

export type PageExtractionStatus = "proposed" | "verified" | "rejected";

export type PageExtractionRecord = {
  id: string;
  project_id: string;
  document_id: string;
  page_id: string;
  page_number: number;
  page_sha256?: string | null;
  model: string;
  prompt_version: string;
  mode: string;
  status: PageExtractionStatus;
  confidence?: number | null;
  extraction: {
    page_type?: string;
    title?: string | null;
    drawing_number?: string | null;
    revision?: string | null;
    summary?: string;
    key_values?: Array<{
      name: string;
      value: string;
      unit?: string | null;
      quote: string;
    }>;
    table_rows?: string[][];
    warnings?: string[];
  };
  warnings: string[];
  created_by?: string | null;
  verified_by?: string | null;
  verified_at?: string | null;
  verify_note?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};
