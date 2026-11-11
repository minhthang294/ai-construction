import type {
  AcceptanceExport,
  AcceptanceRecord,
  AcceptanceRequest,
  ConfirmInput,
  LinkedDailyReport,
  NumberingConfig,
  ParticipantProfile,
  ParticipantProfileInput,
  PreviewPayload,
  RecordInput,
  RequestInput,
  WorkItemAcceptanceHistory,
} from "../types";

const API_BASE = (import.meta as any)?.env?.VITE_API_BASE ?? "/api/v1";

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
  const token = localStorage.getItem("access_token");
  const headers = new Headers(init?.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  return fetch(`${API_BASE}${path}`, { ...init, headers });
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

export function listRequests(projectId: string): Promise<AcceptanceRequest[]> {
  return jsonRequest(`/projects/${projectId}/acceptance-requests`, { method: "GET" });
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
