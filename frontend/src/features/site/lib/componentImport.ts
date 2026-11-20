/** Types and pure helpers for the Sprint 1 component catalog import UI. */

export type ComponentType = "pile" | "beam";
export type ComponentScope = "DESIGN_SCOPE" | "ADDITIONAL_SCOPE";

export type ComponentCandidate = {
  source_id: string;
  source_row: number;
  zone: string;
  type: ComponentType;
  segment: number;
  design_group: string | null;
  canonical_code: string;
  raw_code: string;
  scope: ComponentScope;
  drawing: string;
  source: string;
  verification: "NEEDS_REVIEW";
  aliases: string[];
};

export type ComponentWorkLink = {
  source_id: string;
  code: string;
  dm_row: number;
  /** Row in the seed sheet LIEN_KET_CONG_VIEC. */
  seed_row: number;
  work: string;
  raw_location: string;
};

export type PreviewSegment = {
  source_id: string;
  zone: string;
  number: number;
};

/** Exact response of `POST /projects/{p}/components/import-preview`. */
export type ComponentPreview = {
  source_sha256: string;
  components: ComponentCandidate[];
  work_links: ComponentWorkLink[];
  segments: PreviewSegment[];
  conflicts: string[];
};

export type ComponentImportResult = {
  components: number;
  work_links: number;
  segments: number;
};

/** Item returned by `GET /projects/{p}/components`. */
export type ComponentSummary = {
  id: string;
  type: ComponentType;
  canonical_code: string;
  raw_code: string;
  segment_id: string;
  design_group_id: string | null;
  verification: string;
};

/** Item returned by `GET /projects/{p}/segments`. */
export type ComponentSegment = {
  id: string;
  number: number;
  source_code: string;
  zone: string;
};

export type ComponentFilters = {
  query: string;
  zone: string;
  type: string;
  segment: string;
  scope: string;
  verification: string;
};

export const EMPTY_COMPONENT_FILTERS: ComponentFilters = {
  query: "",
  zone: "",
  type: "",
  segment: "",
  scope: "",
  verification: "",
};

/** Manual creation only sends fields the shared core contract accepts. */
export type ManualComponentDraft = {
  segment_id: string;
  type: ComponentType | "";
  raw_code: string;
  canonical_code: string;
  scope: ComponentScope | "";
};

export type ManualComponentInput = {
  segment_id: string;
  type: ComponentType;
  raw_code: string;
  canonical_code: string;
  scope: ComponentScope;
};

export const EMPTY_MANUAL_COMPONENT: ManualComponentDraft = {
  segment_id: "",
  type: "",
  raw_code: "",
  canonical_code: "",
  scope: "",
};

export function manualComponentError(draft: ManualComponentDraft): string | null {
  if (!draft.segment_id.trim()) return "Chọn phân đoạn đã có.";
  if (!draft.type) return "Chọn loại cấu kiện.";
  if (!draft.scope) return "Chọn phạm vi.";
  if (!draft.raw_code.trim()) return "Nhập mã gốc.";
  if (draft.raw_code.trim().length > 120) return "Mã gốc tối đa 120 ký tự.";
  if (!draft.canonical_code.trim()) return "Nhập mã chuẩn.";
  if (draft.canonical_code.trim().length > 120) {
    return "Mã chuẩn tối đa 120 ký tự.";
  }
  return null;
}

/** Keep the user's casing; the server owns canonicalisation and verification. */
export function buildManualComponentPayload(
  draft: ManualComponentDraft,
): ManualComponentInput {
  if (!draft.type || !draft.scope) {
    throw new Error("Chọn loại và phạm vi trước khi gửi.");
  }
  return {
    segment_id: draft.segment_id.trim(),
    type: draft.type,
    raw_code: draft.raw_code.trim(),
    canonical_code: draft.canonical_code.trim(),
    scope: draft.scope,
  };
}

function searchable(component: ComponentCandidate): string {
  return [
    component.source_id,
    component.canonical_code,
    component.raw_code,
    component.drawing,
    component.source,
    component.design_group ?? "",
    ...component.aliases,
  ]
    .join(" ")
    .toLowerCase();
}

/** Filter for display only; values are shown exactly as the server returned them. */
export function filterPreviewComponents(
  components: ReadonlyArray<ComponentCandidate>,
  filters: ComponentFilters,
): ComponentCandidate[] {
  const query = filters.query.trim().toLowerCase();
  return components.filter((component) => {
    if (filters.zone && component.zone !== filters.zone) return false;
    if (filters.type && component.type !== filters.type) return false;
    if (filters.segment && String(component.segment) !== filters.segment) return false;
    if (filters.scope && component.scope !== filters.scope) return false;
    if (filters.verification && component.verification !== filters.verification) {
      return false;
    }
    return !query || searchable(component).includes(query);
  });
}

export function summarizePreview(preview: ComponentPreview) {
  return {
    components: preview.components.length,
    workLinks: preview.work_links.length,
    segments: preview.segments.length,
    conflicts: preview.conflicts.length,
  };
}

/** The backend rejects an empty inventory or any unresolved conflict. */
export function canCommitPreview(
  preview: ComponentPreview | null,
  hasWorkbook: boolean,
): boolean {
  return Boolean(
    preview &&
      hasWorkbook &&
      preview.conflicts.length === 0 &&
      preview.components.length > 0 &&
      preview.segments.length > 0,
  );
}

/** The key must stay stable across retries because the backend is idempotent. */
export function newIdempotencyKey(
  sourceSha256: string,
  random: string = typeof crypto !== "undefined" && crypto.randomUUID
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`,
): string {
  return `components:${sourceSha256.slice(0, 12)}:${random}`.slice(0, 120);
}

/**
 * `reviewed: true` is the caller's explicit confirmation. The exact preview
 * object is passed by reference so fields added by newer backends are never
 * dropped by a local re-serialisation. The UI has no per-row editing.
 */
export function buildCommitPayload(
  preview: ComponentPreview,
  sourceFileBase64: string,
  idempotencyKey: string,
) {
  return {
    reviewed: true as const,
    idempotency_key: idempotencyKey,
    preview,
    source_file_base64: sourceFileBase64,
  };
}

/** Raw bytes on purpose: the backend re-hashes the file and compares it. */
export function bytesToBase64(bytes: Uint8Array): string {
  let binary = "";
  const chunk = 0x8000;
  for (let index = 0; index < bytes.length; index += chunk) {
    binary += String.fromCharCode(...bytes.subarray(index, index + chunk));
  }
  return btoa(binary);
}

export async function fileToBase64(file: File): Promise<string> {
  return bytesToBase64(new Uint8Array(await file.arrayBuffer()));
}
