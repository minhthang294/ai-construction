// Read-only acceptance history loader for the site report page.
// It prefers the acceptance-agent work-item history endpoint and falls back to
// the existing project-level PYC/BBNT list endpoints.  It never mutates PYC/BBNT.

import { apiFetch } from "./api";
import type {
  AcceptanceRecordSummary,
  AcceptanceRequestSummary,
  WorkItemAcceptanceHistory,
} from "../types";

type RawRecord = Record<string, unknown>;

export type AcceptanceHistorySource = "history" | "fallback";

export type AcceptanceHistoryResult = {
  items: WorkItemAcceptanceHistory[];
  source: AcceptanceHistorySource;
  warning?: string | null;
};

function text(value: unknown): string | null {
  if (value === null || value === undefined) return null;
  const valueText = String(value).trim();
  return valueText || null;
}

function numberOrNull(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function warnings(value: unknown): string[] {
  if (!value) return [];
  const values = Array.isArray(value) ? value : [value];
  return values
    .map((entry) => {
      if (typeof entry === "string") return entry.trim();
      if (entry && typeof entry === "object") {
        const record = entry as RawRecord;
        const message = text(record.message) ?? text(record.detail);
        if (message) return message;
        try {
          return JSON.stringify(entry);
        } catch {
          return "";
        }
      }
      return text(entry) ?? "";
    })
    .filter((entry) => entry.length > 0);
}

function normalizeStale(raw: RawRecord): boolean {
  return raw.stale === true || raw.is_stale === true;
}

function normalizeRecord(raw: RawRecord): AcceptanceRecordSummary | null {
  const id = text(raw.id);
  if (!id) return null;
  return {
    id,
    number: text(raw.number),
    status: text(raw.status) ?? "unknown",
    result: text(raw.result),
    revision: numberOrNull(raw.revision),
    stale: normalizeStale(raw),
    warnings: warnings(raw.warnings ?? raw.warning),
    confirmed_at: text(raw.confirmed_at),
  };
}

function recordList(raw: RawRecord): RawRecord[] {
  const candidates = [
    raw.records,
    raw.bbnt,
    raw.acceptance_records,
    raw.record_list,
  ];
  for (const candidate of candidates) {
    if (Array.isArray(candidate)) return candidate as RawRecord[];
  }
  return [];
}

export function normalizeRequest(raw: RawRecord): AcceptanceRequestSummary | null {
  const id = text(raw.id);
  if (!id) return null;
  return {
    id,
    number: text(raw.number) ?? text(raw.code) ?? id,
    status: text(raw.status) ?? "unknown",
    work_item_id: text(raw.work_item_id),
    revision: numberOrNull(raw.revision),
    stale: normalizeStale(raw),
    warnings: warnings(raw.warnings ?? raw.warning),
    requested_at: text(raw.requested_at),
    records: recordList(raw)
      .map((entry) => normalizeRecord(entry))
      .filter((entry): entry is AcceptanceRecordSummary => entry !== null),
  };
}

function requestList(payload: unknown): RawRecord[] {
  if (Array.isArray(payload)) return payload as RawRecord[];
  if (!payload || typeof payload !== "object") return [];
  const record = payload as RawRecord;
  for (const key of ["requests", "items", "history", "data"]) {
    const candidate = record[key];
    if (Array.isArray(candidate)) return candidate as RawRecord[];
  }
  return [];
}

export function normalizeAcceptanceHistory(
  payload: unknown,
  workItemId: string,
): AcceptanceRequestSummary[] {
  const raw = requestList(payload);
  const flat = raw.some((entry) => {
    const kind = text(entry.kind);
    return kind === "pyc" || kind === "bbnt";
  });
  if (flat) {
    // Work-item history returns a flat list of PYC/BBNT rows.  Group BBNT
    // rows under their request so the panel can render one card per PYC.
    const requests = new Map<string, RawRecord>();
    const records = new Map<string, RawRecord[]>();
    for (const entry of raw) {
      const kind = text(entry.kind);
      const id = text(entry.id);
      if (!id) continue;
      if (kind === "pyc") {
        requests.set(id, entry);
      } else if (kind === "bbnt") {
        const requestId = text(entry.request_id);
        if (!requestId) continue;
        records.set(requestId, [...(records.get(requestId) ?? []), entry]);
      }
    }
    const rows: AcceptanceRequestSummary[] = [];
    for (const entry of requests.values()) {
      const request = normalizeRequest(entry);
      if (!request) continue;
      rows.push({
        ...request,
        records: (records.get(request.id) ?? [])
          .map((record) => normalizeRecord(record))
          .filter((record): record is AcceptanceRecordSummary => record !== null),
      });
    }
    // A BBNT without its PYC should still be visible rather than silently lost.
    for (const [requestId, entries] of records) {
      if (requests.has(requestId)) continue;
      const first = entries[0];
      if (!first) continue;
      rows.push({
        id: requestId,
        number: text(first.number) ?? requestId,
        status: "unknown",
        revision: null,
        stale: false,
        warnings: [],
        records: entries
          .map((record) => normalizeRecord(record))
          .filter((record): record is AcceptanceRecordSummary => record !== null),
      });
    }
    return rows;
  }
  return raw
    .map((entry) => normalizeRequest(entry))
    .filter(
      (entry): entry is AcceptanceRequestSummary =>
        entry !== null &&
        (!entry.work_item_id || entry.work_item_id === workItemId),
    );
}

/** Fallback when `/acceptance-requests` only exposes flat records by request. */
export function buildFallbackHistory(
  requests: unknown[],
  records: unknown[],
  workItemId: string,
): AcceptanceRequestSummary[] {
  const recordsByRequest = new Map<string, AcceptanceRecordSummary[]>();
  records.forEach((entry) => {
    if (!entry || typeof entry !== "object") return;
    const raw = entry as RawRecord;
    const record = normalizeRecord(raw);
    const requestId = text(raw.request_id);
    if (record && requestId) {
      recordsByRequest.set(requestId, [
        ...(recordsByRequest.get(requestId) ?? []),
        record,
      ]);
    }
  });
  return requests
    .filter((entry): entry is RawRecord => Boolean(entry && typeof entry === "object"))
    .map((entry) => {
      const request = normalizeRequest(entry);
      if (!request || request.work_item_id !== workItemId) return null;
      return {
        ...request,
        records: recordsByRequest.get(request.id) ?? request.records,
      };
    })
    .filter((entry): entry is AcceptanceRequestSummary => entry !== null);
}

async function fetchJson(res: Response): Promise<unknown> {
  try {
    return await res.json();
  } catch {
    return null;
  }
}

/**
 * Load history for the given work items.  A 404/missing history endpoint is an
 * expected state during integration and resolves to the flat-list fallback.
 */
export async function loadAcceptanceHistory(
  projectId: string,
  workItemIds: string[],
): Promise<AcceptanceHistoryResult> {
  const ids = Array.from(new Set(workItemIds.filter(Boolean)));
  if (ids.length === 0) return { items: [], source: "history" };

  const historyItems: WorkItemAcceptanceHistory[] = [];
  let historyEndpointMissing = false;
  let warning: string | null = null;

  for (const workItemId of ids) {
    const res = await apiFetch(
      `/projects/${projectId}/work-items/${workItemId}/acceptance-history`,
    );
    if (res.status === 404) {
      historyEndpointMissing = true;
      break;
    }
    if (!res.ok) {
      historyEndpointMissing = true;
      warning = `Không tải được lịch sử nghiệm thu (${res.status}).`;
      break;
    }
    historyItems.push({
      work_item_id: workItemId,
      requests: normalizeAcceptanceHistory(await fetchJson(res), workItemId),
    });
  }
  if (!historyEndpointMissing) {
    return { items: historyItems, source: "history", warning: null };
  }

  try {
    const [requestsRes, recordsRes] = await Promise.all([
      apiFetch(`/projects/${projectId}/acceptance-requests`),
      apiFetch(`/projects/${projectId}/acceptance-records`),
    ]);
    if (requestsRes.status === 404) {
      return { items: [], source: "fallback", warning: null };
    }
    if (!requestsRes.ok) {
      return {
        items: [],
        source: "fallback",
        warning: `Không tải được PYC/BBNT (${requestsRes.status}).`,
      };
    }
    const requests = await fetchJson(requestsRes);
    const records = recordsRes.ok ? await fetchJson(recordsRes) : [];
    const requestRows = Array.isArray(requests) ? requests : requestList(requests);
    const recordRows = Array.isArray(records) ? records : [];
    return {
      items: ids.map((workItemId) => ({
        work_item_id: workItemId,
        requests: buildFallbackHistory(requestRows, recordRows, workItemId),
      })),
      source: "fallback",
      warning,
    };
  } catch (error) {
    return {
      items: [],
      source: "fallback",
      warning:
        error instanceof Error
          ? `Không tải được lịch sử nghiệm thu: ${error.message}`
          : "Không tải được lịch sử nghiệm thu.",
    };
  }
}
