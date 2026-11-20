/** Types and pure helpers for reviewed daily journal snapshots and exports. */

export type JournalEvidence = {
  photo_id: string;
  sha256: string;
  filename: string | null;
  mime_type: string | null;
  caption: string | null;
  category: string | null;
  confirmed_caption: string | null;
  location: string | null;
  component: string | null;
  stage: string | null;
  sources: string[];
  relative_path?: string;
};

export type JournalPreview = {
  project_id: string;
  project_title: string;
  date: string;
  date_display: string;
  reviewed_only: boolean;
  snapshot_eligible: boolean;
  blockers: string[];
  daily_report: Record<string, unknown> | null;
  construction_events: Array<Record<string, unknown>>;
  acceptance_events: Array<Record<string, unknown>>;
  acceptance_count: number;
  journal: Record<string, unknown>;
  blank_sections: string[];
  warnings: string[];
  evidence: JournalEvidence[];
  omitted_evidence_refs: Array<Record<string, unknown>>;
  evidence_summary: {
    evidence_count: number;
    omitted_evidence_count: number;
  };
  preview_sha256: string;
  preview_text: string;
};

export type JournalSnapshot = {
  id: string;
  project_id: string;
  journal_date: string;
  sha256: string;
  reviewed_by: string | null;
  reviewed_at: string;
  evidence_count: number;
  omitted_evidence_count: number;
  acceptance_count: number;
  warnings: string[];
  download_url: string;
};

export type JournalExport = {
  id: string;
  project_id: string;
  snapshot_id: string;
  journal_date: string;
  format: "pdf" | "docx" | "zip";
  sha256: string;
  snapshot_sha256: string;
  download_url: string;
  auto_send: boolean;
  generated_at: string;
};

export type JournalExportFormat = JournalExport["format"];

/** A snapshot is only allowed after the user reviewed an eligible preview. */
export function canCreateJournalSnapshot(
  preview: JournalPreview | null,
  confirmed: boolean,
): boolean {
  return Boolean(
    preview &&
      confirmed &&
      preview.snapshot_eligible &&
      preview.preview_sha256.length === 64,
  );
}

export function journalBlockerLabel(blocker: string): string {
  if (blocker === "DAILY_REPORT_NOT_REVIEWED") {
    return "Báo cáo ngày chưa được duyệt.";
  }
  return blocker;
}
