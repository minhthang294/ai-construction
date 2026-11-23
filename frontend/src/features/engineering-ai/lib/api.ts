import type {
  ChatResponse,
  Conversation,
  DocumentPage,
  PageExtractionRecord,
  QuestionSuggestion,
  SourceDocument,
} from "../types";

const API_BASE = (import.meta as any)?.env?.VITE_API_BASE ?? "/api/v1";

export async function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  const token = typeof localStorage !== "undefined" ? localStorage.getItem("access_token") : null;
  const headers = new Headers(init?.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  return fetch(`${API_BASE}${path}`, { ...init, headers });
}

async function jsonOrThrow<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body?.detail ?? detail;
    } catch {
      // keep status text
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return response.json() as Promise<T>;
}

export async function listDocuments(projectId: string, includeHistory = true): Promise<SourceDocument[]> {
  const suffix = includeHistory ? "" : "?include_history=false";
  const response = await apiFetch(`/projects/${projectId}/documents${suffix}`);
  return jsonOrThrow<SourceDocument[]>(response);
}

export async function getDocumentPage(
  projectId: string,
  documentId: string,
  pageNumber: number,
): Promise<DocumentPage> {
  const response = await apiFetch(
    `/projects/${projectId}/documents/${documentId}/pages/${pageNumber}`,
  );
  return jsonOrThrow<DocumentPage>(response);
}

export async function fetchAuthenticatedBlob(path: string): Promise<Blob> {
  const response = await apiFetch(path);
  if (!response.ok) throw new Error(`Không tải được tệp (${response.status}).`);
  return response.blob();
}

/** Fetch an API URL returned by the backend (already prefixed with /api/v1). */
export async function fetchResourceBlob(apiUrl: string): Promise<Blob> {
  const path = apiUrl.startsWith("/api/v1") ? apiUrl.slice("/api/v1".length) : apiUrl;
  return fetchAuthenticatedBlob(path);
}

export async function listQuestionSuggestions(
  projectId: string,
): Promise<QuestionSuggestion[]> {
  const response = await apiFetch(
    `/projects/${projectId}/ai/question-suggestions`,
  );
  return jsonOrThrow<QuestionSuggestion[]>(response);
}

export async function askEngineeringAI(  projectId: string,
  message: string,
  conversationId?: string | null,
  topK = 6,
  scope: "effective" | "history" = "effective",
): Promise<ChatResponse> {
  const response = await apiFetch(`/projects/${projectId}/ai/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      conversation_id: conversationId ?? null,
      top_k: topK,
      scope,
    }),
  });
  return jsonOrThrow<ChatResponse>(response);
}

export async function listConversations(
  projectId: string,
  q?: string,
): Promise<Conversation[]> {
  const query = q?.trim() ? `?q=${encodeURIComponent(q.trim())}` : "";
  const response = await apiFetch(`/projects/${projectId}/ai/conversations${query}`);
  return jsonOrThrow<Conversation[]>(response);
}

export async function createConversation(
  projectId: string,
  title?: string,
): Promise<Conversation> {
  const response = await apiFetch(`/projects/${projectId}/ai/conversations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title: title?.trim() || null }),
  });
  return jsonOrThrow<Conversation>(response);
}

export async function renameConversation(
  projectId: string,
  conversationId: string,
  title: string,
): Promise<Conversation> {
  const response = await apiFetch(
    `/projects/${projectId}/ai/conversations/${conversationId}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title }),
    },
  );
  return jsonOrThrow<Conversation>(response);
}

export async function deleteConversation(
  projectId: string,
  conversationId: string,
): Promise<void> {
  const response = await apiFetch(
    `/projects/${projectId}/ai/conversations/${conversationId}`,
    { method: "DELETE" },
  );
  if (!response.ok) throw new Error(`Không xóa được hội thoại (${response.status}).`);
}

export async function listPageExtractions(
  projectId: string,
  documentId: string,
  page?: number,
  status?: "proposed" | "verified" | "rejected",
): Promise<PageExtractionRecord[]> {
  const params = new URLSearchParams();
  if (page != null) params.set("page", String(page));
  if (status) params.set("status", status);
  const suffix = params.size > 0 ? `?${params.toString()}` : "";
  const response = await apiFetch(
    `/projects/${projectId}/documents/${documentId}/extractions${suffix}`,
  );
  return jsonOrThrow<PageExtractionRecord[]>(response);
}

export async function verifyPageExtraction(
  projectId: string,
  extractionId: string,
  status: "verified" | "rejected",
  note?: string,
): Promise<PageExtractionRecord> {
  const response = await apiFetch(
    `/projects/${projectId}/page-extractions/${extractionId}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status, note: note?.trim() || null }),
    },
  );
  return jsonOrThrow<PageExtractionRecord>(response);
}

export async function getConversation(
  projectId: string,
  conversationId: string,
): Promise<Conversation> {
  const response = await apiFetch(
    `/projects/${projectId}/ai/conversations/${conversationId}`,
  );
  return jsonOrThrow<Conversation>(response);
}
