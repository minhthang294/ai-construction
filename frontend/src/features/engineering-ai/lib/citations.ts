import type { Citation } from "../types";

export type CitationDisplay = {
  isDatabase: boolean;
  title: string;
  table: string | null;
  code: string | null;
  recordId: string | null;
  pageLabel: string | null;
};

function firstString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

/** Compact display data for a citation; database quotes carry the row JSON. */
export function citationDisplay(citation: Citation): CitationDisplay {
  const isDatabase = citation.source === "database";
  const recordId = citation.record_id ?? (isDatabase ? citation.document_id : null);
  if (!isDatabase) {
    return {
      isDatabase,
      title: citation.document_name,
      table: null,
      code: null,
      recordId,
      pageLabel: citation.page_number > 0 ? `trang ${citation.page_number}` : null,
    };
  }

  let row: Record<string, unknown> = {};
  try {
    const parsed = JSON.parse(citation.quote);
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      row = parsed as Record<string, unknown>;
    }
  } catch {
    row = {};
  }
  const table = citation.document_name.replace(/^Database\s*·\s*/, "") || "database";
  const code =
    firstString(row.canonical_code) ??
    firstString(row.raw_code) ??
    firstString(row.component_code) ??
    firstString(row.alias);
  const componentLabel = code ? `Cấu kiện ${code}` : table;
  return {
    isDatabase,
    title: componentLabel,
    table,
    code,
    recordId,
    pageLabel: null,
  };
}
