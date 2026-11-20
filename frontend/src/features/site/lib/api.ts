import type {
  DailyReport,
  DailyReportInput,
  ExportFormat,
  ExportResult,
  ManpowerPreset,
  Organization,
  PhotoFilters,
  SitePhoto,
  WorkItem,
} from "../types";
import type {
  ComponentImportResult,
  ComponentPreview,
  ComponentSegment,
  ComponentSummary,
  ManualComponentInput,
} from "./componentImport";
import type {
  BulkProgressInput,
  DesignQuantityMap,
  ProgressFilters,
  ProgressPreview,
  ProgressRow,
  ProgressSaveResult,
  StageDefinition,
} from "./componentProgress";
import type {
  JournalExport,
  JournalExportFormat,
  JournalPreview,
  JournalSnapshot,
} from "./journal";

const API_BASE = (import.meta as any)?.env?.VITE_API_BASE ?? "/api/v1";

function authHeaders(init?: RequestInit): Headers {
  let token: string | null = null;
  try {
    token =
      typeof localStorage === "undefined" ? null : localStorage.getItem("access_token");
  } catch {
    token = null;
  }
  const headers = new Headers(init?.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  return headers;
}

export async function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  return fetch(`${API_BASE}${path}`, { ...init, headers: authHeaders(init) });
}

/** Fetch a server-provided URL (already includes `/api/v1`). */
export async function apiFetchUrl(url: string, init?: RequestInit): Promise<Response> {
  let target = url;
  if (!/^https?:/i.test(url) && /^https?:/i.test(API_BASE)) {
    target = new URL(url, API_BASE).toString();
  }
  return fetch(target, { ...init, headers: authHeaders(init) });
}

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function readError(res: Response): Promise<string> {
  try {
    const body = await res.json();
    if (typeof body?.detail === "string") return body.detail;
    return JSON.stringify(body);
  } catch {
    return `${res.status} ${res.statusText}`;
  }
}

async function fail(res: Response): Promise<never> {
  throw new ApiError(await readError(res), res.status);
}

export async function getDailyReport(
  projectId: string,
  date: string,
): Promise<DailyReport | null> {
  const res = await apiFetch(`/projects/${projectId}/daily-reports/${date}`);
  if (res.status === 404) return null;
  if (!res.ok) return fail(res);
  return res.json();
}

