import { describe, expect, it } from "vitest";
import type { DailyReport, DailyReportInput } from "../types";
import {
  decideReconnectAction,
  draftConflictsWithServer,
  hasLocalChanges,
  hasServerUpdate,
  reportContentKey,
  selectDraftForLoad,
} from "./reportReconnect";

const base: DailyReport = {
  id: "r1",
  project_id: "p1",
  report_date: "2026-11-11",
  status: "draft",
  notes: "old",
  site_notes: { weather: "Nắng" },
  manpower: [{ group_name: "A", count: 0, person_name: null, organization_id: null }],
  work_logs: [],
  next_day_plans: [],
  created_at: "2026-11-11T01:00:00Z",
  updated_at: "2026-11-11T02:00:00Z",
};

function body(): DailyReportInput {
  return {
    status: base.status,
    notes: base.notes,
    site_notes: base.site_notes,
    manpower: base.manpower,
    work_logs: base.work_logs,
    next_day_plans: base.next_day_plans,
  };
}

describe("report reconnect conflict decisions", () => {
  it("detects a newer server version with exact timestamp comparison", () => {
    expect(hasServerUpdate("2026-11-11T02:00:00Z", "2026-11-11T01:59:58Z")).toBe(true);
    expect(hasServerUpdate("2026-11-11T02:00:00Z", "2026-11-11T02:00:00Z")).toBe(false);
    expect(hasServerUpdate("2026-11-11T01:00:00Z", "2026-11-11T02:00:00Z")).toBe(false);
    expect(hasServerUpdate("invalid", "2026-11-11T02:00:00Z")).toBe(false);
    expect(hasServerUpdate("2026-11-11T02:00:00Z", null)).toBe(true);
  });

  it("detects a same-second server update without a tolerance window", () => {
    expect(
      hasServerUpdate("2026-11-11T02:00:00.500Z", "2026-11-11T02:00:00.000Z"),
    ).toBe(true);
    expect(
      hasServerUpdate("2026-11-11T02:00:00.001Z", "2026-11-11T02:00:00.000Z"),
    ).toBe(true);
    expect(
      hasServerUpdate("2026-11-11T02:00:00.000Z", "2026-11-11T02:00:00.000Z"),
    ).toBe(false);
  });

  it("detects local edits without treating ids as changes", () => {
    expect(hasLocalChanges(body(), base)).toBe(false);
    expect(hasLocalChanges({ ...body(), notes: "changed" }, base)).toBe(true);
    expect(
      hasLocalChanges(
        { ...body(), manpower: [{ ...base.manpower[0], count: null }] },
        base,
      ),
    ).toBe(true);
  });

  it("only acts when a cache is in use and the server is newer", () => {
    const newer = { ...base, updated_at: "2026-11-11T03:00:00Z" };
    expect(
      decideReconnectAction({
        usingCache: false,
        serverReport: newer,
        cachedUpdatedAt: base.updated_at,
        localChanges: true,
      }),
    ).toBe("none");
    expect(
      decideReconnectAction({
        usingCache: true,
        serverReport: newer,
        cachedUpdatedAt: base.updated_at,
        localChanges: false,
      }),
    ).toBe("reload");
    expect(
      decideReconnectAction({
        usingCache: true,
        serverReport: newer,
        cachedUpdatedAt: base.updated_at,
        localChanges: true,
      }),
    ).toBe("conflict");
    expect(
      decideReconnectAction({
        usingCache: true,
        serverReport: base,
        cachedUpdatedAt: base.updated_at,
        localChanges: true,
      }),
    ).toBe("none");
  });

  it("treats a draft based on an older server version as conflicting", () => {
    expect(
      draftConflictsWithServer("2026-11-11T02:00:00Z", "2026-11-11T03:00:00Z"),
    ).toBe(true);
    expect(
      draftConflictsWithServer("2026-11-11T03:00:00Z", "2026-11-11T03:00:00Z"),
    ).toBe(false);
    expect(draftConflictsWithServer(undefined, "2026-11-11T03:00:00Z")).toBe(true);
  });
});

describe("draft selection when server is newer (t1 < t2)", () => {
  it("preserves an edited draft and reports a conflict even when server timestamp is later", () => {
    const edited = { ...body(), notes: "edited offline at t1" };
    const server = { ...base, updated_at: "2026-11-11T03:00:00Z" };
    const decision = selectDraftForLoad({
      draft: {
        payload: edited,
        updatedAt: Date.parse("2026-11-11T02:30:00Z"), // t1 < t2
        baseUpdatedAt: base.updated_at,
        baselineKey: reportContentKey(body()),
      },
      serverReport: server,
      fallbackReport: null,
    });
    expect(decision.useDraft).toBe(true);
    expect(decision.conflict).toBe(true);
  });

  it("reports conflict for an edited draft when the server update is in the same second", () => {
    const edited = { ...body(), notes: "edited offline" };
    const server = {
      ...base,
      updated_at: "2026-11-11T02:00:00.500Z",
    };
    const decision = selectDraftForLoad({
      draft: {
        payload: edited,
        updatedAt: Date.parse("2026-11-11T02:00:00.100Z"),
        baseUpdatedAt: "2026-11-11T02:00:00.000Z",
        baselineKey: reportContentKey(body()),
      },
      serverReport: server,
      fallbackReport: null,
    });
    expect(decision.useDraft).toBe(true);
    expect(decision.conflict).toBe(true);
  });

  it("does not create a false conflict for an untouched autosaved baseline", () => {
    const server = { ...base, updated_at: "2026-11-11T03:00:00Z" };
    const decision = selectDraftForLoad({
      draft: {
        payload: body(),
        updatedAt: Date.parse("2026-11-11T02:30:00Z"),
        baseUpdatedAt: base.updated_at,
        baselineKey: reportContentKey(body()),
      },
      serverReport: server,
      fallbackReport: null,
    });
    expect(decision.useDraft).toBe(false);
    expect(decision.conflict).toBe(false);
  });
});
