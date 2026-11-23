import type {
  AcceptanceExport,
  AcceptanceRecord,
  AcceptanceRequest,
  ConfirmInput,
  LinkedDailyReport,
  NumberingConfig,
  ParticipantProfile,
  ParticipantProfileInput,
  PendingAcceptanceResponse,
  PreviewPayload,
  ProjectContext,
  RecordInput,
  RequestInput,
  WorkItemAcceptanceHistory,
  WorkItemSummary,
} from "../types";

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

export class AcceptanceApiError extends Error {
  status: number;
  code?: string;

  constructor(status: number, message: string, code?: string) {
    super(message);
    this.name = "AcceptanceApiError";
    this.status = status;
    this.code = code;
  }
}

async function readError(response: Response): Promise<AcceptanceApiError> {
  let detail = `HTTP ${response.status}`;
  let code: string | undefined;
  try {
    const body = await response.json();
    if (typeof body?.detail === "string") detail = body.detail;
    if (typeof body?.code === "string") code = body.code;
  } catch {
    // Non-JSON error body; keep the HTTP status message.
  }
  return new AcceptanceApiError(response.status, detail, code);
}

export async function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  return fetch(`${API_BASE}${path}`, { ...init, headers: authHeaders(init) });
}

function resolveApiUrl(url: string, apiBase: string = API_BASE): string {
  if (/^https?:/i.test(url)) return url;
  if (/^https?:/i.test(apiBase)) return new URL(url, apiBase).toString();
  if (url.startsWith("/")) return url;
  return `${apiBase}/${url.replace(/^\/+/, "")}`;
}

/**
 * Only send the bearer token to this app or the configured API origin.
 *
 * A server-provided absolute URL must never receive the admin token by
 * accident; relative URLs resolve against the page/API as before.
 */
export function isTrustedApiUrl(
  url: string,
  apiBase: string = API_BASE,
  pageOrigin: string = typeof window === "undefined"
    ? ""
    : window.location.origin,
): boolean {
  const resolved = resolveApiUrl(url, apiBase);
  const origin = pageOrigin || "http://localhost";
  let targetOrigin: string;
  try {
    targetOrigin = new URL(resolved, origin).origin;
  } catch {
    return false;
  }
  const allowed = new Set([new URL(origin).origin]);
  if (/^https?:/i.test(apiBase)) {
    try {
      allowed.add(new URL(apiBase).origin);
    } catch {
      return false;
    }
  }
  return allowed.has(targetOrigin);
}

/** Fetch a server-provided URL (already includes `/api/v1`). */
export async function apiFetchUrl(url: string, init?: RequestInit): Promise<Response> {
  if (!isTrustedApiUrl(url)) {
    throw new AcceptanceApiError(
      400,
      "Đường dẫn tải file không cùng nguồn với API; đã chặn gửi token.",
      "download_origin_invalid",
    );
  }
  return fetch(resolveApiUrl(url), { ...init, headers: authHeaders(init) });
}

async function jsonRequest<T>(path: string, init: RequestInit): Promise<T> {
  const response = await apiFetch(path, init);
  if (!response.ok) throw await readError(response);
  return response.json() as Promise<T>;
}

