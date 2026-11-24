import { describe, expect, it } from "vitest";
import {
  buildLatestDayZaloSummary,
  componentUnit,
  formatLatestDayLine,
  formatOverviewPercent,
  formatSegmentLabel,
  formatShortDate,
  uniqueCodes,
  type LatestDay,
} from "./overviewFormat";

function day(overrides: Partial<LatestDay> = {}): LatestDay {
  return {
    date: "2026-11-21",
    works: [],
    manpower_total: null,
    photo_count: 0,
    daily_report_exists: false,
    acceptance_today: [],
    ...overrides,
  };
}

describe("overview formatting", () => {
  it("writes the latest day line from the real work group", () => {
    const line = formatLatestDayLine(day({
      works: [{
        stage_name: "Đục bê tông om vỡ",
        zone: "Cầu chính",
        segment: 2,
        component_type: "pile",
        status: "COMPLETED",
        count: 14,
        codes: ["F67"],
      }],
    }));
    expect(line).toBe("21/11 · Đục bê tông om vỡ · PD2 Cầu chính · 14 cọc hoàn thành");
  });

  it("picks the largest group and counts the other groups", () => {
    const line = formatLatestDayLine(day({
      works: [
        { stage_name: "Sơn bảo vệ", zone: "Cầu dẫn", segment: 1, component_type: "beam",
          status: "IN_PROGRESS", count: 2, codes: ["D1", "D2"] },
        { stage_name: "Đục bê tông om vỡ", zone: "Cầu chính", segment: 2, component_type: "pile",
          status: "COMPLETED", count: 5, codes: ["F67", "F64"] },
      ],
    }));
    expect(line).toBe("21/11 · Đục bê tông om vỡ · PD2 Cầu chính · 5 cọc hoàn thành · +1 nhóm công tác khác");
  });

  it("keeps empty days explicit instead of showing zero work", () => {
    expect(formatLatestDayLine(day({ date: null }))).toBe(
      "Chưa có báo cáo ngày hoặc tiến độ thi công.",
    );
    expect(formatLatestDayLine(day())).toBe("21/11 · Chưa có công tác ghi nhận");
  });

  it("formats dates, percentages, units and segment labels for Vietnamese readers", () => {
    expect(formatShortDate("2026-11-21")).toBe("21/11");
    expect(formatShortDate(null)).toBe("—");
    expect(formatOverviewPercent(0.6667)).toBe("66,7%");
    expect(formatOverviewPercent(Number.NaN)).toBe("0%");
    expect(componentUnit("pile")).toBe("cọc");
    expect(componentUnit("beam")).toBe("dầm");
    expect(componentUnit("other")).toBe("cấu kiện");
    expect(formatSegmentLabel("Cầu chính", 2)).toBe("PD2 · Cầu chính");
  });

  it("deduplicates codes across work groups", () => {
    expect(uniqueCodes([
      { stage_name: "A", zone: "Z", segment: 1, component_type: "pile", status: "COMPLETED",
        count: 2, codes: ["F67", "F64"] },
      { stage_name: "B", zone: "Z", segment: 1, component_type: "pile", status: "COMPLETED",
        count: 1, codes: ["F64"] },
    ])).toEqual(["F64", "F67"]);
  });

  it("builds the copyable Zalo summary from the latest day groups", () => {
    const text = buildLatestDayZaloSummary(day({
      works: [{
        stage_name: "Đục bê tông om vỡ",
        zone: "Cầu chính",
        segment: 2,
        component_type: "pile",
        status: "COMPLETED",
        count: 2,
        codes: ["F67", "F64"],
      }],
    }), 4);
    expect(text).toContain("Ngày 21/11/2026");
    expect(text).toContain("Tổng: 2 cọc");
    expect(text).toContain("Đục bê tông om vỡ: 2 cọc");
    expect(text).toContain("F67, F64");
    expect(text).toContain("Chưa nghiệm thu: 4 cấu kiện đã xong");
  });
});
