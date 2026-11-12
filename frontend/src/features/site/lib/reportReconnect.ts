// Pure conflict decisions for reopening a cached report after reconnecting.
// No browser/network access: the page supplies the server report and local body.

import type { DailyReport, DailyReportInput } from "../types";

export type ReconnectDecision = "none" | "reload" | "conflict";

function time(value?: string | null): number {
  if (!value) return Number.NaN;
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : Number.NaN;
}

export function hasServerUpdate(
  serverUpdatedAt?: string | null,
  baseUpdatedAt?: string | null,
): boolean {
  const server = time(serverUpdatedAt);
  if (!Number.isFinite(server)) return false;
  const base = time(baseUpdatedAt);
  // An old draft without a base timestamp cannot be trusted to be current.
  if (!Number.isFinite(base)) return true;
  // `baseUpdatedAt` is the exact server timestamp. Any strictly later server
  // update must win; a coarse tolerance could miss a second-device edit.
  return server > base;
}

export function draftConflictsWithServer(
  draftBaseUpdatedAt: string | null | undefined,
  serverUpdatedAt: string | null | undefined,
): boolean {
  return hasServerUpdate(serverUpdatedAt, draftBaseUpdatedAt);
}

function normalise(value: DailyReportInput | DailyReport) {
  return {
    status: value.status,
    notes: value.notes ?? null,
    site_notes: {
      weather: value.site_notes?.weather ?? null,
      materials: value.site_notes?.materials ?? null,
      equipment: value.site_notes?.equipment ?? null,
      incidents: value.site_notes?.incidents ?? null,
      difficulties: value.site_notes?.difficulties ?? null,
      safety: value.site_notes?.safety ?? null,
      recommendations: value.site_notes?.recommendations ?? null,
      other: value.site_notes?.other ?? null,
    },
    manpower: value.manpower.map((entry) => ({
      group_name: entry.group_name,
      person_name: entry.person_name ?? null,
      count: entry.count ?? null,
      organization_id: entry.organization_id ?? null,
    })),
    work_logs: value.work_logs.map((entry) => ({
      work_item_id: entry.work_item_id ?? null,
      location: entry.location ?? null,
      component: entry.component ?? null,
      quantity: entry.quantity ?? null,
      unit: entry.unit ?? null,
      start_time: entry.start_time ?? null,
      end_time: entry.end_time ?? null,
      status: entry.status ?? null,
      notes: entry.notes ?? null,
    })),
    next_day_plans: value.next_day_plans.map((entry) => ({
      plan_date: entry.plan_date,
      work_item_id: entry.work_item_id ?? null,
      description: entry.description ?? null,
      location: entry.location ?? null,
      manpower: entry.manpower ?? null,
      equipment: entry.equipment ?? null,
      dependency: entry.dependency ?? null,
    })),
  };
}

/** Ignore server ids/timestamps; compare only user-editable fields. */
export function hasLocalChanges(
  body: DailyReportInput,
  base: DailyReport | null | undefined,
): boolean {
  if (!base) return true;
  return JSON.stringify(normalise(body)) !== JSON.stringify(normalise(base));
}

export function decideReconnectAction(input: {
  usingCache: boolean;
  serverReport: DailyReport | null | undefined;
  cachedUpdatedAt?: string | null;
  localChanges: boolean;
}): ReconnectDecision {
  if (!input.usingCache) return "none";
  if (!input.serverReport) return "none";
  if (!hasServerUpdate(input.serverReport.updated_at, input.cachedUpdatedAt)) {
    return "none";
  }
  return input.localChanges ? "conflict" : "reload";
}

export type DraftLike = {
  payload: unknown;
  updatedAt: number;
  baseUpdatedAt?: string | null;
  /** Content key of the server/base body this draft started from. */
  baselineKey?: string | null;
};

export type DraftLoadDecision = {
  useDraft: boolean;
  conflict: boolean;
  baselineKey: string | null;
};

/** Stable representation of user-editable report fields (ignores ids/timestamps). */
export function reportContentKey(value: DailyReportInput | DailyReport): string {
  return JSON.stringify(normalise(value));
}

function contentKeyOrNull(value: unknown): string | null {
  if (!value || typeof value !== "object") return null;
  try {
    return reportContentKey(value as DailyReportInput);
  } catch {
    return null;
  }
}

/**
 * Select the form body when a local draft exists.
 *
 * - A draft with actual edits must be shown even when the server timestamp is
 *   newer; the caller shows a conflict and blocks overwriting the server.
 * - An untouched autosaved baseline is not a conflict: the server/cache body wins.
 */
export function selectDraftForLoad(input: {
  draft?: DraftLike | null;
  serverReport?: DailyReport | null;
  fallbackReport?: DailyReport | null;
}): DraftLoadDecision {
  const base = input.serverReport ?? input.fallbackReport ?? null;
  const baseKey = base ? reportContentKey(base) : null;
  const draft = input.draft;
  if (!draft) {
    return { useDraft: false, conflict: false, baselineKey: baseKey };
  }

  const draftKey = contentKeyOrNull(draft.payload);
  const draftHasEdits = draft.baselineKey
    ? draftKey !== draft.baselineKey
    : baseKey
      ? draftKey !== baseKey
      : true;
  const serverChanged = base
    ? hasServerUpdate(base.updated_at, draft.baseUpdatedAt)
    : false;

  return {
    useDraft: draftHasEdits,
    conflict: draftHasEdits && Boolean(input.serverReport) && serverChanged,
    baselineKey: draftHasEdits ? (draft.baselineKey ?? null) : baseKey,
  };
}

