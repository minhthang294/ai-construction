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
  drawing_number?: string | null;
  revision?: string | null;
  width?: number | null;
  height?: number | null;
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
  record_id?: string | null;
  source?: "page_extraction" | "database" | string | null;
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
  }>;
  created_at?: string | null;
  updated_at?: string | null;
};

export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  citations: Citation[];
  warnings: string[];
  confidence?: number;
  no_source?: boolean;
};

export type QuestionSuggestion = {
  id: string;
  label: string;
  prompt: string;
  mode: "send" | "fill";
  badge?: "verified" | "proposed" | "navigation" | "caution" | null;
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
