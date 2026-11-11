import { describe, expect, it } from "vitest";
import {
  parseManpowerCount,
  presetToManpowerEntry,
  summarizeManpower,
} from "./manpower";

describe("manpower summary", () => {
  it("keeps zero known and null unknown", () => {
    const summary = summarizeManpower([
      { group_name: "Workers", count: 0 },
      { group_name: "Engineers", count: null },
      { group_name: "Supervisors", count: 5 },
    ]);
    expect(summary.knownTotal).toBe(5);
    expect(summary.unknownGroups).toEqual(["Engineers"]);
    expect(summary.zeroGroups).toEqual(["Workers"]);
    expect(summary.hasUnknown).toBe(true);
  });

  it("treats empty input as unknown, not zero", () => {
    expect(parseManpowerCount("")).toBeNull();
    expect(parseManpowerCount("  ")).toBeNull();
    expect(parseManpowerCount("0")).toBe(0);
    expect(parseManpowerCount("12")).toBe(12);
    expect(parseManpowerCount("-1")).toBeNull();
    expect(parseManpowerCount("1.5")).toBeNull();
  });

  it("converts presets without collapsing zero into null", () => {
    const zero = presetToManpowerEntry({
      group_name: "Workers",
      person_name: null,
      count: 0,
      organization_id: "org1",
    });
    const unknown = presetToManpowerEntry({
      group_name: "Engineers",
      person_name: "A",
      count: null,
      organization_id: null,
    });
    expect(zero).toEqual({
      group_name: "Workers",
      person_name: null,
      count: 0,
      organization_id: "org1",
    });
    expect(unknown.count).toBeNull();
    expect(unknown.organization_id).toBeNull();
  });
});