function jsonInit(method: string, body: unknown): RequestInit {
  return {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
}

/**
 * Project setup values reused by PYC/BBNT headers.
 *
 * The core API exposes them through `GET /projects` (including client and
 * location); the acceptance module deliberately does not duplicate project
 * storage or edit shared core.
 */
export async function getProjectContext(
  projectId: string,
): Promise<ProjectContext | null> {
  const response = await apiFetch("/projects", { method: "GET" });
  if (!response.ok) throw await readError(response);
  const projects = (await response.json()) as ProjectContext[];
  return projects.find((project) => project.id === projectId) ?? null;
}

export function listRequests(projectId: string): Promise<AcceptanceRequest[]> {
  return jsonRequest(`/projects/${projectId}/acceptance-requests`, { method: "GET" });
}

export function listPendingAcceptance(
  projectId: string,
  params: { batch_id?: string | null; stage_definition_id?: string | null } = {},
): Promise<PendingAcceptanceResponse> {
  const query = new URLSearchParams();
  if (params.batch_id) query.set("batch_id", params.batch_id);
  if (params.stage_definition_id) {
    query.set("stage_definition_id", params.stage_definition_id);
  }
  const suffix = query.size ? `?${query.toString()}` : "";
  return jsonRequest(`/projects/${projectId}/acceptance/pending${suffix}`, {
    method: "GET",
  });
}

export function createRequestFromComponents(
  projectId: string,
  body: {
    component_ids: string[];
    stage_definition_id?: string | null;
    event_date?: string | null;
    request_date?: string | null;
  },
): Promise<AcceptanceRequest> {
  return jsonRequest(
    `/projects/${projectId}/acceptance/requests/from-components`,
    jsonInit("POST", body),
  );
}

export function getRequest(projectId: string, requestId: string): Promise<AcceptanceRequest> {
  return jsonRequest(
    `/projects/${projectId}/acceptance-requests/${requestId}`,
    { method: "GET" },
  );
}

export function createRequest(
  projectId: string,
  body: RequestInput,
): Promise<AcceptanceRequest> {
  return jsonRequest(
    `/projects/${projectId}/acceptance-requests`,
    jsonInit("POST", body),
  );
}

export function updateRequest(
  projectId: string,
  requestId: string,
  body: Partial<RequestInput>,
): Promise<AcceptanceRequest> {
  return jsonRequest(
    `/projects/${projectId}/acceptance-requests/${requestId}`,
    jsonInit("PATCH", body),
  );
}

/** Delete a PYC; force also removes its linked BBNT records and exports. */
export async function deleteRequest(
  projectId: string,
  requestId: string,
  force = false,
): Promise<void> {
  const query = force ? "?force=true" : "";
  const response = await apiFetch(
    `/projects/${projectId}/acceptance-requests/${requestId}${query}`,
    { method: "DELETE" },
  );
  if (!response.ok) throw await readError(response);
}

/** Render the filled PYC form to an authenticated PNG preview. */
export async function fetchRequestPreviewImage(
  projectId: string,
  requestId: string,
): Promise<string> {
  const response = await apiFetch(
    `/projects/${projectId}/acceptance-requests/${requestId}/preview-image`,
    { method: "GET" },
  );
  if (!response.ok) throw await readError(response);
  return URL.createObjectURL(await response.blob());
}

/** Read the daily report linked to a PYC, if any. */
export function getRequestDailyReport(
  projectId: string,
  requestId: string,
): Promise<LinkedDailyReport | null> {
  return jsonRequest(
    `/projects/${projectId}/acceptance-requests/${requestId}/daily-report`,
    { method: "GET" },
  );
}

/** Look up a project's daily report by date (read-only link helper). */
export async function getDailyReportByDate(
  projectId: string,
  reportDate: string,
): Promise<LinkedDailyReport | null> {
  const response = await apiFetch(
    `/projects/${projectId}/daily-reports/${encodeURIComponent(reportDate)}`,
    { method: "GET" },
  );
  if (response.status === 404) return null;
  if (!response.ok) throw await readError(response);
  return response.json() as Promise<LinkedDailyReport>;
}

export function listParticipantProfiles(
  projectId: string,
  activeOnly = false,
): Promise<ParticipantProfile[]> {
  const query = activeOnly ? "?active_only=true" : "";
  return jsonRequest(`/projects/${projectId}/acceptance-participants${query}`, {
    method: "GET",
  });
}

export function createParticipantProfile(
  projectId: string,
  body: ParticipantProfileInput,
): Promise<ParticipantProfile> {
  return jsonRequest(
    `/projects/${projectId}/acceptance-participants`,
    jsonInit("POST", body),
  );
}

export function updateParticipantProfile(
  projectId: string,
  profileId: string,
  body: Partial<ParticipantProfileInput>,
): Promise<ParticipantProfile> {
  return jsonRequest(
    `/projects/${projectId}/acceptance-participants/${profileId}`,
    jsonInit("PATCH", body),
  );
}

export async function deleteParticipantProfile(
  projectId: string,
  profileId: string,
): Promise<void> {
  const response = await apiFetch(
    `/projects/${projectId}/acceptance-participants/${profileId}`,
    { method: "DELETE" },
  );
  if (!response.ok) throw await readError(response);
}

export function listWorkItems(projectId: string): Promise<WorkItemSummary[]> {
  return jsonRequest(`/projects/${projectId}/work-items`, { method: "GET" });
}

export function listNumbering(projectId: string): Promise<NumberingConfig[]> {
  return jsonRequest(`/projects/${projectId}/acceptance-numbering`, { method: "GET" });
}

export function updateNumbering(
  projectId: string,
  kind: "pyc" | "bbnt",
  body: Omit<NumberingConfig, "project_id" | "kind" | "next_number" | "period_key" | "updated_at">,
): Promise<NumberingConfig> {
  return jsonRequest(
    `/projects/${projectId}/acceptance-numbering/${kind}`,
    jsonInit("PUT", body),
  );
}

export function previewRequest(
  projectId: string,
  requestId: string,
): Promise<PreviewPayload> {
  return jsonRequest(
    `/projects/${projectId}/acceptance-requests/${requestId}/preview`,
    { method: "GET" },
  );
}

export function previewRecord(
  projectId: string,
  recordId: string,
): Promise<PreviewPayload> {
  return jsonRequest(
    `/projects/${projectId}/acceptance-records/${recordId}/preview`,
    { method: "GET" },
  );
}

export function createRecordRevision(
  projectId: string,
  recordId: string,
): Promise<AcceptanceRecord> {
  return jsonRequest(
    `/projects/${projectId}/acceptance-records/${recordId}/revisions`,
    { method: "POST" },
  );
}

export function workItemAcceptanceHistory(
  projectId: string,
  workItemId: string,
): Promise<WorkItemAcceptanceHistory> {
  return jsonRequest(
    `/projects/${projectId}/work-items/${workItemId}/acceptance-history`,
    { method: "GET" },
  );
}

export function listRecords(
  projectId: string,
  requestId?: string,
): Promise<AcceptanceRecord[]> {
  const query = requestId ? `?request_id=${encodeURIComponent(requestId)}` : "";
  return jsonRequest(`/projects/${projectId}/acceptance-records${query}`, { method: "GET" });
}

export function getRecord(projectId: string, recordId: string): Promise<AcceptanceRecord> {
  return jsonRequest(
    `/projects/${projectId}/acceptance-records/${recordId}`,
    { method: "GET" },
  );
}

export function createRecord(
  projectId: string,
  body: RecordInput,
): Promise<AcceptanceRecord> {
  return jsonRequest(`/projects/${projectId}/acceptance-records`, jsonInit("POST", body));
}

export function updateRecord(
  projectId: string,
  recordId: string,
  body: Partial<Omit<RecordInput, "request_id">>,
): Promise<AcceptanceRecord> {
  return jsonRequest(
    `/projects/${projectId}/acceptance-records/${recordId}`,
    jsonInit("PATCH", body),
  );
}

export function confirmRecord(
  projectId: string,
  recordId: string,
  body: ConfirmInput,
): Promise<AcceptanceRecord> {
  return jsonRequest(
    `/projects/${projectId}/acceptance-records/${recordId}/confirm`,
    jsonInit("POST", body),
  );
}

/** Export the PYC sheet for a request. PDF uses the validated workbook. */
export function exportRequest(
  projectId: string,
  requestId: string,
  format: "xlsx" | "pdf" = "xlsx",
): Promise<AcceptanceExport> {
  return jsonRequest(
    `/projects/${projectId}/acceptance-requests/${requestId}/exports`,
    jsonInit("POST", { kind: "pyc", format }),
  );
}

/**
 * Export from a record. `kind="pyc"` regenerates the linked request sheet;
 * `kind="bbnt"` requires the record to be human-confirmed first.
 */
export function exportRecord(
  projectId: string,
  recordId: string,
  kind: "pyc" | "bbnt",
  format: "xlsx" | "pdf" = "xlsx",
): Promise<AcceptanceExport> {
  return jsonRequest(
    `/projects/${projectId}/acceptance-records/${recordId}/exports`,
    jsonInit("POST", { kind, format }),
  );
}

export function listRequestExports(
  projectId: string,
  requestId: string,
): Promise<AcceptanceExport[]> {
  return jsonRequest(
    `/projects/${projectId}/acceptance-requests/${requestId}/exports`,
    { method: "GET" },
  );
}

export function listRecordExports(
  projectId: string,
  recordId: string,
): Promise<AcceptanceExport[]> {
  return jsonRequest(
    `/projects/${projectId}/acceptance-records/${recordId}/exports`,
    { method: "GET" },
  );
}

/** Absolute/relative download URL for an export record. */
export function exportDownloadUrl(exported: AcceptanceExport): string {
  if (exported.download_url) return exported.download_url;
  return `${API_BASE}/projects/${exported.project_id}/acceptance-exports/${exported.id}/download`;
}

function decodeFilename(value: string): string {
  let text = value.trim();
  if (text.startsWith('"') && text.endsWith('"')) text = text.slice(1, -1);
  try {
    return decodeURIComponent(text);
  } catch {
    return text;
  }
}

/** Keep the server-provided name; blob downloads need it explicitly. */
export function filenameFromContentDisposition(
  header: string | null,
  fallback: string,
): string {
  if (!header) return fallback;

  const extended = /filename\*\s*=\s*([^;]+)/i.exec(header);
  if (extended) {
    const raw = extended[1].trim();
    const encoded = raw.includes("''") ? raw.split("''", 2)[1] : raw;
    const decoded = decodeFilename(encoded);
    if (decoded) return decoded;
  }

  const quoted = /filename\s*=\s*"([^"]*)"/i.exec(header);
  if (quoted?.[1]) return decodeFilename(quoted[1]);

  const plain = /filename\s*=\s*([^;]+)/i.exec(header);
  if (plain?.[1]) return decodeFilename(plain[1]);

  return fallback;
}

export function fallbackExportFilename(exported: AcceptanceExport): string {
  const prefix = exported.kind === "pyc" ? "YC" : "BBNT";
  const extension = exported.format === "pdf" ? "pdf" : "xlsx";
  return `${prefix}-${exported.id.slice(0, 8)}.${extension}`;
}

export function downloadFilenameFromResponse(
  response: Pick<Response, "headers">,
  exported: AcceptanceExport,
): string {
  return filenameFromContentDisposition(
    response.headers.get("Content-Disposition"),
    fallbackExportFilename(exported),
  );
}

/**
 * Download an authenticated export through fetch + blob.
 *
 * A plain `<a href>` cannot attach the bearer token, which caused admin PYC
 * downloads to fail.  The filename comes from Content-Disposition so both PYC
 * and BBNT keep their server-side name.  Revocation is deferred because some
 * mobile browsers abort the download if the blob URL disappears immediately.
 */
export async function downloadExport(exported: AcceptanceExport): Promise<string> {
  const response = await apiFetchUrl(exportDownloadUrl(exported));
  if (!response.ok) throw await readError(response);
  const blob = await response.blob();
  const filename = downloadFilenameFromResponse(response, exported);
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.rel = "noopener";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  return filename;
}