export async function saveDailyReport(
  projectId: string,
  date: string,
  body: DailyReportInput,
): Promise<DailyReport> {
  const res = await apiFetch(`/projects/${projectId}/daily-reports/${date}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) return fail(res);
  return res.json();
}

export type UploadPhotoMeta = {
  reportId?: string;
  category?: string;
  location?: string;
  component?: string;
  stage?: string;
  confirmedCaption?: string;
  suggestedCaption?: string;
  workItemIds?: string[];
  clientUploadIds?: string[];
};

export async function uploadPhotos(
  projectId: string,
  files: File[],
  meta: UploadPhotoMeta = {},
): Promise<SitePhoto[]> {
  const form = new FormData();
  files.forEach((file) => form.append("files", file));
  if (meta.reportId) form.append("report_id", meta.reportId);
  if (meta.category) form.append("category", meta.category);
  if (meta.location) form.append("location", meta.location);
  if (meta.component) form.append("component", meta.component);
  if (meta.stage) form.append("stage", meta.stage);
  if (meta.confirmedCaption) form.append("confirmed_caption", meta.confirmedCaption);
  if (meta.suggestedCaption) form.append("suggested_caption", meta.suggestedCaption);
  if (meta.workItemIds?.length) form.append("work_item_ids", meta.workItemIds.join(","));
  if (meta.clientUploadIds?.length) {
    form.append("client_upload_ids", meta.clientUploadIds.join(","));
  }
  const res = await apiFetch(`/projects/${projectId}/photos`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) return fail(res);
  return res.json();
}

export async function listPhotos(
  projectId: string,
  reportId?: string | null,
  filters?: Partial<PhotoFilters>,
): Promise<SitePhoto[]> {
  const params = new URLSearchParams();
  if (reportId) params.set("report_id", reportId);
  if (filters?.date) params.set("date", filters.date);
  if (filters?.location) params.set("location", filters.location);
  if (filters?.component) params.set("component", filters.component);
  if (filters?.stage) params.set("stage", filters.stage);
  if (filters?.work_item_id) params.set("work_item_id", filters.work_item_id);
  const query = params.toString() ? `?${params.toString()}` : "";
  const res = await apiFetch(`/projects/${projectId}/photos${query}`);
  if (!res.ok) return fail(res);
  return res.json();
}

export type PhotoPatch = {
  report_id?: string | null;
  category?: string | null;
  location?: string | null;
  component?: string | null;
  stage?: string | null;
  suggested_caption?: string | null;
  confirmed_caption?: string | null;
  work_item_ids?: string[] | null;
};

export async function patchPhoto(
  projectId: string,
  photoId: string,
  body: PhotoPatch,
): Promise<SitePhoto> {
  const res = await apiFetch(`/projects/${projectId}/photos/${photoId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) return fail(res);
  return res.json();
}

/** Fetch the original photo with the bearer token and return a blob URL. */
export async function fetchPhotoObjectUrl(
  projectId: string,
  photoId: string,
  signal?: AbortSignal,
): Promise<string> {
  const res = await apiFetch(`/projects/${projectId}/photos/${photoId}/original`, {
    signal,
  });
  if (!res.ok) return fail(res);
  return URL.createObjectURL(await res.blob());
}

export async function getWorkItems(projectId: string): Promise<WorkItem[]> {
  const res = await apiFetch(`/projects/${projectId}/work-items`);
  if (!res.ok) return fail(res);
  return res.json();
}

export async function getOrganizations(projectId: string): Promise<Organization[]> {
  const res = await apiFetch(`/projects/${projectId}/organizations`);
  if (!res.ok) return fail(res);
  return res.json();
}

export async function previewComponentImport(
  projectId: string,
  file: File,
): Promise<ComponentPreview> {
  const form = new FormData();
  form.append("file", file, file.name);
  const res = await apiFetch(`/projects/${projectId}/components/import-preview`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) return fail(res);
  return res.json();
}

export type ComponentCommitPayload = {
  reviewed: true;
  idempotency_key: string;
  preview: ComponentPreview;
  source_file_base64: string;
};

export async function commitComponentImport(
  projectId: string,
  payload: ComponentCommitPayload,
): Promise<ComponentImportResult> {
  const res = await apiFetch(`/projects/${projectId}/components/import-commit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) return fail(res);
  return res.json();
}

export async function listComponents(
  projectId: string,
  query?: string,
): Promise<ComponentSummary[]> {
  const search = query?.trim();
  const suffix = search ? `?q=${encodeURIComponent(search)}` : "";
  const res = await apiFetch(`/projects/${projectId}/components${suffix}`);
  if (!res.ok) return fail(res);
  return res.json();
}

export async function createComponent(
  projectId: string,
  payload: ManualComponentInput,
): Promise<ComponentSummary> {
  const res = await apiFetch(`/projects/${projectId}/components`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) return fail(res);
  return res.json();
}

export async function listSegments(
  projectId: string,
  zone?: string,
): Promise<ComponentSegment[]> {
  const suffix = zone ? `?zone=${encodeURIComponent(zone)}` : "";
  const res = await apiFetch(`/projects/${projectId}/segments${suffix}`);
  if (!res.ok) return fail(res);
  return res.json();
}

export async function listStageDefinitions(
  projectId: string,
  type?: "pile" | "beam",
): Promise<StageDefinition[]> {
  const suffix = type ? `?type=${type}` : "";
  const res = await apiFetch(`/projects/${projectId}/stage-definitions${suffix}`);
  if (!res.ok) return fail(res);
  return res.json();
}

export async function listComponentProgress(
  projectId: string,
  filters?: Partial<ProgressFilters>,
): Promise<ProgressRow[]> {
  const params = new URLSearchParams();
  const query = filters?.query?.trim();
  if (query) params.set("q", query);
  if (filters?.zone) params.set("zone", filters.zone);
  if (filters?.segment) params.set("segment_id", filters.segment);
  if (filters?.type) params.set("type", filters.type);
  if (filters?.stage_definition_id) {
    params.set("stage_definition_id", filters.stage_definition_id);
  }
  if (filters?.construction_status) {
    params.set("construction_status", filters.construction_status);
  }
  if (filters?.acceptance_status) {
    params.set("acceptance_status", filters.acceptance_status);
  }
  const suffix = params.toString() ? `?${params.toString()}` : "";
  const res = await apiFetch(`/projects/${projectId}/progress${suffix}`);
  if (!res.ok) return fail(res);
  return res.json();
}

/** Read-only design quantities keyed by concrete stage id. */
export async function getDesignQuantities(
  projectId: string,
  componentIds: string[],
  signal?: AbortSignal,
): Promise<DesignQuantityMap> {
  const res = await apiFetch(`/projects/${projectId}/progress/design-quantities`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ component_ids: componentIds }),
    signal,
  });
  if (!res.ok) return fail(res);
  return res.json();
}

export async function previewProgressBulk(
  projectId: string,
  payload: BulkProgressInput,
): Promise<ProgressPreview> {
  const res = await apiFetch(`/projects/${projectId}/progress/bulk-preview`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) return fail(res);
  return res.json();
}

export type ProgressSavePayload = BulkProgressInput & {
  reviewed: true;
  idempotency_key: string;
};

export async function saveProgressBulk(
  projectId: string,
  payload: ProgressSavePayload,
): Promise<ProgressSaveResult> {
  const res = await apiFetch(`/projects/${projectId}/progress/bulk`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) return fail(res);
  return res.json();
}

/** Read-only preview: unreviewed/missing sections stay explicit. */
export async function getJournalPreview(
  projectId: string,
  date: string,
): Promise<JournalPreview> {
  const res = await apiFetch(
    `/projects/${projectId}/journals/${date}/preview`,
  );
  if (!res.ok) return fail(res);
  return res.json();
}

export async function createJournalSnapshot(
  projectId: string,
  date: string,
  previewSha256: string,
): Promise<JournalSnapshot> {
  const res = await apiFetch(`/projects/${projectId}/journals/${date}/snapshots`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reviewed: true, preview_sha256: previewSha256 }),
  });
  if (!res.ok) return fail(res);
  return res.json();
}

export async function listJournalSnapshots(
  projectId: string,
  date: string,
): Promise<JournalSnapshot[]> {
  const res = await apiFetch(`/projects/${projectId}/journals/${date}/snapshots`);
  if (!res.ok) return fail(res);
  return res.json();
}

export async function createJournalExport(
  projectId: string,
  date: string,
  snapshotId: string,
  format: JournalExportFormat,
): Promise<JournalExport> {
  const res = await apiFetch(`/projects/${projectId}/journals/${date}/exports`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ snapshot_id: snapshotId, format }),
  });
  if (!res.ok) return fail(res);
  return res.json();
}

export async function listJournalExports(
  projectId: string,
  date: string,
): Promise<JournalExport[]> {
  const res = await apiFetch(`/projects/${projectId}/journals/${date}/exports`);
  if (!res.ok) return fail(res);
  return res.json();
}

/** Download the frozen snapshot JSON with auth headers. */
export async function downloadJournalSnapshot(
  result: JournalSnapshot,
): Promise<void> {
  const res = await apiFetchUrl(result.download_url);
  if (!res.ok) return fail(res);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `nhat-ky-${result.journal_date}-snapshot.json`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

/** Download a frozen journal export with auth headers. */
export async function downloadJournalExport(
  result: JournalExport,
): Promise<void> {
  if (!result.download_url) throw new Error("Export has no download URL");
  const res = await apiFetchUrl(result.download_url);
  if (!res.ok) return fail(res);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `nhat-ky-${result.journal_date}-${result.format}`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export type ManpowerPresetInput = Pick<
  ManpowerPreset,
  "group_name" | "person_name" | "count" | "organization_id"
>;

export async function listManpowerPresets(
  projectId: string,
): Promise<ManpowerPreset[]> {
  const res = await apiFetch(`/projects/${projectId}/manpower-presets`);
  if (!res.ok) return fail(res);
  return res.json();
}

export async function createManpowerPreset(
  projectId: string,
  payload: ManpowerPresetInput,
): Promise<ManpowerPreset> {
  const res = await apiFetch(`/projects/${projectId}/manpower-presets`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) return fail(res);
  return res.json();
}

export async function updateManpowerPreset(
  projectId: string,
  presetId: string,
  payload: ManpowerPresetInput,
): Promise<ManpowerPreset> {
  const res = await apiFetch(
    `/projects/${projectId}/manpower-presets/${presetId}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
  if (!res.ok) return fail(res);
  return res.json();
}

export async function deleteManpowerPreset(
  projectId: string,
  presetId: string,
): Promise<void> {
  const res = await apiFetch(
    `/projects/${projectId}/manpower-presets/${presetId}`,
    { method: "DELETE" },
  );
  if (!res.ok) return fail(res);
}

export async function createExport(
  projectId: string,
  date: string,
  format: ExportFormat,
): Promise<ExportResult> {
  const res = await apiFetch(`/projects/${projectId}/daily-reports/${date}/exports`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ format }),
  });
  if (!res.ok) return fail(res);
  return res.json();
}

