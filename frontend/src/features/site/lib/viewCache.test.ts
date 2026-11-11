import { describe, expect, it } from "vitest";
import {
  decideViewSource,
  makeViewCacheRecord,
  offlineDataLabel,
  selectCachedView,
  viewCacheKey,
  type ViewCacheRecord,
} from "./viewCache";

function record(
  projectId: string,
  date: string,
  cachedAt: number,
  report: string,
): ViewCacheRecord {
  return makeViewCacheRecord({
    projectId,
    date,
    report,
    photos: [{ id: "photo-1", filename: "a.jpg" }],
    workItems: [{ id: "w1", code: "W1" }],
    cachedAt,
  });
}

describe("offline view cache", () => {
  it("stores and reads a snapshot by exact project+date", () => {
    const cached = record("p1", "2026-11-11", 1000, "report-a");
    expect(cached.key).toBe(viewCacheKey("p1", "2026-11-11"));
    expect(selectCachedView([cached], "p1", "2026-11-11")).toBe(cached);
  });

  it("never returns another project's or another date's snapshot", () => {
    const p1 = record("p1", "2026-11-11", 1000, "p1-report");
    const p2 = record("p2", "2026-11-11", 2000, "p2-report");
    const otherDate = record("p1", "2026-11-12", 3000, "other-date");
    expect(selectCachedView([p1, p2, otherDate], "p1", "2026-11-11")).toBe(p1);
    expect(selectCachedView([p2], "p1", "2026-11-11")).toBeUndefined();
  });

  it("selects the newest snapshot when multiple records match", () => {
    const older = record("p1", "2026-11-11", 1000, "older");
    const newer = record("p1", "2026-11-11", 5000, "newer");
    expect(selectCachedView([older, newer], "p1", "2026-11-11")).toBe(newer);
  });

  it("falls back only when the server failed and a cache exists", () => {
    const cached = record("p1", "2026-11-11", 1000, "cached");
    expect(decideViewSource(true, cached)).toBe("cache");
    expect(decideViewSource(true, undefined)).toBe("empty");
    expect(decideViewSource(false, cached)).toBe("server");
  });

  it("labels the cached timestamp in Vietnamese", () => {
    const label = offlineDataLabel(Date.UTC(2026, 10, 11, 2, 30, 0));
    expect(label).toContain("Dữ liệu lưu trên thiết bị, cập nhật lúc");
    expect(label).toContain("11/11/2026");
  });
});