export async function listExports(
  projectId: string,
  date: string,
): Promise<ExportResult[]> {
  const res = await apiFetch(`/projects/${projectId}/daily-reports/${date}/exports`);
  if (!res.ok) return fail(res);
  return res.json();
}

/** Download an export with auth headers (plain <a href> cannot send Bearer). */
export async function downloadExport(result: ExportResult): Promise<void> {
  if (!result.download_url) throw new Error("Export has no download URL");
  const res = await apiFetchUrl(result.download_url);
  if (!res.ok) return fail(res);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `bao-cao-${result.report_date ?? "ngay"}-${result.format}`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export async function copyText(text: string): Promise<void> {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  document.body.appendChild(textarea);
  textarea.select();
  document.execCommand("copy");
  textarea.remove();
}

export function canShareText(): boolean {
  return (
    typeof navigator !== "undefined" && typeof navigator.share === "function"
  );
}

export type ShareOutcome = "shared" | "copied" | "cancelled" | "unavailable";

/**
 * User-triggered share only.  Never called automatically; if the device has no
 * Web Share API it copies the text instead, and cancellation does not fall back
 * to copying without the user's action.
 */
export async function shareText(
  title: string,
  text: string,
): Promise<ShareOutcome> {
  if (canShareText()) {
    try {
      await navigator.share({ title, text });
      return "shared";
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") {
        return "cancelled";
      }
    }
  }
  try {
    await copyText(text);
    return "copied";
  } catch {
    return "unavailable";
  }
}

export function originalPhotoUrl(projectId: string, photoId: string): string {
  return `${API_BASE}/projects/${projectId}/photos/${photoId}/original`;
}
